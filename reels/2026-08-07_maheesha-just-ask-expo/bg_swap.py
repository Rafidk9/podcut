"""One-off: put real city photos (assets/cities/{melbourne,sydney,adelaide}_plate.jpg
-- see that folder's CREDITS.txt) BEHIND Maheesha for segment 4 (P4, clip index 3),
snap-cutting between the three as she says each city name: "...at our Melbourne,
Sydney, and Adelaide offices."

Unlike bg_swap.py's usual one-image convention (Perth/Adelaide reels), this is
THREE images shown in rapid hard-cut succession while she stays continuously
matted on top -- the background visibly snaps city-to-city in under a second,
which is the point: it's the reel's one "text/image behind subject" standout
moment (per podcut/CLAUDE.md) but built for the "fast paced, energetic
transitions" brief rather than a single slow reveal. No crossfade between
images by design -- a hard cut here reads as a deliberate beat, not a glitch.

Timing is LOCAL to this segment's own clock (0 .. clip duration), matching
where insert_broll.py's wipes land relative to this reel's own cut points --
this segment carries no wipe of its own mid-segment, so there's no cut to
hide the swap under; the smooth fade in/out at the edges is what sells it
instead of a masked cut.

    ENTRANCE (fade 0->1): 8.05 - 8.25s
    MELBOURNE hold:       8.25 - 8.70s   (covers her saying "Melbourne," 8.24-8.62 local)
    SYDNEY hold:          8.70 - 9.10s   (covers "Sydney," 8.70-8.94 local)
    ADELAIDE hold:        9.10 - 9.65s   (covers "Adelaide" 9.10-9.56 local)
    EXIT (fade 1->0):     9.65 - 9.90s

Composite order per frame, while a photo is visible:
    original footage (her real surroundings) -> the photo (alpha-faded) ->
    her rembg cutout (u2net_human_seg) on top
so she genuinely stands in front of each city in turn. Frames where alpha is
0 skip matting entirely and are just re-saved (cheap).

FIX (added after first render): her forearm rests flat on a round wooden table
throughout this take, and in several frames there's no visible gap between her
sleeve and the tabletop -- u2net_human_seg (and isnet-general-use, tried as a
comparison) both fuse the table into her "person" blob as ONE connected region,
not a separate one, so connected-component filtering can't split them off and
neither can erosion (tested up to 30 iterations -- the contact area is wide,
not a thin bridge, so eroding enough to sever it also eats her actual silhouette
elsewhere). Fix instead: feather-clip the alpha mask to zero below 66% of frame
height (30px feather over a 1920-tall frame) -- her face/hands/gesture never
reach that low in this window, so it only ever removes the table, replacing it
with a clean fade into the city photo instead of the warped double-exposed
shape. Applied to all three cities for consistency, not just Melbourne (only
Melbourne was confirmed to need it, but it's a no-op where the mask is already
clean).

Overwrites work/segments/seg_03.mp4 in place -- run AFTER build_base.py and
BEFORE insert_broll.py:
    PODCUT_REEL=2026-08-07_maheesha-just-ask-expo \\
        python 2026-08-07_maheesha-just-ask-expo/bg_swap.py
Re-running build_base.py regenerates the segment and undoes this.
"""
import os
import shutil
import subprocess

import numpy as np
from PIL import Image
from rembg import new_session, remove

FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
REEL = os.path.dirname(os.path.abspath(__file__))
SEG = os.path.join(REEL, "work", "segments", "seg_03.mp4")
CITIES_DIR = os.path.join(REEL, "assets", "cities")
TMP = os.path.join(REEL, "work", "bg_swap_tmp")
FPS = 30

ENTRANCE_START = 8.05
MELBOURNE_START = 8.25
SYDNEY_START = 8.70
ADELAIDE_START = 9.10
EXIT_START = 9.65
EXIT_END = 9.90
ENTRANCE_DUR = MELBOURNE_START - ENTRANCE_START
EXIT_DUR = EXIT_END - EXIT_START


def _smoothstep(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def bg_alpha(t):
    """Blend strength (0..1) of whichever city photo is active at local time t."""
    if t < ENTRANCE_START:
        return 0.0
    if t < MELBOURNE_START:
        return _smoothstep((t - ENTRANCE_START) / ENTRANCE_DUR)
    if t < EXIT_START:
        return 1.0
    if t < EXIT_END:
        return 1.0 - _smoothstep((t - EXIT_START) / EXIT_DUR)
    return 0.0


def bg_image_for(t):
    """Which city plate is active at local time t (hard cuts, no crossfade --
    see module docstring). Returns None outside the window."""
    if t < ENTRANCE_START or t >= EXIT_END:
        return None
    if t < SYDNEY_START:
        return "melbourne_plate.jpg"
    if t < ADELAIDE_START:
        return "sydney_plate.jpg"
    return "adelaide_plate.jpg"


def clip_mask_below_table(cutout):
    """Feather the alpha channel to zero below 66% of frame height -- see the
    module docstring's FIX note. Her real content never reaches that low in
    this window; the round table she's resting on sometimes does, and gets
    fused into the person mask as one blob (not separable by connected-
    component filtering or erosion -- both were tried and failed)."""
    arr = np.array(cutout)
    h = arr.shape[0]
    cutoff = int(h * 0.66)
    feather = max(1, int(h * 0.0156))
    alpha = arr[:, :, 3].astype(np.float32)
    for y in range(cutoff, min(cutoff + feather, h)):
        alpha[y] *= 1.0 - (y - cutoff) / feather
    alpha[cutoff + feather:] = 0
    arr[:, :, 3] = alpha.astype(np.uint8)
    return Image.fromarray(arr)


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


def main():
    """RESUMABLE: this run's matting cost (55 frames through rembg) turned out
    to exceed the 10-minute ceiling a single tool call can budget, so unlike
    the original one-shot bg_swap.py convention, this version checkpoints at
    the frame level -- re-running the exact same command after a kill picks
    up where it left off instead of redoing already-composited frames. Only
    wipes TMP if it looks incomplete/foreign (no frames/ dir yet); once
    frames/ exists with the full frame count, extraction is skipped and the
    per-frame loop just skips any f_NNNNN.png that already exists in out/."""
    frames_dir = os.path.join(TMP, "frames")
    out_dir = os.path.join(TMP, "out")
    audio = os.path.join(TMP, "audio.aac")

    # A kill mid-extraction (rare -- extraction itself only takes ~1-2s, but
    # not impossible) would leave frames/ non-empty but short of the real
    # count; treat that the same as "not extracted yet" rather than silently
    # matting a truncated frame set.
    expected_frames = None
    if os.path.isdir(frames_dir) and os.listdir(frames_dir):
        probe = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries",
             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", SEG],
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

    bg_cache = {}
    session = new_session("u2net_human_seg") if todo else None
    matted = 0

    for i, fn in enumerate(frame_files):
        if fn in already:
            continue
        t = i / FPS
        src = Image.open(os.path.join(frames_dir, fn))
        alpha = bg_alpha(t)
        img_name = bg_image_for(t)
        if alpha > 0.001 and img_name is not None:
            if img_name not in bg_cache:
                bg_cache[img_name] = Image.open(
                    os.path.join(CITIES_DIR, img_name)).convert("RGB")
            base = src.convert("RGBA")
            cutout = clip_mask_below_table(remove(src, session=session))
            bg_frame = bg_cache[img_name].convert("RGBA")
            bg_frame.putalpha(round(alpha * 255))
            comp = Image.alpha_composite(base, bg_frame)
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
        # Non-fatal: SEG is already written by this point. A lingering file
        # handle (antivirus scan, etc.) on the temp dir shouldn't fail the
        # whole run -- just leave it for the next invocation's startup check
        # (frames/ already exists -> resumed-and-complete, out_dir already
        # full -> skips straight to re-encode) or manual cleanup.
        print(f"note: couldn't remove {TMP} ({e}) -- SEG was written fine, "
              f"safe to delete that folder manually")
    print("wrote", SEG)


if __name__ == "__main__":
    main()
