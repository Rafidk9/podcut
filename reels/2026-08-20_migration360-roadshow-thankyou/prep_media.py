"""
prep_media.py

1. Converts every .HEIC/.heic file under input/perth/ to .jpg (quality 92,
   EXIF-orientation-corrected, RGB), using pillow-heif + PIL exactly as
   documented in work/heic_conversion_method.md. Skips files that already
   have a .jpg sibling. Originals are left in place.

2. Photo inventory: opens every JPG/JPEG (any case) under
   input/{perth,adelaide,brisbane,melbourne,tasmania}/ with PIL, records
   (width, height) and portrait/landscape orientation. No transforms.

3. Video inventory: for every .MOV/.mp4 (any case) under the 5 city folders
   plus input/gazi/, runs ffprobe to get duration, raw stream width/height,
   rotation (from side_data Display Matrix or the 'rotate' tag), and the
   effective displayed orientation once rotation is accounted for.

Writes work/media_inventory.json and prints a compact summary.
"""

import json
import subprocess
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input"
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)

PHOTO_CITIES = ["perth", "adelaide", "brisbane", "melbourne", "tasmania"]
VIDEO_CITIES = PHOTO_CITIES + ["gazi"]

FFPROBE = r"C:\Users\AU-0011-PFEC-G\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffprobe.exe"


# ---------------------------------------------------------------------------
# Step 1: HEIC -> JPG conversion (Perth only)
# ---------------------------------------------------------------------------

def convert_perth_heic():
    perth_dir = INPUT / "perth"
    heic_files = sorted(
        p for p in perth_dir.iterdir()
        if p.suffix.lower() == ".heic"
    )

    converted = []
    skipped = []
    failed = []

    for heic_path in heic_files:
        jpg_path = heic_path.with_suffix(".jpg")
        if jpg_path.exists():
            skipped.append(heic_path.name)
            continue
        try:
            img = Image.open(heic_path)
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(jpg_path, "JPEG", quality=92, exif=img.info.get("exif", b""))
            converted.append(heic_path.name)
        except Exception as e:
            failed.append((heic_path.name, str(e)))

    return converted, skipped, failed


# ---------------------------------------------------------------------------
# Step 2: Photo inventory
# ---------------------------------------------------------------------------

def gather_photos():
    photos = []
    failures = []

    for city in PHOTO_CITIES:
        city_dir = INPUT / city
        if not city_dir.exists():
            continue
        photo_paths = sorted(
            p for p in city_dir.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg")
        )
        for p in photo_paths:
            try:
                with Image.open(p) as img:
                    img.load()
                    width, height = img.size
                orientation = "landscape" if width >= height else "portrait"
                photos.append({
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "city": city,
                    "width": width,
                    "height": height,
                    "orientation": orientation,
                })
            except Exception as e:
                failures.append({
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "error": str(e),
                })

    return photos, failures


# ---------------------------------------------------------------------------
# Step 3: Video inventory (ffprobe)
# ---------------------------------------------------------------------------

def ffprobe_json(path):
    cmd = [
        FFPROBE,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return json.loads(result.stdout)


def extract_rotation_deg(video_stream):
    """
    Look for rotation info in:
      - stream 'tags' -> 'rotate'
      - side_data_list entries with side_data_type == 'Display Matrix'
        (has a 'rotation' field, degrees, can be negative)
    Returns an int rotation in degrees, normalized to one of
    0 / 90 / 180 / 270 (as a magnitude that flips width/height when
    90 or 270), or 0 if none found.
    """
    rotation = 0

    tags = video_stream.get("tags", {}) or {}
    if "rotate" in tags:
        try:
            rotation = int(tags["rotate"])
        except (TypeError, ValueError):
            rotation = 0

    for sd in video_stream.get("side_data_list", []) or []:
        if sd.get("side_data_type") == "Display Matrix" and "rotation" in sd:
            try:
                rotation = int(round(float(sd["rotation"])))
            except (TypeError, ValueError):
                pass

    # normalize to 0/90/180/270
    rotation = rotation % 360
    if rotation < 0:
        rotation += 360
    return rotation


def gather_videos():
    videos = []
    failures = []

    for city in VIDEO_CITIES:
        city_dir = INPUT / city
        if not city_dir.exists():
            continue
        vid_paths = sorted(
            p for p in city_dir.iterdir()
            if p.suffix.lower() in (".mov", ".mp4")
        )
        for p in vid_paths:
            try:
                data = ffprobe_json(p)
                video_stream = next(
                    (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                    None,
                )
                if video_stream is None:
                    raise RuntimeError("no video stream found")

                raw_width = video_stream.get("width")
                raw_height = video_stream.get("height")
                duration_sec = None
                if "duration" in video_stream:
                    duration_sec = float(video_stream["duration"])
                elif "duration" in data.get("format", {}):
                    duration_sec = float(data["format"]["duration"])

                rotation_deg = extract_rotation_deg(video_stream)

                # effective displayed dims after rotation
                if rotation_deg in (90, 270):
                    eff_width, eff_height = raw_height, raw_width
                else:
                    eff_width, eff_height = raw_width, raw_height

                effective_orientation = (
                    "landscape" if eff_width >= eff_height else "portrait"
                )

                videos.append({
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "city": city,
                    "duration_sec": round(duration_sec, 3) if duration_sec is not None else None,
                    "raw_width": raw_width,
                    "raw_height": raw_height,
                    "rotation_deg": rotation_deg,
                    "effective_width": eff_width,
                    "effective_height": eff_height,
                    "effective_orientation": effective_orientation,
                })
            except Exception as e:
                failures.append({
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "error": str(e),
                })

    return videos, failures


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    converted, skipped, heic_failed = convert_perth_heic()
    photos, photo_failures = gather_photos()
    videos, video_failures = gather_videos()

    inventory = {
        "photos": photos,
        "videos": videos,
        "failures": {
            "heic_conversion": [{"file": f, "error": e} for f, e in heic_failed],
            "photos": photo_failures,
            "videos": video_failures,
        },
    }

    out_path = WORK / "media_inventory.json"
    out_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    # ---------------- summary ----------------
    print("=== HEIC -> JPG (input/perth/) ===")
    print(f"Converted: {len(converted)}  Skipped (already existed): {len(skipped)}  Failed: {len(heic_failed)}")
    if converted:
        print("  Converted files:", ", ".join(converted))
    if skipped:
        print("  Skipped files:", ", ".join(skipped))
    if heic_failed:
        print("  FAILED:", ", ".join(f for f, _ in heic_failed))

    print("\n=== Photo inventory ===")
    by_city = {}
    for p in photos:
        c = by_city.setdefault(p["city"], {"total": 0, "portrait": 0, "landscape": 0})
        c["total"] += 1
        c[p["orientation"]] += 1
    for city in PHOTO_CITIES:
        c = by_city.get(city, {"total": 0, "portrait": 0, "landscape": 0})
        print(f"  {city}: {c['total']} photos ({c['portrait']} portrait, {c['landscape']} landscape)")
    print(f"  TOTAL: {len(photos)} photos")
    if photo_failures:
        print("  PHOTO FAILURES:", ", ".join(f["path"] for f in photo_failures))

    print("\n=== Video inventory ===")
    vby_city = {}
    for v in videos:
        c = vby_city.setdefault(v["city"], {"total": 0, "portrait": 0, "landscape": 0, "duration": 0.0})
        c["total"] += 1
        c[v["effective_orientation"]] += 1
        c["duration"] += v["duration_sec"] or 0.0
    for city in VIDEO_CITIES:
        c = vby_city.get(city, {"total": 0, "portrait": 0, "landscape": 0, "duration": 0.0})
        print(f"  {city}: {c['total']} videos, {c['duration']:.1f}s total "
              f"({c['portrait']} portrait, {c['landscape']} landscape)")
    total_dur = sum(v["duration_sec"] or 0.0 for v in videos)
    print(f"  TOTAL: {len(videos)} videos, {total_dur:.1f}s")
    if video_failures:
        print("  VIDEO FAILURES:", ", ".join(f["path"] for f in video_failures))

    print(f"\nInventory written to {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
