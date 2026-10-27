"""Fetch ENTSO-E day-ahead prices and archive the raw XML in S3.
"""
import argparse
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import boto3

API_URL = "https://web-api.tp.entsoe.eu/api"
BERLIN = ZoneInfo("Europe/Berlin")
UTC = ZoneInfo("UTC")
BIDDING_ZONES = {"DE-LU": "10Y1001A1001A82H"}  # add more zones later

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def delivery_window_utc(delivery_date: date) -> tuple[str, str]:
    """A German delivery day (00:00-24:00 Berlin time) as an ENTSO-E UTC window."""
    start = datetime.combine(delivery_date, time(0), tzinfo=BERLIN)
    end = datetime.combine(delivery_date + timedelta(days=1), time(0), tzinfo=BERLIN)
    fmt = "%Y%m%d%H%M"
    return start.astimezone(UTC).strftime(fmt), end.astimezone(UTC).strftime(fmt)


def fetch_day_ahead_prices(token: str, bzn_code: str, delivery_date: date) -> bytes | None:
    """Return the raw XML, or None if ENTSO-E has no data for that day yet."""
    period_start, period_end = delivery_window_utc(delivery_date)
    params = {
        "securityToken": token,
        "documentType": "A44",  # day-ahead prices
        "in_Domain": bzn_code,
        "out_Domain": bzn_code,
        "periodStart": period_start,
        "periodEnd": period_end,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read()
        if b"Acknowledgement_MarketDocument" in body:
            logger.warning("No data for %s on %s", bzn_code, delivery_date)
            return None
        # never log the URL: it contains the token
        raise RuntimeError(f"ENTSO-E HTTP {e.code}: {body[:300]!r}") from e

    if b"Acknowledgement_MarketDocument" in body:
        logger.warning("No data for %s on %s", bzn_code, delivery_date)
        return None
    return body


def s3_key(bzn: str, delivery_date: date) -> str:
    return (
        f"entsoe/day_ahead_prices/bzn={bzn}/"
        f"delivery_date={delivery_date.isoformat()}/response.xml"
    )


def default_dates(today: date, lookback_days: int = 2) -> list[date]:
    """Tomorrow plus the last few days, to pick up ENTSO-E revisions."""
    return [today + timedelta(days=d) for d in range(1, -lookback_days - 1, -1)]


def run(delivery_dates: list[date], bucket: str, token: str, s3=None) -> list[dict]:
    s3 = s3 or boto3.client("s3")
    results = []
    for bzn, code in BIDDING_ZONES.items():
        for d in delivery_dates:
            body = fetch_day_ahead_prices(token, code, d)
            if body is None:
                results.append({"bzn": bzn, "date": d.isoformat(), "status": "no_data"})
                continue
            key = s3_key(bzn, d)
            s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/xml")
            logger.info("Saved s3://%s/%s (%d bytes)", bucket, key, len(body))
            results.append({"bzn": bzn, "date": d.isoformat(), "status": "saved", "key": key})
    return results

def get_token() -> str:
    """Local runs: env var. Lambda: SSM Parameter Store."""
    if os.environ.get("ENTSOE_API_KEY"):
        return os.environ["ENTSOE_API_KEY"]
    resp = boto3.client("ssm").get_parameter(
        Name=os.environ["ENTSOE_PARAM_NAME"], WithDecryption=True
    )
    return resp["Parameter"]["Value"]
    
def lambda_handler(event, context):
    """Lambda entry point. Optional event: {"delivery_dates": ["2026-10-27"]}."""
    if event and event.get("delivery_dates"):
        dates = [date.fromisoformat(d) for d in event["delivery_dates"]]
    else:
        dates = default_dates(datetime.now(BERLIN).date())
    return run(dates, os.environ["RAW_BUCKET"], os.environ["ENTSOE_API_KEY"])


def load_env_file(path: str) -> None:
    """Load KEY=VALUE lines from a local .env file. Real env vars take priority."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    load_env_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", action="append", help="YYYY-MM-DD, repeatable")
    args = parser.parse_args()
    event = {"delivery_dates": args.date} if args.date else {}
    for r in lambda_handler(event, None):
        print(r)