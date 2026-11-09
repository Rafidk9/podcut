"""Put Flinders Street Station (assets/cities/flinders_plate.jpg -- see that
folder's CREDITS.txt) BEHIND Tushar for segment index 2 (seg_02.mp4), on the
one line in the whole script that names his city:

    "...I'll be running a migration seminar AT OUR MELBOURNE OFFICE."

This is the reel's single "image behind subject" standout moment (per
podcut/CLAUDE.md -- reserve it for 1-2 beats, the matting pass is expensive).
Unlike the 2026-08-07 reel's three-city hard-cut version, this is ONE image
with a smooth fade in and out: there's only one city in this script, so a
snap-cut would be punctuating nothing. The fade is what sells it here, since
this segment carries no wipe of its own mid-segment to hide a cut under.

PLATE CHANGED (2026-08-11): was melbourne_plate.jpg, the CC BY Melbourne
CBD/Yarra skyline panorama carried over from the 2026-08-07 reel; now the CC0
Flinders Street Station photo. Nothing about the timing or compositing below
changed -- only the image file -- but note the plate is only on screen for
about 1.2s, which is why a single instantly-legible landmark beats a general
skyline here. See CREDITS.txt for the crop reasoning.

Timing is LOCAL to this segment's own clock (0 .. 7.60s), i.e. raw IMG_8066
time minus clips.json's keep start of 1.85s:

    ENTRANCE (fade 0->1): 6.30 - 6.55s
    FLINDERS ST hold:     6.55 - 7.25s   (covers "Melbourne" 6.57-6.85 local
                                          and "office" 6.91-7.33 local)
    EXIT (fade 1->0):     7.25 - 7.50s
    (segment ends 7.60s -- exit completes with 0.10s of clean footage to spare,
     so the skyline is fully gone before insert_broll.py's wipe at the cut)

Deliberately clear of the other two things happening in this segment:
  - the punch zoom (content.json zoom.hits clip 2) fires at local 0.43-1.49
  - the Just Ask Expo poster card clears frame around local 4.3

No mask clipping needed here (contrast with the 2026-08-07 reel, which had to
feather the alpha to zero below 66% frame height because the presenter's
forearm rested on a table and u2net_human_seg fused the tabletop into her
person blob as one inseparable region). Tushar is standing free of any
surface in this take -- verified on check/melb_moment.jpg -- so the raw
u2net_human_seg cutout is used as-is.

Composite order per frame, while the photo is visible:
    original footage (his real atrium surroundings) -> the skyline photo
    (alpha-faded) -> his rembg cutout on top
so he genuinely stands in front of the Melbourne skyline. Frames where alpha
is 0 skip matting entirely and are just re-saved (cheap) -- only ~36 of the
228 frames in this segment ever go through rembg.

Overwrites work/segments/seg_02.mp4 in place -- run AFTER build_base.py and
BEFORE insert_broll.py:
    PODCUT_REEL=2026-08-11_tushar-melbourne-expo \\
        python 2026-08-11_tushar-melbourne-expo/bg_swap_melbourne.py
Re-running build_base.py regenerates the segment and undoes this.

RESUMABLE at the frame level (same convention as the 2026-08-07 script): a
kill mid-run is picked up by re-issuing the exact same command -- already
composited frames in out/ are skipped rather than redone.
"""
import os
import shutil
import subprocess

from PIL import Image
from rembg import new_session, remove

FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
REEL = os.path.dirname(os.path.abspath(__file__))
SEG = os.path.join(REEL, "work", "segments", "seg_02.mp4")
PLATE = os.path.join(REEL, "assets", "cities", "flinders_plate.jpg")
TMP = os.path.join(REEL, "work", "bg_swap_tmp")
FPS = 30

ENTRANCE_START = 6.30
HOLD_START = 6.55
EXIT_START = 7.25
EXIT_END = 7.50
ENTRANCE_DUR = HOLD_START - ENTRANCE_START
EXIT_DUR = EXIT_END - EXIT_START


def _smoothstep(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def bg_alpha(t):
    """Blend strength (0..1) of the skyline plate at local segment time t."""
    if t < ENTRANCE_START:
        return 0.0
    if t < HOLD_START:
        return _smoothstep((t - ENTRANCE_START) / ENTRANCE_DUR)
    if t < EXIT_START:
        return 1.0
    if t < EXIT_END:
        return 1.0 - _smoothstep((t - EXIT_START) / EXIT_DUR)
    return 0.0


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


def main():
    frames_dir = os.path.join(TMP, "frames")
    out_dir = os.path.join(TMP, "out")
    audio = os.path.join(TMP, "audio.aac")

    # A kill mid-extraction would leave frames/ non-empty but short of the real
    # count; treat that the same as "not extracted yet" rather than silently
    # matting a truncated frame set.
    expected_frames = None
    if os.path.isdir(frames_dir) and os.listdir(frames_dir):
        probe = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", SEG],
            capture_output=True, text=True)
        try:
            expected_frames = round(float(probe.stdout.strip()) * FPS)
        except ValueError:
            expected_frames = None

    frames_incomplete = (expected_frames is not None
                         and len(os.listdir(frames_dir)) < expected_frames)

    if not os.path.isdir(frames_dir) or not os.listdir(frames_dir) or frames_incomplete:
        if os.path.exists(TMP):
            shutil.rmtree(TMP)
        os.makedirs(frames_dir)
        os.makedirs(out_dir)
        run(["-i", SEG, "-vn", "-c:a", "copy", audio])
        run(["-i", SEG, os.path.join(frames_dir, "f_%05d.png")])
    else:
        os.makedirs(out_dir, exist_ok=True)
        print("resuming: frames/ already extracted, skipping ffmpeg extract")

    frame_files = sorted(os.listdir(frames_dir))
    print(f"{len(frame_files)} frames total")

    already = set(os.listdir(out_dir))
    todo = [fn for fn in frame_files if fn not in already]
    print(f"  {len(already)} already composited, {len(todo)} remaining this run")

    plate = None
    session = None
    matted = 0

    for i, fn in enumerate(frame_files):
        if fn in already:
            continue
        t = i / FPS
        src = Image.open(os.path.join(frames_dir, fn))
        alpha = bg_alpha(t)
        if alpha > 0.001:
            if plate is None:
                plate = Image.open(PLATE).convert("RGB").resize(src.size)
            if session is None:
                session = new_session("u2net_human_seg")
            base = src.convert("RGBA")
            cutout = remove(src, session=session)
            bg_frame = plate.convert("RGBA")
            bg_frame.putalpha(round(alpha * 255))
            comp = Image.alpha_composite(base, bg_frame)
            comp = Image.alpha_composite(comp, cutout)
            matted += 1
        else:
            comp = src.convert("RGBA")
        comp.convert("RGB").save(os.path.join(out_dir, fn))
        if (i + 1) % 30 == 0 or i + 1 == len(frame_files):
            print(f"  {i + 1}/{len(frame_files)} ({matted} matted this run)")

    if len(os.listdir(out_dir)) < len(frame_files):
        print("still incomplete -- re-run this same command to continue")
        return

    composited = os.path.join(TMP, "composited.mp4")
    run(["-framerate", "30", "-i", os.path.join(out_dir, "f_%05d.png"),
         "-i", audio, "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-color_range", "tv",
         "-c:a", "aac", "-ar", "48000", "-ac", "2",
         "-video_track_timescale", "90000", composited])

    shutil.copy2(composited, SEG)
    try:
        shutil.rmtree(TMP)
    except OSError as e:
        # Non-fatal: SEG is already written by this point. A lingering file
        # handle (antivirus scan, etc.) shouldn't fail the whole run.
        print(f"note: couldn't remove {TMP} ({e}) -- SEG was written fine, "
              f"safe to delete that folder manually")
    print("wrote", SEG)


if __name__ == "__main__":
    main()
