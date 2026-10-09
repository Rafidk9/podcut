"""Put a city plate BEHIND Maheesha for each of the five branches she names in
segment 4 (P4, clip index 3): "...at our Brisbane, Melbourne, Perth, Adelaide
and Sydney branches." Five hard cuts inside a single ~3.6s window, with her
matted continuously on top the whole time, so the world behind her snaps from
city to city while she never moves. This is the reel's one image-behind-subject
standout moment (podcut/CLAUDE.md) and the direct answer to the brief's "use
the welcome day images appropriately for each city" -- Melbourne, Sydney and
Adelaide are real PFEC Welcome Day photographs from the March 2026 cruise;
Brisbane and Perth, which have no Welcome Day photo library, fall back to
permissively-licensed river-and-skyline plates (assets/cities/CREDITS.txt).

Hard cuts, no crossfade: at ~0.6s per city a dissolve would smear two cities
together and read as a glitch. Only the entrance and the exit fade, so the
sequence arrives and leaves cleanly against the untouched footage either side.

Timing is LOCAL to this segment's own clock (0 .. clip duration). Derived from
the Sinhala word timings in work/P4.transcript.si.json minus clips.json's
k_start of 2.00s -- each city plate is up slightly BEFORE its branch is spoken
and holds until the next one:

    ENTRANCE (fade 0->1):  4.50 - 4.70s
    BRISBANE   4.70 - 5.28   ("brisbane"  spoken 4.72-5.20 local)
    MELBOURNE  5.28 - 5.90   ("melbourne" spoken 5.34-5.78)
    PERTH      5.90 - 6.38   ("perth"     spoken 5.96-6.36)
    ADELAIDE   6.38 - 7.05   ("adelaide"  spoken 6.44-6.92)
    SYDNEY     7.05 - 7.85   ("and sydney branches" spoken 7.00-7.86)
    EXIT (fade 1->0):      7.85 - 8.10s

Composite order per frame while a plate is visible:
    original footage -> the plate (alpha-faded) -> her rembg cutout on top.
Frames at alpha 0 skip matting entirely and are just re-saved (cheap).

She sits at a wooden table in this take with her hands clasped on it, which is
the same failure mode the Just Ask Expo reel hit: u2net_human_seg fuses a
tabletop her arms rest flat on into the person blob as ONE connected region, so
neither connected-component filtering nor erosion can separate it. Same fix --
feather the alpha to zero below TABLE_CUTOFF of frame height. The cutoff here is
set from this take's own framing (see check/seg03_*.jpg), low enough to keep her
clasped hands, which sit higher in frame than the Expo reel's.

Overwrites work/segments/seg_03.mp4 in place -- run AFTER build_base.py and
BEFORE insert_broll.py. Re-running build_base.py regenerates the segment and
undoes this. RESUMABLE at frame level: re-running the same command after a kill
picks up where it left off rather than re-matting finished frames.

    PODCUT_REEL=2026-09-02_maheesha-welcome-day-sinhala
        python 2026-09-02_maheesha-welcome-day-sinhala/bg_swap.py
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

ENTRANCE_START = 4.50
ENTRANCE_DUR = 0.20
EXIT_START = 7.85
EXIT_END = 8.10
EXIT_DUR = EXIT_END - EXIT_START
TABLE_CUTOFF = 0.73

# (plate becomes active at this local time, plate file). Last entry runs to EXIT_END.
CUTS = [
    (4.70, "brisbane_plate.jpg"),
    (5.28, "melbourne_plate.jpg"),
    (5.90, "perth_plate.jpg"),
    (6.38, "adelaide_plate.jpg"),
    (7.05, "sydney_plate.jpg"),
]


def _smoothstep(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def bg_alpha(t):
    """Blend strength (0..1) of whichever plate is active at local time t."""
    if t < ENTRANCE_START or t >= EXIT_END:
        return 0.0
    if t < ENTRANCE_START + ENTRANCE_DUR:
        return _smoothstep((t - ENTRANCE_START) / ENTRANCE_DUR)
    if t < EXIT_START:
        return 1.0
    return 1.0 - _smoothstep((t - EXIT_START) / EXIT_DUR)


def bg_image_for(t):
    """Which city plate is active at local time t (hard cuts, no crossfade)."""
    if t < ENTRANCE_START or t >= EXIT_END:
        return None
    active = CUTS[0][1]
    for start, name in CUTS:
        if t >= start:
            active = name
    return active


def clip_mask_below_table(cutout):
    """Feather the alpha to zero below TABLE_CUTOFF of frame height -- see the
    module docstring. Removes the tabletop that gets fused into her person mask
    without eating the clasped hands, which sit just above the cutoff."""
    arr = np.array(cutout)
    h = arr.shape[0]
    cutoff = int(h * TABLE_CUTOFF)
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
    incomplete = (expected_frames is not None
                  and len(os.listdir(frames_dir)) < expected_frames)

    if not os.path.isdir(frames_dir) or not os.listdir(frames_dir) or incomplete:
        if os.path.exists(TMP):
            shutil.rmtree(TMP)
        os.makedirs(frames_dir)
        os.makedirs(out_dir)
        run(["-i", SEG, "-vn", "-c:a", "copy", audio])
        run(["-i", SEG, os.path.join(frames_dir, "f_%05d.png")])
    else:
        os.makedirs(out_dir, exist_ok=True)
        print("resuming: frames/ already extracted")

    frame_files = sorted(os.listdir(frames_dir))
    already = set(os.listdir(out_dir))
    todo = [fn for fn in frame_files if fn not in already]
    print(f"{len(frame_files)} frames, {len(already)} done, {len(todo)} to go")

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
        if (i + 1) % 25 == 0 or i + 1 == len(frame_files):
            print(f"  {i + 1}/{len(frame_files)} ({matted} matted)")

    if len(os.listdir(out_dir)) < len(frame_files):
        print("still incomplete -- re-run to continue")
        return

    composited = os.path.join(TMP, "composited.mp4")
    run(["-framerate", "30", "-i", os.path.join(out_dir, "f_%05d.png"),
         "-i", audio, "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-color_range", "tv",
         "-c:a", "aac", "-ar", "48000", "-ac", "2",
         "-video_track_timescale", "90000", composited])
    shutil.copyfile(composited, SEG)
    print(f"seg_03.mp4 replaced ({matted} frames matted this run)")


if __name__ == "__main__":
    main()
