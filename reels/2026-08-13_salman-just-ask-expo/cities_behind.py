"""Image-behind-subject treatment for the reel's three-cities beat (the user's
"use some stock pictures of Melbourne Sydney and Adelaide and use image behind
subject when he says that... use only half of the top part of the screen").

Puts a real photo of each city BEHIND Salman for segment 3 (the P3b keep span,
clip index 3) -- the line "in our Melbourne, Sydney, and Adelaide office" --
cutting between the three in sync with him naming each one.

Composite order per frame, while a plate is visible:
    original footage (his real street) -> the city photo band -> his rembg
    cutout (u2net_human_seg) on top
so he genuinely stands in front of the skyline. Same z-order and resumable
frame-cache structure as date_behind.py.

THE BAND IS THE TOP HALF ONLY, as asked: each photo is a 1080x960 crop
(assets/cities/*_band.jpg, see that folder's CREDITS.txt for sourcing and
licences) drawn over y=0..960. Its bottom 80px ramp to transparent rather than
ending on a hard horizontal line, which would read as a UI panel rather than a
backdrop -- BAND_FEATHER controls that. His head sits at roughly y=670-845 in
this segment, i.e. inside the band, so the cutout genuinely overlaps the photo
and the effect reads.

Timing is LOCAL to this segment's own clock (0 .. 3.10, the P3b keep span
6.65-9.75). Output-timeline word times minus this segment's 15.55 start:
    "Melbourne,"  16.219 -> 0.669 local
    "Sydney,"     16.979 -> 1.429 local
    "Adelaide"    17.879 -> 2.329 local

Each photo enters just ahead of its city name and hands straight over to the
next, with a short cross-dissolve rather than a hard snap (the two overlap for
0.12s, so the outgoing alpha is still falling as the incoming one rises):
    MELBOURNE  0.52 -> 1.40
    SYDNEY     1.30 -> 2.30
    ADELAIDE   2.20 -> 3.04

Each photo also carries its CITY NAME, set into the band at a fixed y=505
baseline (see the LABEL_* block for why that position is safe and why the type
is stroked rather than plain). The label lags its photo by LABEL_LAG and slides
up as it fades in, so the beat reads photo-then-name rather than both landing
flat together; it shares the photo's exit so the pair always clears as one.
Because the labels live inside the band, they are BEHIND him too -- consistent
with the photos, though in practice he never reaches high enough to cross them.

The final exit deliberately lands under the outgoing wipe (the segment cut is
at 18.65 and the wipe covers +/-0.25s around it, i.e. local 2.85-3.35), so the
last photo never visibly pops off on clean footage.

Note this segment also carries a slow zoom-IN baked in by build_base.py
(1.00 -> 1.10 across the segment). The band is rendered in fixed output space,
so the footage and his cutout push in while the photos stay locked -- the same
relationship date_behind.py's plate has, and it reads as the photos being a
backdrop rather than part of the scene.

Overwrites work/segments/seg_03.mp4 in place -- run AFTER build_base.py and
BEFORE insert_broll.py (order doesn't matter relative to date_behind.py /
prep_searchmg.py -- they touch different files):

    PODCUT_REEL=2026-08-13_salman-just-ask-expo \\
        python 2026-08-13_salman-just-ask-expo/cities_behind.py

Re-running build_base.py regenerates the segment and undoes this.
Pass --preview to write check/cities_preview.jpg -- the real composite
(footage -> band -> cutout) on one frame per city, so the framing and z-order
can be judged without paying for the whole segment's matting.
"""
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
REEL = os.path.dirname(os.path.abspath(__file__))
SEG = os.path.join(REEL, "work", "segments", "seg_03.mp4")
CITY_DIR = os.path.join(REEL, "assets", "cities")
TMP = os.path.join(REEL, "work", "cities_tmp")
FPS = 30
W, H = 1080, 1920

BAND_H = 960          # exactly the top half, per the brief
BAND_FEATHER = 80     # bottom rows that ramp to transparent

# (file, label, entrance_start, hold_start, exit_start, exit_end) -- segment-local
CITIES = [
    ("melbourne_band.jpg", "MELBOURNE", 0.52, 0.64, 1.30, 1.42),
    ("sydney_band.jpg",    "SYDNEY",    1.30, 1.42, 2.20, 2.32),
    ("adelaide_band.jpg",  "ADELAIDE",  2.20, 2.32, 2.92, 3.04),
]

DRIFT = 0.045         # slow Ken Burns push across each photo's own window
PUNCH = 0.05          # extra scale on entrance, easing back to the drift

# --- city name labels ---------------------------------------------------
# The whole frame above y=600 is clear of him in this segment (measured off
# work/base.mp4 with rembg across the band window: he first appears at
# y=600-720, x=520..638, and only widens below that). So the label sits with
# its baseline at y=505 -- inside the photo band, just above his head, clear of
# the logo chip at the top, and impossible to occlude.
#
# White fill with a heavy navy stroke, NOT the plate's gold-on-navy: these
# photos run from bright cloud (Sydney's sails are nearly white) to dark
# sunset, and a stroke is the only treatment that holds up across all three.
# The label is drawn at fixed size on top of the drifting photo rather than
# baked into it, so the type stays crisp while the image behind it moves.
LABEL_FONT = os.path.join(REEL, "assets", "fonts", "Poppins-Black.ttf")
LABEL_SIZE = 120
LABEL_MAX_W = 900
LABEL_BASELINE = 505
LABEL_RULE_H = 12          # gold rule under the name
LABEL_RULE_GAP = 22
LABEL_RISE = 26            # slide-up distance on entrance
LABEL_LAG = 0.10           # label lands just after its photo, as a reveal
WHITE = (255, 255, 255, 255)
NAVY = (16, 7, 150, 255)   # brand #100796
GOLD = (255, 197, 0, 255)  # brand #FFC500


def _smoothstep(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def _alpha(t, a, b, c, d):
    if t < a:
        return 0.0
    if t < b:
        return _smoothstep((t - a) / (b - a))
    if t < c:
        return 1.0
    if t < d:
        return 1.0 - _smoothstep((t - c) / (d - c))
    return 0.0


def _scale(t, a, b, c, d):
    """Entrance punch settling into a slow drift for the rest of the window."""
    span = max(1e-6, d - a)
    drift = 1.0 + DRIFT * _smoothstep((t - a) / span)
    if t < b:
        return drift + PUNCH * (1.0 - _smoothstep((t - a) / max(1e-6, b - a)))
    return drift


def _label_img(text):
    """One city name: white on a navy stroke, over a gold rule. Returned as a
    tight RGBA tile whose bottom edge is the rule, so callers position by
    LABEL_BASELINE without needing font metrics."""
    font = ImageFont.truetype(LABEL_FONT, LABEL_SIZE)
    stroke = 7
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    x0, y0, x1, y1 = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
    tw, th = x1 - x0, y1 - y0
    pad = 10
    tile = Image.new("RGBA", (tw + pad * 2,
                              th + pad * 2 + LABEL_RULE_GAP + LABEL_RULE_H),
                     (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.text((pad - x0, pad - y0), text, font=font, fill=WHITE,
           stroke_width=stroke, stroke_fill=NAVY)
    ry = th + pad * 2 + LABEL_RULE_GAP
    rw = int(tw * 0.42)
    rx = (tile.width - rw) // 2
    d.rounded_rectangle([rx, ry, rx + rw, ry + LABEL_RULE_H],
                        radius=LABEL_RULE_H // 2, fill=GOLD)
    if tile.width > LABEL_MAX_W:
        k = LABEL_MAX_W / tile.width
        tile = tile.resize((LABEL_MAX_W, max(1, int(tile.height * k))),
                           Image.LANCZOS)
    return tile


def load_bands():
    """Each photo as an RGBA band, pre-feathered along its bottom edge, plus
    its rendered city-name label."""
    ramp = np.ones(BAND_H, dtype=np.float32)
    ramp[BAND_H - BAND_FEATHER:] = np.linspace(1.0, 0.0, BAND_FEATHER)
    out = []
    for name, label, a, b, c, d in CITIES:
        im = Image.open(os.path.join(CITY_DIR, name)).convert("RGB")
        if im.size != (W, BAND_H):
            im = im.resize((W, BAND_H), Image.LANCZOS)
        rgba = im.convert("RGBA")
        alpha = (ramp[:, None] * 255).astype(np.uint8)
        rgba.putalpha(Image.fromarray(np.repeat(alpha, W, axis=1)))
        out.append({"img": rgba, "label": _label_img(label), "t": (a, b, c, d)})
    return out


def render_band(t, bands):
    """The full-frame overlay for segment-local time `t`, or None when nothing
    is visible so the caller can skip that frame's matting entirely."""
    canvas = None
    for band in bands:
        a, b, c, d = band["t"]
        al = _alpha(t, a, b, c, d)
        if al <= 0.001:
            continue
        if canvas is None:
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img = band["img"]
        s = _scale(t, a, b, c, d)
        if abs(s - 1.0) > 0.002:
            nw, nh = int(W * s), int(BAND_H * s)
            img = img.resize((nw, nh), Image.LANCZOS)
            # keep the band pinned to the top edge, centred horizontally, so the
            # drift never exposes a gap above or beside it
            img = img.crop(((nw - W) // 2, 0, (nw - W) // 2 + W, BAND_H))
        if al < 0.999:
            ch = np.array(img.getchannel("A")).astype(np.float32) * al
            img = img.copy()
            img.putalpha(Image.fromarray(ch.astype(np.uint8)))
        canvas.alpha_composite(img, (0, 0))

        # City name, lagged slightly behind its photo so it reads as a reveal
        # rather than arriving stuck to the image. Drawn at fixed size (no
        # drift) to keep the type crisp, and it shares the photo's own exit so
        # the pair always clears together.
        lab_a = _alpha(t, a + LABEL_LAG, b + LABEL_LAG, c, d)
        if lab_a > 0.001:
            lab = band["label"]
            rise = int(round(LABEL_RISE * (1.0 - _smoothstep(
                (t - (a + LABEL_LAG)) / max(1e-6, (b + LABEL_LAG) - (a + LABEL_LAG))))))
            if lab_a < 0.999:
                ch = np.array(lab.getchannel("A")).astype(np.float32) * lab_a
                lab = lab.copy()
                lab.putalpha(Image.fromarray(ch.astype(np.uint8)))
            canvas.alpha_composite(lab, ((W - lab.width) // 2,
                                         LABEL_BASELINE - lab.height + rise))
    return canvas


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args,
                   check=True)


def preview():
    from rembg import new_session, remove

    bands = load_bands()
    session = new_session("u2net_human_seg")
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(os.path.join(REEL, "check"), exist_ok=True)
    tiles = []
    for t in (0.85, 1.60, 2.50):
        frame = os.path.join(TMP, f"pv_{t}.png")
        run(["-ss", f"{t:.2f}", "-i", SEG, "-frames:v", "1", frame])
        src = Image.open(frame)
        comp = src.convert("RGBA")
        band = render_band(t, bands)
        if band is not None:
            comp = Image.alpha_composite(comp, band)
            comp = Image.alpha_composite(comp, remove(src, session=session))
        tiles.append(comp.convert("RGB"))
    sheet = Image.new("RGB", (W * len(tiles), H))
    for i, im in enumerate(tiles):
        sheet.paste(im, (W * i, 0))
    sheet = sheet.resize((sheet.width // 4, sheet.height // 4))
    dest = os.path.join(REEL, "check", "cities_preview.jpg")
    sheet.save(dest, quality=92)
    shutil.rmtree(TMP, ignore_errors=True)
    print("wrote", dest)


def main():
    from rembg import new_session, remove

    bands = load_bands()
    frames_dir = os.path.join(TMP, "frames")
    out_dir = os.path.join(TMP, "out")
    audio = os.path.join(TMP, "audio.aac")

    expected = None
    if os.path.isdir(frames_dir) and os.listdir(frames_dir):
        probe = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", SEG],
            capture_output=True, text=True)
        try:
            expected = round(float(probe.stdout.strip()) * FPS)
        except ValueError:
            expected = None
    incomplete = expected is not None and len(os.listdir(frames_dir)) < expected

    if not os.path.isdir(frames_dir) or not os.listdir(frames_dir) or incomplete:
        shutil.rmtree(TMP, ignore_errors=True)
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

    session = new_session("u2net_human_seg") if todo else None
    matted = 0

    for i, fn in enumerate(frame_files):
        if fn in already:
            continue
        t = i / FPS
        src = Image.open(os.path.join(frames_dir, fn))
        band = render_band(t, bands)
        if band is not None:
            comp = Image.alpha_composite(src.convert("RGBA"), band)
            comp = Image.alpha_composite(comp, remove(src, session=session))
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
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-color_range", "tv",
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
    if "--preview" in sys.argv:
        preview()
    else:
        main()
