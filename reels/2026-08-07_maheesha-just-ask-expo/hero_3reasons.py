"""One-off: put a giant text-behind-subject "3" (wrapping around her head/
torso, per user request) + a smaller "REASONS" reading vertically on the
right, BEHIND Maheesha for segment 1 (P1, clip index 0) -- the reel's
opening "Three reasons you need to be at the Just Ask Expo" line. Replaces
the plain "THREE" / "REASONS" 2-word caption cards that used to show here
(suppressed via content.json's silent hero_words entry -- see
build_captions.py's `silent` flag).

Composite order per frame, while the plate is visible:
    original footage (her real surroundings) -> the "3"+"REASONS" plate
    (alpha-faded) -> her rembg cutout (u2net_human_seg) on top
so she genuinely stands in front of it, the giant "3"'s two lobes visible
on either side of her head/torso.

Timing is LOCAL to this segment's own clock (0 .. clip duration, P1 keep
range 2.0-5.7 -> segment is 3.7s):
    ENTRANCE (fade 0->1): 0.15 - 0.35s
    HOLD:                 0.35 - 1.90s   (covers "Three" 0.32-0.54 and
                                           "reasons" 0.58-1.06 local, plus
                                           a beat of readability after)
    EXIT (fade 1->0):     1.90 - 2.15s
well clear of the P1->P3 cut at 3.7s, so the wipe there lands on plain
footage same as always.

Overwrites work/segments/seg_00.mp4 in place -- run AFTER build_base.py and
BEFORE insert_broll.py (same convention as bg_swap.py, and both must run
before insert_broll -- order between the two scripts doesn't matter, they
touch different segments):
    PODCUT_REEL=2026-08-07_maheesha-just-ask-expo \\
        python 2026-08-07_maheesha-just-ask-expo/hero_3reasons.py
Re-running build_base.py regenerates the segment and undoes this.
"""
import os
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rembg import new_session, remove

FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
REEL = os.path.dirname(os.path.abspath(__file__))
SEG = os.path.join(REEL, "work", "segments", "seg_00.mp4")
FONT = os.path.join(REEL, "assets", "fonts", "Poppins-Black.ttf")
FONT_ITALIC = os.path.join(REEL, "assets", "fonts", "Poppins-BlackItalic.ttf")
TMP = os.path.join(REEL, "work", "hero3_tmp")
FPS = 30
W, H = 1080, 1920

ENTRANCE_START = 0.15
HOLD_START = 0.35
EXIT_START = 1.90
EXIT_END = 2.15
ENTRANCE_DUR = HOLD_START - ENTRANCE_START
EXIT_DUR = EXIT_END - EXIT_START

GOLD = (255, 197, 0, 255)      # brand #FFC500
NAVY = (16, 7, 150, 255)       # brand #100796


def _smoothstep(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def plate_alpha(t):
    if t < ENTRANCE_START:
        return 0.0
    if t < HOLD_START:
        return _smoothstep((t - ENTRANCE_START) / ENTRANCE_DUR)
    if t < EXIT_START:
        return 1.0
    if t < EXIT_END:
        return 1.0 - _smoothstep((t - EXIT_START) / EXIT_DUR)
    return 0.0


def build_plate():
    """The '3' + rotated 'REASONS' graphic. Per user feedback on the first
    cut (2026-08-07): the original 1300pt upright '3' at (60, -144) read as
    too big and crowded the frame edges -- shrunk to 1000pt, switched to
    Poppins Black Italic, and moved to (20, 75), verified against
    check/test_3reasons_v2.jpg + check/test_full_composite_v2.jpg (textbbox
    at these settings: (15, 373, 640, 1137) -- comfortably inside the
    1080x1920 canvas with real margin on every side, and well clear of
    REASONS' left edge at x=860)."""
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)

    font3 = ImageFont.truetype(FONT_ITALIC, 1000)
    d.text((20, 75), "3", font=font3, fill=GOLD, stroke_width=5, stroke_fill=NAVY)

    font_r = ImageFont.truetype(FONT, 150)
    rtxt = Image.new("RGBA", (900, 220), (0, 0, 0, 0))
    dr = ImageDraw.Draw(rtxt)
    dr.text((10, 10), "REASONS", font=font_r, fill=(255, 255, 255, 255),
             stroke_width=4, stroke_fill=NAVY)
    rtxt_rot = rtxt.rotate(-90, expand=True)
    canvas.alpha_composite(rtxt_rot, (860, 480))
    return canvas


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


def main():
    frames_dir = os.path.join(TMP, "frames")
    out_dir = os.path.join(TMP, "out")
    audio = os.path.join(TMP, "audio.aac")

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

    plate = build_plate() if todo else None
    session = new_session("u2net_human_seg") if todo else None
    matted = 0

    for i, fn in enumerate(frame_files):
        if fn in already:
            continue
        t = i / FPS
        src = Image.open(os.path.join(frames_dir, fn))
        alpha = plate_alpha(t)
        if alpha > 0.001:
            base = src.convert("RGBA")
            cutout = remove(src, session=session)
            plate_frame = plate.copy()
            a = np.array(plate_frame.getchannel("A")).astype(np.float32) * alpha
            plate_frame.putalpha(Image.fromarray(a.astype(np.uint8)))
            comp = Image.alpha_composite(base, plate_frame)
            comp = Image.alpha_composite(comp, cutout)
            matted += 1
        else:
            comp = src.convert("RGBA")
        comp.convert("RGB").save(os.path.join(out_dir, fn))
        if (i + 1) % 20 == 0 or i + 1 == len(frame_files):
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
        print(f"note: couldn't remove {TMP} ({e}) -- SEG was written fine, "
              f"safe to delete that folder manually")
    print("wrote", SEG)


if __name__ == "__main__":
    main()
