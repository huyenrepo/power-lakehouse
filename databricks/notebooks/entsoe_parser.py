"""Parse ENTSO-E day-ahead price XML (document type A44) into flat rows."""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone


def _local(tag: str) -> str:
    """Strip the XML namespace: '{urn:...}Point' -> 'Point'."""
    return tag.rsplit("}", 1)[-1]


def _children(elem, name):
    return [c for c in elem if _local(c.tag) == name]


def _child(elem, name):
    found = _children(elem, name)
    return found[0] if found else None


def _text(elem, name):
    c = _child(elem, name)
    return c.text.strip() if c is not None and c.text else None


def _resolution_minutes(resolution: str) -> int:
    m = re.fullmatch(r"PT(\d+)M", resolution or "")
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"PT(\d+)H", resolution or "")
    if m:
        return int(m.group(1)) * 60
    raise ValueError(f"Unsupported resolution: {resolution}")


def parse_day_ahead(xml_bytes: bytes) -> list[dict]:
    """Return one dict per <Point>, with its absolute delivery start time in UTC."""
    root = ET.fromstring(xml_bytes)
    rows = []
    for ts in _children(root, "TimeSeries"):
        currency = _text(ts, "currency_Unit.name")
        price_unit = _text(ts, "price_Measure_Unit.name")
        curve_type = _text(ts, "curveType")
        for period in _children(ts, "Period"):
            interval = _child(period, "timeInterval")
            start = datetime.strptime(_text(interval, "start"), "%Y-%m-%dT%H:%MZ")
            start = start.replace(tzinfo=timezone.utc)
            resolution = _text(period, "resolution")
            step = timedelta(minutes=_resolution_minutes(resolution))
            for point in _children(period, "Point"):
                position = int(_text(point, "position"))
                rows.append({
                    "delivery_start_utc": start + (position - 1) * step,
                    "price": float(_text(point, "price.amount")),
                    "currency": currency,
                    "price_unit": price_unit,
                    "resolution": resolution,
                    "position": position,
                    "period_start_utc": start,
                    "curve_type": curve_type,
                })
    return rows