"""Text-behind-subject treatment for the 189-round reel's two hook beats.

Generalised from the 2026-08-14 Salman reel's date_behind.py: same z-order
(footage -> animated type plate -> his rembg u2net_human_seg cutout on top),
same in-place overwrite of a segment, same --preview contact sheet. Two
segments are treated, each with its own kinetic type:

    seg 1  "189 round is happening"            -> giant "189", digits drop in
                                                  one by one with a back-ease
    seg 2  "this Thursday on the 15th of Oct"  -> "THURSDAY" letters rise in,
                                                  fly out, then "15" slams and
                                                  "OCT" slides in beside it

Times are LOCAL to each segment (keep start subtracted). Word times, from
work/raw.transcript.json:
    seg 1 keep 3.63: "189" 3.72 -> 0.09, "round" 0.57, "happening" 1.01-1.39
    seg 2 keep 5.42: "Thursday" 5.86 -> 0.44-1.14, "fifteenth" 1.52,
                     "October" 2.04-2.50, segment ends 2.66

Layout comes from rembg probes of these exact segments (head-top y / x span):
    seg 1  head top 502-550, x ~360-770 as he sways
    seg 2  head top 420-472, x ~300-850
Type is placed ABOVE the head with only its bottom ~20-25% tucked behind
him, so it reads as a magazine-cover "behind" rather than being eaten.

Run AFTER build_base.py and BEFORE insert_broll.py (re-running build_base
regenerates the segments and undoes this):
    python 2026-10-12_tushar-fast/text_behind.py 1 2
    python 2026-10-12_tushar-fast/text_behind.py --preview 1 2
"""
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FF = shutil.which("ffmpeg") or "ffmpeg"
REEL = os.path.dirname(os.path.abspath(__file__))
SEGDIR = os.path.join(REEL, "work", "segments")
FONT = os.path.join(REEL, "assets", "fonts", "Poppins-Black.ttf")
FONT_IT = os.path.join(REEL, "assets", "fonts", "Poppins-BlackItalic.ttf")
FPS = 30
W, H = 1080, 1920

GOLD = (255, 197, 0, 255)
NAVY = (16, 7, 150, 255)
CYAN = (0, 179, 227, 255)
WHITE = (255, 255, 255, 255)


def clamp01(p):
    return max(0.0, min(1.0, p))


def ease_out_back(p, s=1.9):
    p = clamp01(p) - 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def ease_out_cubic(p):
    return 1 - (1 - clamp01(p)) ** 3


def ease_in_cubic(p):
    return clamp01(p) ** 3


def glyph(ch, size, fill, font_path, shadow=None, depth=0):
    """One glyph as a tight RGBA image: solid fill with a hard offset
    'extrude' shadow (the retro 3D-type look common in viral edits)."""
    font = ImageFont.truetype(font_path, size)
    x0, y0, x1, y1 = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox(
        (0, 0), ch, font=font)
    pad = 10 + depth
    img = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if shadow and depth:
        for k in range(depth, 0, -1):
            d.text((pad - x0 + k, pad - y0 + k), ch, font=font, fill=shadow)
    d.text((pad - x0, pad - y0), ch, font=font, fill=fill)
    return img


class Word:
    """A word laid out glyph by glyph so each letter can animate on its own.
    (cx, bottom) anchors the row's centre-x and baseline-ish bottom edge."""

    def __init__(self, text, size, fill, font, cx, bottom, t_in, t_out,
                 stagger=0.05, enter="drop", exit="up", shadow=None, depth=0,
                 track=0, dur_in=0.28, dur_out=0.14):
        self.g = [glyph(c, size, fill, font, shadow, depth) if c != " " else None
                  for c in text]
        sp = int(size * 0.28)
        widths = [g.width if g else sp for g in self.g]
        total = sum(widths) + track * (len(widths) - 1)
        x = cx - total // 2
        self.xs = []
        for w_ in widths:
            self.xs.append(x)
            x += w_ + track
        self.bottom = bottom
        self.t_in, self.t_out = t_in, t_out
        self.stagger, self.enter, self.exit = stagger, enter, exit
        self.dur_in, self.dur_out = dur_in, dur_out
        self.right = x - track          # used to dock a second word beside it

    def draw(self, canvas, t):
        n = 0
        for g, x in zip(self.g, self.xs):
            if g is None:
                continue
            a0 = self.t_in + n * self.stagger
            n += 1
            if t < a0 or t >= self.t_out + self.dur_out:
                continue
            p = (t - a0) / self.dur_in
            dx = dy = 0
            scale, alpha = 1.0, 1.0
            if self.enter == "drop":          # falls from above, overshoots
                dy = int(-260 * (1 - ease_out_back(p)))
                alpha = clamp01(p * 3)
            elif self.enter == "rise":        # rises from below, fades in
                dy = int(120 * (1 - ease_out_cubic(p)))
                alpha = clamp01(p * 2.5)
            elif self.enter == "slam":        # big -> 1.0 punch
                scale = 1 + 0.9 * (1 - ease_out_back(p, 1.4))
                alpha = clamp01(p * 4)
            elif self.enter == "slide":       # from the right
                dx = int(300 * (1 - ease_out_cubic(p)))
                alpha = clamp01(p * 2.5)
            if t >= self.t_out:               # exit
                q = ease_in_cubic((t - self.t_out) / self.dur_out)
                if self.exit == "up":
                    dy -= int(220 * q)
                alpha *= 1 - q
            img = g
            if abs(scale - 1) > 0.01:
                img = g.resize((max(1, int(g.width * scale)),
                                max(1, int(g.height * scale))), Image.BICUBIC)
            if alpha < 0.99:
                img = img.copy()
                img.putalpha(Image.fromarray(
                    (np.array(img.getchannel("A")) * alpha).astype(np.uint8)))
            gx = x + g.width // 2 - img.width // 2 + dx
            gy = self.bottom - g.height // 2 - img.height // 2 + dy
            canvas.alpha_composite(img, (gx, gy))


def spec(seg):
    if seg == 1:
        # "189" digits drop in right on the cut (the word starts 0.09 local);
        # stays up for the whole 1.49s segment, which hard-cuts into seg 2.
        # `bottom` is each glyph's bottom edge: head top is ~520 here, so a
        # bottom at 690 tucks the lowest ~35% of the digits behind his head.
        return [Word("189", 430, NAVY, FONT_IT, cx=W // 2, bottom=700,
                     t_in=0.0, t_out=9.0, stagger=0.07, enter="drop",
                     shadow=GOLD, depth=18, track=-6)]
    if seg == 2:
        thu = Word("THURSDAY", 138, NAVY, FONT, cx=W // 2, bottom=480,
                   t_in=0.30, t_out=1.38, stagger=0.035, enter="rise",
                   shadow=GOLD, depth=10, track=-4, dur_out=0.12)
        fifteen = Word("15", 330, GOLD, FONT_IT, cx=0, bottom=520,
                       t_in=1.50, t_out=9.0, stagger=0.06, enter="slam",
                       shadow=NAVY, depth=16, dur_in=0.24)
        octo = Word("OCT", 190, NAVY, FONT, cx=0, bottom=520,
                    t_in=1.98, t_out=9.0, stagger=0.05, enter="slide",
                    shadow=CYAN, depth=10, dur_in=0.24)
        # dock OCT to the right of 15, then centre the pair as one row
        shift = fifteen.right + 24 - octo.xs[0]
        octo.xs = [x + shift for x in octo.xs]
        row_l, row_r = fifteen.xs[0], octo.xs[-1] + octo.g[-1].width
        dx = W // 2 - (row_l + row_r) // 2
        fifteen.xs = [x + dx for x in fifteen.xs]
        octo.xs = [x + dx for x in octo.xs]
        return [thu, fifteen, octo]
    raise SystemExit(f"no spec for seg {seg}")


def render_plate(t, words):
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for w in words:
        w.draw(canvas, t)
    return canvas if canvas.getbbox() else None


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


def seg_path(seg):
    return os.path.join(SEGDIR, f"seg_{seg:02d}.mp4")


def preview(segs):
    from rembg import new_session, remove
    sess = new_session("u2net_human_seg")
    tmp = os.path.join(REEL, "work", "tb_preview")
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(os.path.join(REEL, "check"), exist_ok=True)
    samples = {1: (0.12, 0.35, 0.8, 1.35), 2: (0.45, 0.9, 1.62, 2.1, 2.55)}
    for seg in segs:
        words = spec(seg)
        tiles = []
        for t in samples[seg]:
            f = os.path.join(tmp, f"s{seg}_{t}.png")
            run(["-ss", f"{t:.2f}", "-i", seg_path(seg), "-frames:v", "1", f])
            src = Image.open(f)
            comp = src.convert("RGBA")
            plate = render_plate(t, words)
            if plate is not None:
                comp = Image.alpha_composite(comp, plate)
                comp = Image.alpha_composite(comp, remove(src, session=sess))
            tiles.append(comp.convert("RGB"))
        sheet = Image.new("RGB", (W * len(tiles), H))
        for i, im in enumerate(tiles):
            sheet.paste(im, (W * i, 0))
        dest = os.path.join(REEL, "check", f"tb_preview_seg{seg}.jpg")
        sheet.resize((sheet.width // 4, sheet.height // 4)).save(dest, quality=90)
        print("wrote", dest)
    shutil.rmtree(tmp, ignore_errors=True)


def bake(seg):
    from rembg import new_session, remove
    words = spec(seg)
    src_mp4 = seg_path(seg)
    tmp = os.path.join(REEL, "work", f"tb_tmp_{seg}")
    shutil.rmtree(tmp, ignore_errors=True)
    fdir, odir = os.path.join(tmp, "f"), os.path.join(tmp, "o")
    os.makedirs(fdir)
    os.makedirs(odir)
    audio = os.path.join(tmp, "a.aac")
    run(["-i", src_mp4, "-vn", "-c:a", "copy", audio])
    run(["-i", src_mp4, os.path.join(fdir, "f_%05d.png")])
    sess = new_session("u2net_human_seg")
    files = sorted(os.listdir(fdir))
    for i, fn in enumerate(files):
        src = Image.open(os.path.join(fdir, fn))
        plate = render_plate(i / FPS, words)
        comp = src.convert("RGBA")
        if plate is not None:
            # slight feather on the matte so hair edges don't look cut out
            cut = remove(src, session=sess)
            a = cut.getchannel("A").filter(ImageFilter.GaussianBlur(1.2))
            cut.putalpha(a)
            comp = Image.alpha_composite(Image.alpha_composite(comp, plate), cut)
        comp.convert("RGB").save(os.path.join(odir, fn))
        if (i + 1) % 15 == 0 or i + 1 == len(files):
            print(f"  seg {seg}: {i + 1}/{len(files)}")
    out = os.path.join(tmp, "out.mp4")
    run(["-framerate", str(FPS), "-i", os.path.join(odir, "f_%05d.png"), "-i", audio,
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-color_range", "tv",
         "-c:a", "copy", "-video_track_timescale", "90000", out])
    shutil.copy2(out, src_mp4)
    shutil.rmtree(tmp, ignore_errors=True)
    print("wrote", src_mp4)


if __name__ == "__main__":
    args = sys.argv[1:]
    segs = [int(a) for a in args if a.isdigit()] or [1, 2]
    if "--preview" in args:
        preview(segs)
    else:
        for s in segs:
            bake(s)
