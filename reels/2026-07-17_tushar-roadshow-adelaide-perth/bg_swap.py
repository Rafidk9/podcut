"""One-off: layer the campaign logo graphic (assets/bg_360.png, transparent
except the actual text/artwork -- white keyed out) behind Tushar for the P4
("...bringing the Migration360 Roadshow to your city...") clip, per the
user's request -- a big graphic behind him, but the REAL room/background
must stay visible (not replaced by a flat white canvas -- that read as fake).
Composite order per frame: original footage (real background) -> transparent
logo layer (animated -- see ENTRANCE/SHIMMER below) -> person cutout (rembg,
u2net_human_seg) on top, so he's genuinely in front of both. Reassembled with
the clip's original audio. Overwrites work/segments/seg_03.mp4 in place --
run AFTER build_base.py, BEFORE insert_broll.py.

Animation timing is in this CLIP's own local seconds, but broll_2 (1.1s,
per broll_plan.json) gets spliced over this clip's first 1.1s later in
insert_broll.py -- so the entrance is timed to start AT that handoff (not at
local t=0, which the viewer never actually sees), landing right as the wipe
reveals the real footage."""
import os, shutil, subprocess, sys
import numpy as np
from rembg import remove, new_session
from PIL import Image

FF = shutil.which("ffmpeg") or "ffmpeg"
REEL = os.path.dirname(os.path.abspath(__file__))
SEG = os.path.join(REEL, "work", "segments", "seg_03.mp4")
BG = os.path.join(REEL, "assets", "bg_360.png")
TMP = os.path.join(REEL, "work", "bg_swap_tmp")
FPS = 30

BROLL_HANDOFF = 1.1     # local seconds -- when broll_2 ends and real footage starts
ENTRANCE_DUR = 0.35     # fade + drop-in
SHIMMER_START = BROLL_HANDOFF + ENTRANCE_DUR
SHIMMER_DUR = 0.6       # one light sweep across the card, right after it settles
SLIDE_PX = 40
SHIMMER_WIDTH = 170
SHIMMER_STRENGTH = 150


def _smoothstep(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def animate_logo(bg_arr, t):
    """bg_arr: (H,W,4) float32 RGBA, 0-255. Returns a per-frame modified copy
    for local clip time t (seconds): fade+drop-in entrance right as the real
    footage takes over from broll_2, then one shimmer sweep across the card."""
    if t < BROLL_HANDOFF:
        out = bg_arr.copy()
        out[..., 3] = 0
        return out

    out = bg_arr.copy()

    if t < BROLL_HANDOFF + ENTRANCE_DUR:
        ease = _smoothstep((t - BROLL_HANDOFF) / ENTRANCE_DUR)
        out[..., 3] *= ease
        shift = round(-SLIDE_PX * (1 - ease))
        if shift:
            out = np.roll(out, shift, axis=0)
    else:
        ease = 1.0

    if SHIMMER_START <= t < SHIMMER_START + SHIMMER_DUR:
        # Only brighten pixels that are actually colored (the text/artwork) --
        # boosting the already-white card background is a no-op (255+x clips
        # right back to 255), so the sweep would be invisible without this.
        pos = (t - SHIMMER_START) / SHIMMER_DUR
        w = out.shape[1]
        band_center = -SHIMMER_WIDTH + pos * (w + 2 * SHIMMER_WIDTH)
        xs = np.arange(w, dtype=np.float32)
        intensity = np.exp(-((xs - band_center) / SHIMMER_WIDTH) ** 2) * SHIMMER_STRENGTH
        colored = out[..., :3].min(axis=2) < 235
        mask = (out[..., 3] > 0) & colored
        for c in range(3):
            out[..., c] = np.where(mask, np.clip(out[..., c] + intensity[np.newaxis, :], 0, 255), out[..., c])

    return out


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
    print(f"{len(frame_files)} frames to matte")

    bg_arr = np.array(Image.open(BG).convert("RGBA"), dtype=np.float32)
    session = new_session("u2net_human_seg")

    for i, fn in enumerate(frame_files):
        t = i / FPS
        src = Image.open(os.path.join(frames_dir, fn))
        cutout = remove(src, session=session)
        base = src.convert("RGBA")               # the REAL background, kept as-is
        bg_frame = Image.fromarray(animate_logo(bg_arr, t).astype(np.uint8), "RGBA")
        comp = Image.alpha_composite(base, bg_frame)  # animated logo layered on top
        comp = Image.alpha_composite(comp, cutout)    # he's in front of both
        comp.convert("RGB").save(os.path.join(out_dir, fn))
        if (i + 1) % 20 == 0 or i + 1 == len(frame_files):
            print(f"  {i + 1}/{len(frame_files)}")

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
