"""One-off: put a real Adelaide riverbank photo (assets/adelaide/adl_plate.jpg,
CC BY 2.0 -- see that folder's CREDITS.txt) BEHIND Kapil for segment 4, the
line "your time here in South Australia can set you up for your migration
journey".

This is the reel's single behind-subject moment, deliberately reserved for the
aspirational payoff rather than sprinkled across beats (see podcut/CLAUDE.md:
the matting pass costs roughly 1-2 min per few seconds, and using it
everywhere dilutes it). The line is the "picture yourself here" beat, so the
real place replacing his actual background IS the argument -- especially
because the takes were shot on a riverbank in another city, not in Adelaide.

Composite order per frame, while the photo is visible:
    original footage (his real surroundings) -> the photo (alpha-faded) ->
    his rembg cutout (u2net_human_seg) on top
so he genuinely stands in front of it. Frames where the photo is fully
transparent skip matting entirely and are just re-saved, which is most of the
saving here.

Timing is in this segment's own local seconds (0 .. 3.48). The plate is
already at full strength at local 0 because insert_broll.py lays the 0.5s
"iris" wipe across this segment's opening cut -- so the iris OPENS onto him
already standing in Adelaide, which reads as a reveal instead of the
background visibly dissolving underneath him. It fades back to his real
surroundings before the segment ends, so the hard cut into segment 5 has real
footage on both sides and stays invisible as a cut.

Overwrites work/segments/seg_04.mp4 in place -- run AFTER build_base.py and
BEFORE insert_broll.py:
    PODCUT_REEL=2026-07-28_kapil-adelaide \\
        python 2026-07-28_kapil-adelaide/bg_swap.py
Re-running build_base.py regenerates the segment and undoes this, so it must
be re-run after any base rebuild.
"""
import os
import shutil
import subprocess

from PIL import Image
from rembg import new_session, remove

FF = shutil.which("ffmpeg") or "ffmpeg"
REEL = os.path.dirname(os.path.abspath(__file__))
SEG = os.path.join(REEL, "work", "segments", "seg_04.mp4")
BG = os.path.join(REEL, "assets", "adelaide", "adl_plate.jpg")
TMP = os.path.join(REEL, "work", "bg_swap_tmp")
FPS = 30

ENTRANCE_DUR = 0.28     # covered by the iris wipe sitting across this cut
HOLD_UNTIL = 2.80       # segment is 3.48s local; leave room to land on reality
EXIT_DUR = 0.50
ZOOM_START = 1.00
ZOOM_END = 1.09         # slow Ken Burns push across the visible window


def _smoothstep(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def bg_alpha(t):
    """Blend strength (0..1) of the Adelaide photo over his real background at
    local time t: snaps up under the iris wipe, holds, then fades back out
    before the segment ends."""
    if t < ENTRANCE_DUR:
        return _smoothstep(t / ENTRANCE_DUR)
    if t < HOLD_UNTIL:
        return 1.0
    if t < HOLD_UNTIL + EXIT_DUR:
        return 1.0 - _smoothstep((t - HOLD_UNTIL) / EXIT_DUR)
    return 0.0


def zoomed_bg(bg_img, t):
    """Slow Ken Burns push on the photo while it's visible -- keyed off the
    SAME clock as bg_alpha so the move always lines up with the fade.
    (alpha==0 frames never call this.)"""
    span = max(0.01, HOLD_UNTIL + EXIT_DUR)
    p = _smoothstep(max(0.0, min(1.0, t / span)))
    zoom = ZOOM_START + (ZOOM_END - ZOOM_START) * p
    w, h = bg_img.size
    nw, nh = round(w * zoom), round(h * zoom)
    resized = bg_img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return resized.crop((left, top, left + w, top + h))


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    frames_dir = os.path.join(TMP, "frames")
    out_dir = os.path.join(TMP, "out")
    os.makedirs(frames_dir)
    os.makedirs(out_dir)

    audio = os.path.join(TMP, "audio.aac")
    run(["-i", SEG, "-vn", "-c:a", "copy", audio])
    run(["-i", SEG, os.path.join(frames_dir, "f_%05d.png")])

    frame_files = sorted(os.listdir(frames_dir))
    print(f"{len(frame_files)} frames total")

    bg_img = Image.open(BG).convert("RGB")
    session = new_session("u2net_human_seg")
    matted = 0

    for i, fn in enumerate(frame_files):
        t = i / FPS
        src = Image.open(os.path.join(frames_dir, fn))
        alpha = bg_alpha(t)
        if alpha > 0.001:
            base = src.convert("RGBA")
            cutout = remove(src, session=session)
            bg_frame = zoomed_bg(bg_img, t).convert("RGBA")
            bg_frame.putalpha(round(alpha * 255))
            comp = Image.alpha_composite(base, bg_frame)
            comp = Image.alpha_composite(comp, cutout)
            matted += 1
        else:
            comp = src.convert("RGBA")
        comp.convert("RGB").save(os.path.join(out_dir, fn))
        if (i + 1) % 20 == 0 or i + 1 == len(frame_files):
            print(f"  {i + 1}/{len(frame_files)} ({matted} matted so far)")

    composited = os.path.join(TMP, "composited.mp4")
    run(["-framerate", "30", "-i", os.path.join(out_dir, "f_%05d.png"),
         "-i", audio, "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-color_range", "tv",
         "-c:a", "aac", "-ar", "48000", "-ac", "2",
         "-video_track_timescale", "90000", composited])

    shutil.copy2(composited, SEG)
    shutil.rmtree(TMP)
    print("wrote", SEG)


if __name__ == "__main__":
    main()
