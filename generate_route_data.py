#!/usr/bin/env python3
"""Build a normalized route model from the GPX files in the repo.

This first prompt focuses on the route timeline itself: the files are not one
continuous line because some stages were skipped, so the output explicitly tracks
breaks between GPX segments instead of treating the route as a single smooth
track.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

GPX_NS = {"gpx": "http://www.topografix.com/GPX/1/1"}
ROOT = Path(__file__).resolve().parent
GPX_DIR = ROOT / "gpx"
OUT_PATH = ROOT / "route_data.json"


def parse_iso8601(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return radius_km * c


def parse_gpx_file(path: Path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"Failed to parse {path.name}: {exc}") from exc

    points = []
    for pt in root.findall(".//gpx:trkpt", GPX_NS):
        lat = float(pt.attrib.get("lat", "nan"))
        lon = float(pt.attrib.get("lon", "nan"))
        ts = pt.find("gpx:time", GPX_NS)
        if ts is None or math.isnan(lat) or math.isnan(lon):
            continue
        dt = parse_iso8601(ts.text)
        points.append({
            "lat": lat,
            "lon": lon,
            "time": dt.isoformat().replace("+00:00", "Z"),
            "timestamp_utc": dt.timestamp(),
        })

    if not points:
        return None

    total_distance_km = 0.0
    for previous, current in zip(points, points[1:]):
        total_distance_km += haversine_km(
            previous["lat"], previous["lon"], current["lat"], current["lon"]
        )

    return {
        "distance_km": round(total_distance_km, 2),
        "points": points,
    }


def main() -> None:
    files = sorted(GPX_DIR.glob("*.gpx"))
    tracks = []
    for path in files:
        parsed = parse_gpx_file(path)
        if parsed is not None:
            tracks.append(parsed)

    tracks.sort(key=lambda item: item["points"][0]["timestamp_utc"])

    total_points = sum(len(track["points"]) for track in tracks)

    route_model = {
        "tracks": [
            {
                "distance_km": track["distance_km"],
                "points": track["points"],
            }
            for track in tracks
        ],
    }

    OUT_PATH.write_text(json.dumps(route_model, indent=2), encoding="utf-8")

    print(f"Processed {len(tracks)} GPX files and {total_points} track points.")
    print(f"Output: {OUT_PATH}")


if __name__ == "__main__":
    main()
