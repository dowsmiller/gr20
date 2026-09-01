#!/usr/bin/env python3
"""Build a media dataset for the GR20 route map.

This stage focuses on the map overlay behavior rather than the full browser UI:
- pair Live Photo still/video files
- determine route position from nearest GPX timestamp when no EXIF location exists
- drop items that are not close enough to the route in time to keep the map honest
"""

from __future__ import annotations

import bisect
from concurrent.futures import ThreadPoolExecutor
import json
import re
import subprocess
import imageio_ffmpeg
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PHOTOS_DIR = ROOT / "photos"
PREVIEW_DIR = PHOTOS_DIR / "previews"
ROUTE_DATA_PATH = ROOT / "route_data.json"
OUT_PATH = ROOT / "media_data.json"

VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS
CORSICA_TIMEZONE = ZoneInfo("Europe/Paris")
PREVIEW_SIZES = {"preview": 160, "expanded_preview": 480}


def load_route_points() -> list[dict]:
    data = json.loads(ROUTE_DATA_PATH.read_text(encoding="utf-8"))
    return [point for track in data.get("tracks", []) for point in track["points"]]


def parse_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def build_preview_cache(path: Path) -> dict[str, str]:
    PREVIEW_DIR.mkdir(exist_ok=True)
    previews = {}
    dimensions = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    width_match = re.search(r"pixelWidth:\s+(\d+)", dimensions)
    height_match = re.search(r"pixelHeight:\s+(\d+)", dimensions)
    if not width_match or not height_match:
        return previews
    is_portrait = int(width_match.group(1)) <= int(height_match.group(1))
    for field, size in PREVIEW_SIZES.items():
        output_path = PREVIEW_DIR / f"{path.stem}-{size}-square.jpg"
        if not output_path.exists() or output_path.stat().st_mtime < path.stat().st_mtime:
            scaled_path = PREVIEW_DIR / f".{path.stem}-{size}-scaled.jpg"
            subprocess.run(
                ["sips", "--resampleWidth" if is_portrait else "--resampleHeight", str(size), str(path), "--out", str(scaled_path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "75", "--cropToHeightWidth", str(size), str(size), str(scaled_path), "--out", str(output_path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            scaled_path.unlink(missing_ok=True)
        if output_path.exists():
            previews[field] = f"photos/previews/{output_path.name}"
    return previews


def build_video_cache(path: Path) -> str | None:
    PREVIEW_DIR.mkdir(exist_ok=True)
    output_path = PREVIEW_DIR / f"{path.stem}-video-h264.mp4"
    if not output_path.exists() or output_path.stat().st_mtime < path.stat().st_mtime:
        subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-y",
                "-i", str(path),
                "-c:v", "libx264",
                "-vf", "scale=-2:720",
                "-crf", "25",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-movflags", "+faststart",
                str(output_path),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return f"photos/previews/{output_path.name}" if output_path.exists() else None


def image_capture_timestamp(path: Path) -> float | None:
    if path.suffix.lower() not in IMAGE_EXTS:
        return None
    result = subprocess.run(
        ["sips", "-g", "creation", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"creation:\s+(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2})", result.stdout)
    if not match:
        return None
    capture_time = datetime.strptime(match.group(1), "%Y:%m:%d %H:%M:%S")
    return capture_time.replace(tzinfo=CORSICA_TIMEZONE).timestamp()


def location_for_timestamp(route_points: list[dict], timestamps: list[float], media_epoch: float) -> dict:
    index = bisect.bisect_left(timestamps, media_epoch)
    if index == 0 or index == len(route_points):
        return min(route_points, key=lambda point: abs(point["timestamp_utc"] - media_epoch))

    previous = route_points[index - 1]
    following = route_points[index]
    interval_seconds = following["timestamp_utc"] - previous["timestamp_utc"]
    if interval_seconds <= 0 or interval_seconds > 15 * 60:
        return min((previous, following), key=lambda point: abs(point["timestamp_utc"] - media_epoch))

    progress = (media_epoch - previous["timestamp_utc"]) / interval_seconds
    return {
        "lat": previous["lat"] + (following["lat"] - previous["lat"]) * progress,
        "lon": previous["lon"] + (following["lon"] - previous["lon"]) * progress,
        "time": datetime.fromtimestamp(media_epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "timestamp_utc": media_epoch,
    }


def pair_media_files(files: list[Path]) -> list[dict]:
    by_stem: dict[str, list[Path]] = {}
    for path in files:
        if path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        by_stem.setdefault(path.stem, []).append(path)

    entries: list[dict] = []
    for stem, items in sorted(by_stem.items()):
        images = sorted([p for p in items if p.suffix.lower() in IMAGE_EXTS], key=lambda p: p.name.lower())
        videos = sorted([p for p in items if p.suffix.lower() in VIDEO_EXTS], key=lambda p: p.name.lower())

        if images and videos:
            primary = images[0]
            video = videos[0]
            entries.append({
                "kind": "live_photo",
                "stem": stem,
                "image": primary.name,
                "video": video.name,
                "image_path": primary.as_posix(),
                "video_path": video.as_posix(),
                **build_preview_cache(primary),
            })
        elif images:
            primary = images[0]
            entries.append({
                "kind": "photo",
                "stem": stem,
                "image": primary.name,
                "image_path": primary.as_posix(),
                **build_preview_cache(primary),
            })
        elif videos:
            entries.append({
                "kind": "video",
                "stem": stem,
                "video": videos[0].name,
                "video_path": videos[0].as_posix(),
            })
    return entries


def attach_to_route(entries: list[dict], route_points: list[dict]) -> list[dict]:
    assigned = []
    route_timestamps = [point["timestamp_utc"] for point in route_points]
    for entry in entries:
        # prefer the earliest timestamp for the files involved
        candidate_times = []
        for key in ("image_path", "video_path"):
            value = entry.get(key)
            if not value:
                continue
            path = ROOT / value
            if path.exists():
                candidate_times.append(image_capture_timestamp(path) or path.stat().st_mtime)
        if not candidate_times:
            continue
        media_epoch = min(candidate_times)
        matched_point = min(route_points, key=lambda point: abs(point["timestamp_utc"] - media_epoch))
        location = location_for_timestamp(route_points, route_timestamps, media_epoch)
        if matched_point is None:
            continue
        nearest_ts = parse_timestamp(matched_point["time"])
        if nearest_ts is None:
            continue
        time_gap_seconds = abs(media_epoch - nearest_ts)
        if time_gap_seconds > 2 * 60 * 60:
            continue

        payload = {
            "id": entry["stem"],
            "kind": entry["kind"],
            "filename": entry.get("image") or entry.get("video") or entry["stem"],
            "time": datetime.fromtimestamp(media_epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "lat": location["lat"],
            "lon": location["lon"],
            "route_time": matched_point["time"],
            "route_distance_seconds": int(time_gap_seconds),
        }
        for key in ("image", "video"):
            if key in entry:
                payload[key] = entry[key]

        for key in ("preview", "expanded_preview", "preview_video"):
            if entry.get(key):
                payload[key] = entry[key]

        if "image_path" in entry:
            image_path = entry["image_path"]
            payload["image_path"] = image_path.replace(str(ROOT / "photos"), "photos") if str(ROOT / "photos") in image_path else image_path
        if "video_path" in entry:
            video_path = entry["video_path"]
            payload["video_path"] = video_path.replace(str(ROOT / "photos"), "photos") if str(ROOT / "photos") in video_path else video_path
        assigned.append(payload)

    return sorted(assigned, key=lambda item: item["time"])


def prune_preview_cache(media_items: list[dict]) -> None:
    referenced = {
        item[key]
        for item in media_items
        for key in ("preview", "expanded_preview", "preview_video")
        if item.get(key)
    }
    for path in PREVIEW_DIR.iterdir():
        if path.is_file() and f"photos/previews/{path.name}" not in referenced:
            path.unlink()


def main() -> None:
    files = sorted(PHOTOS_DIR.iterdir())
    media_entries = pair_media_files(files)
    video_paths = {
        ROOT / entry["video_path"]
        for entry in media_entries
        if entry.get("video_path")
    }
    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(build_video_cache, video_paths))
    for entry in media_entries:
        video_path = entry.get("video_path")
        if video_path:
            entry["preview_video"] = build_video_cache(ROOT / video_path)
    route_points = load_route_points()
    media_items = attach_to_route(media_entries, route_points)
    prune_preview_cache(media_items)

    OUT_PATH.write_text(json.dumps(media_items, indent=2), encoding="utf-8")
    print(f"Paired {len(media_entries)} media groups -> {len(media_items)} route-attached media items")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
