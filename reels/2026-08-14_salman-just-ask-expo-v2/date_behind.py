"""Text-behind-subject treatment for the reel's date/time beat (the user's
"highlight key dates and times with big fonts and use text behind subject").

Puts a giant "25 AUG" and then "2-5 PM" BEHIND Salman for segment 2 (the P3a
keep span, clip index 2) -- the line "...on 25th of August from 2 p.m. to
5 p.m.". The plain 2-word caption cards are suppressed across this window by
content.json's silent hero_words entry, so the baked graphic owns it.

Composite order per frame, while a plate element is visible:
    original footage (his real surroundings) -> the animated text plate
    -> his rembg cutout (u2net_human_seg) on top
so he genuinely stands in front of the type rather than it being a flat
overlay. Same z-order and resumable frame-cache structure as the 2026-08-07
Maheesha reel's hero_3reasons.py.

Timing is LOCAL to this segment's own clock (0 .. 6.45, the P3a keep span
0.20-6.65). Output-timeline word times minus this segment's 9.10 start:
    "25th"          12.559 -> 3.459 local
    "of August" end 13.679 -> 4.579 local
    "2"             14.119 -> 5.019 local
    "5 p.m." ends   15.359 -> 6.259 local

The two blocks play SEQUENTIALLY in one screen position rather than stacking
(build_elements() documents the silhouette measurements that force this):
    "25 AUG"  punch-scales in at 3.30, clears 4.70 -> 4.88
    "2-5 PM"  punch-scales in at 4.90, clears 6.20 -> 6.40

The final exit deliberately lands under the outgoing wipe (the segment cut is
at 6.45 and the wipe covers +/-0.25s around it), so the plate never visibly
pops off on clean footage.

Note this segment already carries a slow zoom-OUT baked in by build_base.py
(1.10 -> 1.00 across the segment). The plate is rendered in fixed output
space, so the footage and his cutout drift back slightly while the type stays
locked -- which is the intended reveal, not a mismatch.

Overwrites work/segments/seg_02.mp4 in place -- run AFTER build_base.py and
BEFORE insert_broll.py:

    PODCUT_REEL=2026-08-13_salman-just-ask-expo \\
        python 2026-08-13_salman-just-ask-expo/date_behind.py

Re-running build_base.py regenerates the segment and undoes this.
Pass --preview to write check/date_plate_preview.jpg -- the real composite
(footage -> plate -> cutout) on four sample frames only, so the layout and
z-order can be judged without paying for the whole segment's matting.
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
SEG = os.path.join(REEL, "work", "segments", "seg_02.mp4")
FONT = os.path.join(REEL, "assets", "fonts", "Poppins-Black.ttf")
FONT_ITALIC = os.path.join(REEL, "assets", "fonts", "Poppins-BlackItalic.ttf")
TMP = os.path.join(REEL, "work", "datebehind_tmp")
FPS = 30
W, H = 1080, 1920

GOLD = (255, 197, 0, 255)      # brand #FFC500
NAVY = (16, 7, 150, 255)       # brand #100796
WHITE = (255, 255, 255, 255)
CYAN = (0, 179, 227, 255)      # brand #00B3E3

# (entrance_start, hold_start, exit_start, exit_end) per element, segment-local.
# Sequential, not stacked -- see build_elements() for why they have to share
# one screen position. "25 AUG" holds across "25th of August" (3.459-4.579)
# and clears during "from"; "2-5 PM" lands just before "2" (5.019) and holds
# past the final "p.m." (ends 6.259).
DATE_T = (3.30, 3.50, 4.70, 4.88)
TIME_T = (4.90, 5.08, 6.20, 6.40)


def _smoothstep(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def _alpha(t, timing):
    a, b, c, d = timing
    if t < a:
        return 0.0
    if t < b:
        return _smoothstep((t - a) / (b - a))
    if t < c:
        return 1.0
    if t < d:
        return 1.0 - _smoothstep((t - c) / (d - c))
    return 0.0


def _punch_scale(t, timing, overshoot=0.18):
    """Scale-punch entrance: overshoots past 1.0 then settles. 1.0 once held."""
    a, b, _c, _d = timing
    if t < a:
        return 1.0 + overshoot
    if t < b:
        return 1.0 + overshoot * (1.0 - _smoothstep((t - a) / (b - a)))
    return 1.0


def _rise_offset(t, timing, rise=70):
    """Slide-up entrance: starts `rise` px low, settles to 0."""
    a, b, _c, _d = timing
    if t < a:
        return rise
    if t < b:
        return int(round(rise * (1.0 - _smoothstep((t - a) / (b - a)))))
    return 0


def _text_img(text, size, fill, stroke_fill, stroke_width, font_path=FONT):
    """Render one line of type onto a tightly-cropped RGBA image."""
    font = ImageFont.truetype(font_path, size)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    x0, y0, x1, y1 = probe.textbbox((0, 0), text, font=font,
                                    stroke_width=stroke_width)
    pad = 12
    img = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - x0, pad - y0), text, font=font, fill=fill,
                             stroke_width=stroke_width, stroke_fill=stroke_fill)
    return img


# Where his silhouette sits, measured off this segment's own footage (rembg
# alpha, union of 8 samples across the plate window -- the probe that produced
# these numbers is in the reel's check/ notes):
#
#     y  600- 700   occupied x 518..606   <- just his head, 88px wide
#     y  700- 800   occupied x 421..630
#     y  800- 900   occupied x 390..681
#     y  900-1500   occupied x ~310..750  <- torso/arms, ~410px wide throughout
#
# That is the whole design constraint. Below y=900 his body is ~410px of solid
# occlusion dead-centre, so ANY centred line of type there loses its middle --
# the first attempt put "2-5 PM" at y=1210 and his torso ate the "5", leaving
# "2- PM" on screen (check/date_plate_preview.jpg, second version). The only
# band where type survives is 600-800, where he is head-width.
#
# So both blocks share that band and play SEQUENTIALLY rather than stacking:
# "25 AUG" while he says the date, swapping to "2-5 PM" as he says the time.
# Each is built as two words with a gap, so his head falls INTO the gap and
# the words read whole on either side of him -- that is what makes the
# behind-subject read as deliberate composition instead of damage.
BAND_Y = 772
# His head centre in that band. A centred row's split point sits at
# W/2 + (w1 - w2)/2, so the row is nudged horizontally to land the split here.
HEAD_CX = 562
MAX_ROW = 900


def _word_row(w1_img, w2_img, gap=22):
    """Compose two word images into one row, fit it inside MAX_ROW, and return
    (row, cx) with cx chosen so the gap between the words lands on HEAD_CX."""
    row_h = max(w1_img.height, w2_img.height)
    row = Image.new("RGBA", (w1_img.width + gap + w2_img.width, row_h),
                    (0, 0, 0, 0))
    row.alpha_composite(w1_img, (0, (row_h - w1_img.height) // 2))
    row.alpha_composite(w2_img, (w1_img.width + gap,
                                 (row_h - w2_img.height) // 2))
    w1w, w2w = w1_img.width, w2_img.width
    if row.width > MAX_ROW:
        k = MAX_ROW / row.width
        row = row.resize((MAX_ROW, max(1, int(row.height * k))), Image.LANCZOS)
        w1w, w2w = w1w * k, w2w * k
    # split of a row drawn centred at cx sits at cx + (w1 - w2)/2
    cx = int(round(HEAD_CX - (w1w - w2w) / 2))
    half = row.width // 2
    cx = max(40 + half, min(W - 40 - half, cx))   # keep the row on-frame
    return row, cx


def build_elements():
    """The two type blocks, each as (image, centre_x, centre_y, timing)."""
    els = []

    # "25" enormous + "AUG" beside it. Sizes were capped after a first pass at
    # 520/210pt overflowed both frame edges; MAX_ROW now enforces the margin
    # rather than the point sizes being trusted. The punch entrance overshoots
    # 18% on top of the fitted size, which is why the cap is 900 and not 1080.
    row, cx = _word_row(_text_img("25", 400, GOLD, NAVY, 9,
                                 font_path=FONT_ITALIC),
                        _text_img("AUG", 180, WHITE, NAVY, 7))
    els.append({"img": row, "cx": cx, "cy": BAND_Y, "timing": DATE_T,
                "anim": "punch"})

    # "2-5" in the same gold/italic treatment so the swap reads as the same
    # card updating, with "PM" taking AUG's role on the right of his head.
    row2, cx2 = _word_row(_text_img("2–5", 400, GOLD, NAVY, 9,
                                    font_path=FONT_ITALIC),
                          _text_img("PM", 180, WHITE, NAVY, 7))
    els.append({"img": row2, "cx": cx2, "cy": BAND_Y, "timing": TIME_T,
                "anim": "punch"})
    return els


def render_plate(t, els):
    """The full 1080x1920 overlay for segment-local time `t` (RGBA, or None
    when nothing is visible so the caller can skip the matting entirely)."""
    canvas = None
    for el in els:
        a = _alpha(t, el["timing"])
        if a <= 0.001:
            continue
        if canvas is None:
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img = el["img"]
        dy = 0
        if el["anim"] == "punch":
            s = _punch_scale(t, el["timing"])
            if abs(s - 1.0) > 0.002:
                img = img.resize((max(1, int(img.width * s)),
                                  max(1, int(img.height * s))), Image.LANCZOS)
        elif el["anim"] == "rise":
            dy = _rise_offset(t, el["timing"])
        if a < 0.999:
            ch = np.array(img.getchannel("A")).astype(np.float32) * a
            img = img.copy()
            img.putalpha(Image.fromarray(ch.astype(np.uint8)))
        canvas.alpha_composite(img, (el["cx"] - img.width // 2,
                                     el["cy"] - img.height // 2 + dy))
    return canvas


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args,
                   check=True)


def preview():
    """Layout check: the real composite (footage -> plate -> cutout) on a
    handful of frames only, so the z-order and the type's clearance around his
    head can be judged without paying for the whole segment's matting."""
    from rembg import new_session, remove

    els = build_elements()
    session = new_session("u2net_human_seg")
    out_dir = os.path.join(REEL, "check")
    os.makedirs(out_dir, exist_ok=True)
    tiles = []
    for t in (3.7, 4.4, 5.3, 6.1):
        frame = os.path.join(TMP, f"pv_{t}.png")
        os.makedirs(TMP, exist_ok=True)
        run(["-ss", f"{t:.2f}", "-i", SEG, "-frames:v", "1", frame])
        src = Image.open(frame)
        base = src.convert("RGBA")
        plate = render_plate(t, els)
        if plate is not None:
            comp = Image.alpha_composite(base, plate)
            comp = Image.alpha_composite(comp, remove(src, session=session))
        else:
            comp = base
        tiles.append(comp.convert("RGB"))
    sheet = Image.new("RGB", (W * len(tiles), H))
    for i, im in enumerate(tiles):
        sheet.paste(im, (W * i, 0))
    sheet = sheet.resize((sheet.width // 4, sheet.height // 4))
    dest = os.path.join(out_dir, "date_plate_preview.jpg")
    sheet.save(dest, quality=92)
    shutil.rmtree(TMP, ignore_errors=True)
    print("wrote", dest)


def main():
    from rembg import new_session, remove

    els = build_elements()
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
        plate = render_plate(t, els)
        if plate is not None:
            base = src.convert("RGBA")
            cutout = remove(src, session=session)
            comp = Image.alpha_composite(base, plate)
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
