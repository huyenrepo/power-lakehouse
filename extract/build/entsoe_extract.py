"""Fetch ENTSO-E day-ahead prices, archive the raw XML in S3,
and deliver a copy to a Databricks Unity Catalog Volume.
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
BIDDING_ZONES = {"DE-LU": "10Y1001A1001A82H",
                 "FR":    "10YFR-RTE------C",
                 "NL":    "10YNL----------L",
                 "AT":    "10YAT-APG------L"}

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_secret(env_var: str, param_env_var: str) -> str:
    """Local runs: read from env var. Lambda: read from SSM Parameter Store."""
    if os.environ.get(env_var):
        return os.environ[env_var]
    param_name = os.environ.get(param_env_var)
    if not param_name:
        raise KeyError(f"Set {env_var} (local) or {param_env_var} (SSM name)")
    resp = boto3.client("ssm").get_parameter(Name=param_name, WithDecryption=True)
    return resp["Parameter"]["Value"]


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
        "documentType": "A44",
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
        raise RuntimeError(f"ENTSO-E HTTP {e.code}: {body[:300]!r}") from e

    if b"Acknowledgement_MarketDocument" in body:
        logger.warning("No data for %s on %s", bzn_code, delivery_date)
        return None
    return body


def upload_to_volume(host: str, token: str, volume_path: str, body: bytes) -> None:
    """PUT a file into a Unity Catalog Volume via the Databricks Files API."""
    path = urllib.parse.quote(volume_path, safe="/=")
    url = f"{host.rstrip('/')}/api/2.0/fs/files{path}?overwrite=true"
    req = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60):
            pass  # 204 No Content = success
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Databricks HTTP {e.code}: {e.read()[:300]!r}") from e


def s3_key(bzn: str, delivery_date: date) -> str:
    return (
        f"entsoe/day_ahead_prices/bzn={bzn}/"
        f"delivery_date={delivery_date.isoformat()}/response.xml"
    )


def default_dates(today: date, lookback_days: int = 0) -> list[date]:
    """Tomorrow plus the last few days, to pick up ENTSO-E revisions."""
    return [today + timedelta(days=d) for d in range(1, -lookback_days - 1, -1)]


def run(delivery_dates, bucket, entsoe_token, databricks=None, s3=None, zones=None) -> list[dict]:
    """databricks: {"host", "token", "volume_base"} or None to skip the Volume upload."""
    s3 = s3 or boto3.client("s3")
    zones = zones or list(BIDDING_ZONES.keys())
    if isinstance(zones, str):
        zones = [zones]
    results = []
    for bzn in zones:
        code = BIDDING_ZONES[bzn]
        for d in delivery_dates:
            body = fetch_day_ahead_prices(entsoe_token, code, d)
            if body is None:
                results.append({"bzn": bzn, "date": d.isoformat(), "status": "no_data"})
                continue

            # 1. Archive in S3 first: this is the source of truth
            key = s3_key(bzn, d)
            s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/xml")
            logger.info("Saved s3://%s/%s (%d bytes)", bucket, key, len(body))
            result = {"bzn": bzn, "date": d.isoformat(), "status": "saved", "key": key}

            # 2. Deliver a copy to Databricks
            if databricks:
                volume_path = f"{databricks['volume_base']}/{key}"
                try:
                    upload_to_volume(databricks["host"], databricks["token"], volume_path, body)
                    logger.info("Uploaded %s", volume_path)
                    result["volume_path"] = volume_path
                except Exception as e:
                    logger.error("Volume upload failed for %s: %s", volume_path, e)
                    result["status"] = "s3_only"
            results.append(result)

    failed = [r for r in results if r["status"] == "s3_only"]
    if failed:
        # fail the run so it shows as an error and the schedule retries
        raise RuntimeError(f"Volume upload failed for {len(failed)} file(s): {failed}")
    return results


def lambda_handler(event, context):
    """Optional event: {"delivery_dates": ["2026-10-20"]}."""
    if event and event.get("delivery_dates"):
        dates = [date.fromisoformat(d) for d in event["delivery_dates"]]
    else:
        dates = default_dates(datetime.now(BERLIN).date())

    databricks = None
    if os.environ.get("DATABRICKS_HOST"):
        databricks = {
            "host": os.environ["DATABRICKS_HOST"],
            "token": get_secret("DATABRICKS_TOKEN", "DATABRICKS_TOKEN_PARAM"),
            "volume_base": os.environ.get("VOLUME_BASE", "/Volumes/workspace/landing/raw"),
        }

    zones = event.get("bidding_zones") if event else None
    entsoe_token = get_secret("ENTSOE_API_KEY", "ENTSOE_PARAM_NAME")
    return run(dates, os.environ["RAW_BUCKET"], entsoe_token, databricks, zones=zones)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", action="append", help="YYYY-MM-DD, repeatable")
    args = parser.parse_args()
    event = {"delivery_dates": args.date} if args.date else {}
    for r in lambda_handler(event, None):
        print(r)