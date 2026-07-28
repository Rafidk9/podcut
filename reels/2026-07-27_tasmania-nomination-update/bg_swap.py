"""One-off: layer a real Cradle Mountain photo (assets/tasmania/
cradle_mountain_bg.jpg, freely-licensed -- see that folder's CREDITS.txt)
behind Ali for segment 2 ("Tasmania has also confirmed that the state
nomination program will reopen...") -- a full opaque photo replacing his
real office for this one moment, not a small transparent card floating over
it (unlike the precedent this is adapted from, see an earlier reel's
bg_swap.py) -- the point here is "picture yourself in Tasmania", not a
graphic overlay. The SAME photo is what broll_plan.json's broll_cradle
stinger cuts to at the start of this same segment, so the sequence reads as
the cutaway "revealing" the location and then he appears to be standing in
front of it, rather than two unrelated visuals.

Composite order per frame (when the photo is visible): original footage's
own audio/timing preserved -> the photo (opacity fades in/out, see
bg_alpha()) -> person cutout (rembg, u2net_human_seg) on top, so he's
genuinely in front of it. Frames where the photo is fully transparent skip
matting entirely (just re-save the original frame) -- saves real processing
time since the photo is only visible for part of this segment, not all of
it. Reassembled with the segment's original audio. Overwrites
work/segments/seg_02.mp4 in place -- run AFTER build_base.py, BEFORE
insert_broll.py.

Animation timing is in this segment's own local seconds. broll_plan.json's
broll_cradle (1.5s) gets spliced over this segment's first 1.5s later in
insert_broll.py, so BROLL_HANDOFF matches that exactly -- the photo fade-in
starts the instant real footage takes over from the cutaway, continuing the
same view rather than a jarring re-reveal. The fade-out completes well
before this segment's own end (6.24s local) so the hard cut into segment 3
lands on his real, unmodified office both sides -- invisible as a cut."""
import os
import shutil
import subprocess

import numpy as np
from PIL import Image
from rembg import new_session, remove

FF = shutil.which("ffmpeg") or "ffmpeg"
REEL = os.path.dirname(os.path.abspath(__file__))
SEG = os.path.join(REEL, "work", "segments", "seg_02.mp4")
BG = os.path.join(REEL, "assets", "tasmania", "cradle_mountain_bg.jpg")
TMP = os.path.join(REEL, "work", "bg_swap_tmp")
FPS = 30

BROLL_HANDOFF = 1.5     # local seconds -- matches broll_plan.json's broll_dur
ENTRANCE_DUR = 0.45
HOLD_UNTIL = 5.55       # start fading back to his real office well before this
                        # segment's own local end (6.24s) -- see module docstring
EXIT_DUR = 0.5
ZOOM_START = 1.0
ZOOM_END = 1.10         # slow Ken Burns push across the whole visible window


def _smoothstep(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def bg_alpha(t):
    """Blend strength (0..1) of the Tasmania photo over his real office at
    local time t: fades in right as broll_cradle hands off, holds, fades
    back out before this segment (and this reel's only bg-swap moment) ends."""
    if t < BROLL_HANDOFF:
        return 0.0
    if t < BROLL_HANDOFF + ENTRANCE_DUR:
        return _smoothstep((t - BROLL_HANDOFF) / ENTRANCE_DUR)
    if t < HOLD_UNTIL:
        return 1.0
    if t < HOLD_UNTIL + EXIT_DUR:
        return 1.0 - _smoothstep((t - HOLD_UNTIL) / EXIT_DUR)
    return 0.0


def zoomed_bg(bg_img, t):
    """Slow Ken Burns push on the photo itself while it's visible -- purely
    cosmetic (alpha==0 frames never call this), keyed off the SAME clock as
    bg_alpha so the zoom always lines up with the fade."""
    span = max(0.01, (HOLD_UNTIL + EXIT_DUR) - BROLL_HANDOFF)
    p = _smoothstep(max(0.0, min(1.0, (t - BROLL_HANDOFF) / span)))
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
