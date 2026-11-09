"""Per-segment FX pass for the Rahul '190 invitation round' reel (2026-10-21).

Brief (user): sourced images, kinetic text captions and motion graphics.
Toolkit forked from 2026-10-16_rahul-reel/fx.py (kinetic glyph words,
image-behind-subject photo cards via rembg matting, marker handwriting,
boiling hand-drawn strokes, virtual camera, velocity whip-zooms), plus new
motion-graphic elements for this script:

    NotifCard    'invitation received' push-notification drops in
    Stamp        rubber-stamp slam ('VISA LODGMENT')
    CommentCard  social comment bubble that types itself (occupation + points)
    LivePill     pulsing 'LIVE NOW' pill
    Confetti     deterministic confetti fall for 'congrats'
    PhotoCard(overlay=..., progress=...)  -> video-player card for 'detailed
                 video very soon' (photo thumbnail, play button, filling bar)

Rahul sits LEFT of centre, so layout is relative to his head in OUTPUT space:
HT (head-top y) and HX (head centre x) are probed by rembg on each segment's
first frame and pushed through that segment's first camera keyframe.

Bakes into work/segments/seg_XX.mp4 in place, AFTER build_base.py and BEFORE
insert_broll.py, always starting from the clean copies in work/segments_orig/.

    python fx.py            # all segments
    python fx.py 0 4        # just these
    python fx.py --preview 0 4   # contact sheets to check/ (no bake)
"""
import math
import os
import random
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FF = shutil.which("ffmpeg") or "ffmpeg"
REEL = os.path.dirname(os.path.abspath(__file__))
SEGDIR = os.path.join(REEL, "work", "segments")
ORIGDIR = os.path.join(REEL, "work", "segments_orig")
FONTS = os.path.join(REEL, "assets", "fonts")
PHOTOS = os.path.join(REEL, "assets", "photos")
POP = os.path.join(FONTS, "Poppins-Black.ttf")
POP_IT = os.path.join(FONTS, "Poppins-BlackItalic.ttf")
MARKER = os.path.join(FONTS, "PermanentMarker-Regular.ttf")
FPS = 30
W, H = 1080, 1920

GOLD = (255, 197, 0, 255)
NAVY = (16, 7, 150, 255)
CYAN = (0, 179, 227, 255)
GREEN = (49, 235, 124, 255)
RED = (232, 75, 55, 255)
WHITE = (255, 255, 255, 255)


# ----------------------------------------------------------------- easing
def c01(p):
    return max(0.0, min(1.0, p))


def e_cos(p):
    return (1 - math.cos(math.pi * c01(p))) / 2


def e_out_back(p, s=1.9):
    p = c01(p) - 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def e_out_cubic(p):
    return 1 - (1 - c01(p)) ** 3


def e_in_cubic(p):
    return c01(p) ** 3


def e_out_expo(p):
    p = c01(p)
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def e_in_expo(p):
    p = c01(p)
    return 0.0 if p <= 0 else 2 ** (10 * (p - 1))


def keyed(keys, t):
    """keys: [(t, value...), ...] -> cosine-interpolated tuple at t."""
    if t <= keys[0][0]:
        return keys[0][1:]
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            p = e_cos((t - a[0]) / max(1e-6, b[0] - a[0]))
            return tuple(x + (y - x) * p for x, y in zip(a[1:], b[1:]))
    return keys[-1][1:]


def with_alpha(img, a):
    if a >= 0.999:
        return img
    img = img.copy()
    img.putalpha(Image.fromarray((np.asarray(img.getchannel("A")) * a).astype(np.uint8)))
    return img


# ----------------------------------------------------------------- camera
def cam_xform(img, z, cx, cy, extra=1.0, ax=W / 2, ay=H):
    """Virtual camera: output pixel (x,y) samples input at
    cx + (ax + (x-ax)/extra - W/2)/z. `extra` scales about (ax,ay) in OUTPUT
    space -- used for the subject layer's parallax."""
    # clamp centre so the crop never leaves the frame
    hw, hh = W / (2 * z), H / (2 * z)
    cx = min(max(cx, hw), W - hw)
    cy = min(max(cy, hh), H - hh)
    k = 1.0 / (z * extra)
    a = k
    c = cx + (ax - ax / extra - W / 2) / z
    e = k
    f = cy + (ay - ay / extra - H / 2) / z
    return img.transform((W, H), Image.AFFINE, (a, 0, c, 0, e, f), resample=Image.BICUBIC)


def zoom_blur(img, strength, cx=W / 2, cy=H * 0.42, n=7):
    """Radial (zoom) motion blur: average n copies scaled 1..1+strength."""
    if strength < 0.004:
        return img
    base = img.convert("RGB")
    acc = np.zeros((H, W, 3), np.float32)
    for i in range(n):
        s = 1 + strength * i / (n - 1)
        acc += np.asarray(cam_xform(base, s, cx, cy), np.float32)
    return Image.fromarray((acc / n).astype(np.uint8))


# ----------------------------------------------------------- glyph words
_FONT_CACHE = {}


def font(path, size):
    k = (path, size)
    if k not in _FONT_CACHE:
        _FONT_CACHE[k] = ImageFont.truetype(path, size)
    return _FONT_CACHE[k]


def glyph(ch, size, fill, path, shadow=None, depth=0):
    f = font(path, size)
    x0, y0, x1, y1 = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), ch, font=f)
    pad = 10 + depth
    img = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if shadow and depth:
        for k in range(depth, 0, -1):
            d.text((pad - x0 + k, pad - y0 + k), ch, font=f, fill=shadow)
    d.text((pad - x0, pad - y0), ch, font=f, fill=fill)
    return img


class Word:
    """Kinetic word, glyph by glyph (from tushar-fast/text_behind.py).
    (cx, bottom) = row centre-x and glyph bottom edge."""

    def __init__(self, text, size, fill, path, cx, bottom, t_in, t_out,
                 stagger=0.05, enter="drop", exit="up", shadow=None, depth=0,
                 track=0, dur_in=0.28, dur_out=0.16, drift=(0, 0)):
        cx, bottom = int(cx), int(bottom)
        self.g = [glyph(c, size, fill, path, shadow, depth) if c != " " else None for c in text]
        sp = int(size * 0.28)
        pad = 10 + depth          # glyph() padding is NOT letter spacing
        widths = [g.width - 2 * pad + depth if g else sp for g in self.g]
        total = sum(widths) + track * (len(widths) - 1)
        x = cx - total // 2 - pad
        self.xs = []
        for w_ in widths:
            self.xs.append(x)
            x += w_ + track
        self.bottom = bottom
        self.t_in, self.t_out = t_in, t_out
        self.stagger, self.enter, self.exit = stagger, enter, exit
        self.dur_in, self.dur_out = dur_in, dur_out
        self.drift = drift          # px/s parallax drift while on screen

    def draw(self, canvas, t):
        n = 0
        ddx = int(self.drift[0] * max(0, t - self.t_in))
        ddy = int(self.drift[1] * max(0, t - self.t_in))
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
            if self.enter == "drop":
                dy = int(-260 * (1 - e_out_back(p)))
                alpha = c01(p * 3)
            elif self.enter == "rise":
                dy = int(160 * (1 - e_out_cubic(p)))
                alpha = c01(p * 2.5)
            elif self.enter == "slam":
                scale = 1 + 0.9 * (1 - e_out_back(p, 1.4))
                alpha = c01(p * 4)
            elif self.enter == "slide":
                dx = int(340 * (1 - e_out_expo(p)))
                alpha = c01(p * 2.5)
            if t >= self.t_out:
                q = e_in_cubic((t - self.t_out) / self.dur_out)
                if self.exit == "up":
                    dy -= int(260 * q)
                elif self.exit == "left":
                    dx -= int(900 * q)
                alpha *= 1 - q
            img = g
            if abs(scale - 1) > 0.01:
                img = g.resize((max(1, int(g.width * scale)), max(1, int(g.height * scale))),
                               Image.BICUBIC)
            img = with_alpha(img, alpha)
            gx = x + g.width // 2 - img.width // 2 + dx + ddx
            gy = self.bottom - g.height // 2 - img.height // 2 + dy + ddy
            canvas.alpha_composite(img, (gx, gy))


def rest_bbox(word):
    """Union of the word's glyph ink boxes at rest (no animation offsets)."""
    x0 = y0 = 10 ** 6
    x1 = y1 = -10 ** 6
    for g, x in zip(word.g, word.xs):
        if g is None:
            continue
        bx = g.getchannel("A").getbbox()
        if not bx:
            continue
        gy = word.bottom - g.height
        x0, y0 = min(x0, x + bx[0]), min(y0, gy + bx[1])
        x1, y1 = max(x1, x + bx[2]), max(y1, gy + bx[3])
    return x0, y0, x1, y1


class Highlight:
    """Highlighter-marker swipe behind a FRONT word: a rough, slightly
    skewed bar that wipes in left->right just before the word lands and
    drifts with it."""

    def __init__(self, word, color, t0, dur=0.18, pad=(26, 14), t_out=99, rot=-1.5, seed=1):
        x0, y0, x1, y1 = rest_bbox(word)
        x0, y0, x1, y1 = x0 - pad[0], y0 - pad[1], x1 + pad[0], y1 + pad[1]
        w, h = int(x1 - x0), int(y1 - y0)
        r = random.Random(seed)
        img = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        top = [(20 + w * i / 12, 20 + r.uniform(-5, 5)) for i in range(13)]
        bot = [(20 + w * i / 12, 20 + h + r.uniform(-5, 5)) for i in range(12, -1, -1)]
        d.polygon(top + bot, fill=color)
        self.img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.t0, self.dur, self.t_out, self.drift = t0, dur, t_out, word.drift
        self.word_t_in = word.t_in

    def draw(self, canvas, t):
        if t < self.t0 or t > self.t_out + 0.18:
            return
        p = e_out_cubic((t - self.t0) / self.dur)
        img = self.img
        rw = int(img.width * p)
        if rw < 2:
            return
        img = img.crop((0, 0, rw, img.height))
        if t > self.t_out:
            img = with_alpha(img, 1 - (t - self.t_out) / 0.18)
        dx = int(self.drift[0] * max(0, t - self.word_t_in))
        dy = int(self.drift[1] * max(0, t - self.word_t_in))
        canvas.alpha_composite(img, (int(self.cx - self.img.width / 2 + dx),
                                     int(self.cy - self.img.height / 2 + dy)))


def title_stack(lines, fill, hl, HT, t_in, path=POP, size=96, max_w=930, gap=1.22,
                enter="rise", t_out=99, exit="up", drift=(0, 0), seed=1, line_dt=0.16):
    """A multi-line highlighted title (FRONT layer) stacked upward from just
    above his head: last line's bottom at HT-40. Size auto-shrinks until the
    widest line fits max_w. Returns (items, union_bbox)."""
    while True:
        words = []
        for i, ln in enumerate(lines):
            k = len(lines) - 1 - i
            words.append(Word(ln, size, fill, path, cx=540, bottom=int(HT - 40 - k * size * gap),
                              t_in=t_in + i * line_dt, t_out=t_out, stagger=0.02, enter=enter,
                              exit=exit, shadow=None, depth=0, track=-2, dur_in=0.24,
                              drift=drift))
        boxes = [rest_bbox(w) for w in words]
        if max(b[2] - b[0] for b in boxes) <= max_w or size <= 40:
            break
        size -= 4
    items = []
    for i, w in enumerate(words):
        items += [Highlight(w, hl, w.t_in - 0.08, t_out=t_out, seed=seed + i), w]
    u = (min(b[0] for b in boxes), min(b[1] for b in boxes),
         max(b[2] for b in boxes), max(b[3] for b in boxes))
    return items, u


def box_pts(u, px=46, py=40):
    x0, y0, x1, y1 = u
    return [(x0 - px, y0 - py), (x1 + px, y0 - py - 8), (x1 + px + 6, y1 + py - 6),
            (x0 - px + 4, y1 + py), (x0 - px - 2, y0 - py - 12)]


# ------------------------------------------------------- hand-drawn kit
def catmull(pts, steps=10):
    if len(pts) < 3:
        return pts
    P = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for s in range(steps):
            u = s / steps
            u2, u3 = u * u, u * u * u
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * u
                                    + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * u2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * u3)
                             for k in (0, 1)))
    out.append(pts[-1])
    return out


def jitter(pts, amp, seed):
    r = random.Random(seed)
    return [(x + r.uniform(-amp, amp), y + r.uniform(-amp, amp)) for x, y in pts]


def truncate(pts, p):
    """First fraction p (by arc length) of a polyline."""
    if p >= 1:
        return pts
    seg = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    total = sum(seg) or 1
    want, acc, out = total * c01(p), 0.0, [pts[0]]
    for (a, b), L in zip(zip(pts, pts[1:]), seg):
        if acc + L >= want:
            u = (want - acc) / (L or 1)
            out.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
            return out
        out.append(b)
        acc += L
    return out


class Stroke:
    """A marker stroke: control points -> smoothed, jittered polyline drawn
    on over [t0, t0+dur]; 'boils' (re-jitters) 8x/s like hand-drawn
    animation. Drawn at 2x and downsampled by the caller for anti-aliasing."""

    def __init__(self, pts, t0, dur, color, width=12, t_out=99, smooth=True,
                 boil=3.0, seed=1, shadow=True, ease=e_out_cubic, drift=(0, 0)):
        self.base = catmull(pts) if smooth else pts
        self.t0, self.dur, self.t_out = t0, dur, t_out
        self.color, self.width, self.boil, self.seed = color, width, boil, seed
        self.shadow, self.ease, self.drift = shadow, ease, drift

    def draw(self, d2, t):
        if t < self.t0 or t > self.t_out + 0.2:
            return
        p = self.ease((t - self.t0) / self.dur)
        frame = int(t * 8)
        pts = jitter(self.base, self.boil, self.seed * 1000 + frame)
        pts = truncate(pts, p)
        if len(pts) < 2:
            return
        a = 1.0 if t <= self.t_out else 1 - (t - self.t_out) / 0.2
        dx = self.drift[0] * (t - self.t0)
        dy = self.drift[1] * (t - self.t0)
        P = [(2 * (x + dx), 2 * (y + dy)) for x, y in pts]
        w = int(self.width * 2)
        col = self.color[:3] + (int(255 * a),)
        if self.shadow:
            S = [(x + 7, y + 9) for x, y in P]
            d2.line(S, fill=(16, 7, 150, int(110 * a)), width=w, joint="curve")
        d2.line(P, fill=col, width=w, joint="curve")
        for x, y in (P[0], P[-1]):
            d2.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=col)


def ellipse_pts(cx, cy, rx, ry, turns=1.12, start=-2.4, n=40, wob=0.06, seed=3):
    r = random.Random(seed)
    out = []
    for i in range(n + 1):
        a = start + 2 * math.pi * turns * i / n
        k = 1 + r.uniform(-wob, wob)
        out.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    return out


def arrow(x0, y0, x1, y1, bend=0.25, head=46):
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    nx, ny = -(y1 - y0) * bend, (x1 - x0) * bend
    shaft = [(x0, y0), (mx + nx, my + ny), (x1, y1)]
    ang = math.atan2(y1 - (my + ny), x1 - (mx + nx))
    h1 = (x1 - head * math.cos(ang - 0.5), y1 - head * math.sin(ang - 0.5))
    h2 = (x1 - head * math.cos(ang + 0.5), y1 - head * math.sin(ang + 0.5))
    return shaft, [h1, (x1, y1), h2]


def arrow_strokes(x0, y0, x1, y1, t0, color, bend=0.25, width=11, seed=5, t_out=99):
    shaft, hd = arrow(x0, y0, x1, y1, bend)
    return [Stroke(shaft, t0, 0.26, color, width, t_out=t_out, seed=seed),
            Stroke(hd, t0 + 0.24, 0.10, color, width, t_out=t_out, smooth=False, seed=seed + 1)]


def tick(x, y, s, t0, color, width=15, seed=7, t_out=99):
    return Stroke([(x, y), (x + 0.35 * s, y + 0.4 * s), (x + s, y - 0.55 * s)],
                  t0, 0.2, color, width, smooth=False, seed=seed, t_out=t_out)


def magnifier(cx, cy, r, t0, color, seed=11, t_out=99):
    return [Stroke(ellipse_pts(cx, cy, r, r, turns=1.05, seed=seed), t0, 0.32, color, 12,
                   seed=seed, t_out=t_out),
            Stroke([(cx + r * 0.72, cy + r * 0.72), (cx + r * 1.7, cy + r * 1.7)],
                   t0 + 0.3, 0.14, color, 18, smooth=False, seed=seed + 1, t_out=t_out)]


def gear_pts(cx, cy, r, teeth=8):
    out = []
    for i in range(teeth * 4 + 1):
        a = 2 * math.pi * i / (teeth * 4)
        rr = r * (1.0 if (i // 2) % 2 == 0 else 0.78)
        out.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return out


def squiggle(x0, x1, y, amp=14, waves=4):
    n = waves * 6
    return [(x0 + (x1 - x0) * i / n, y + amp * math.sin(i / n * waves * 2 * math.pi))
            for i in range(n + 1)]


def zigzag(x0, x1, y0, y1, n=7):
    return [(x0 + (x1 - x0) * i / n, y0 if i % 2 == 0 else y1) for i in range(n + 1)]


class Marker:
    """Handwritten marker text, written on left->right with a soft wipe,
    a little rotation, and a pop on arrival."""

    def __init__(self, text, size, color, cx, cy, t0, dur=0.4, t_out=99, rot=-3,
                 shadow=True, drift=(0, 0), anchor="c"):
        f = font(MARKER, size)
        x0, y0, x1, y1 = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=f)
        pad = 24
        img = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if shadow:
            d.text((pad - x0 + 5, pad - y0 + 7), text, font=f, fill=(16, 7, 150, 90)
                   if color != NAVY else (255, 197, 0, 160))
        d.text((pad - x0, pad - y0), text, font=f, fill=color)
        self.img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
        self.cx, self.cy, self.anchor = cx, cy, anchor
        self.t0, self.dur, self.t_out, self.drift = t0, dur, t_out, drift

    def draw(self, canvas, t):
        if t < self.t0 or t > self.t_out + 0.18:
            return
        p = c01((t - self.t0) / self.dur)
        img = self.img
        w, h = img.size
        reveal = int(w * e_out_cubic(p))
        if reveal < 2:
            return
        if reveal < w:
            m = Image.new("L", (w, h), 0)
            ImageDraw.Draw(m).rectangle((0, 0, reveal, h), fill=255)
            m = m.filter(ImageFilter.GaussianBlur(6))
            a = Image.fromarray((np.asarray(img.getchannel("A"), np.float32)
                                 * np.asarray(m, np.float32) / 255).astype(np.uint8))
            img = img.copy()
            img.putalpha(a)
        if t > self.t_out:
            img = with_alpha(img, 1 - (t - self.t_out) / 0.18)
        dx = int(self.drift[0] * (t - self.t0))
        dy = int(self.drift[1] * (t - self.t0))
        x = self.cx - (w // 2 if self.anchor == "c" else 0) + dx
        canvas.alpha_composite(img, (int(x), int(self.cy - h // 2 + dy)))


class PhotoCard:
    """Image-behind-subject: a photo printed as a tilted white-bordered card
    with a soft shadow, rising up from behind his head with a back-ease and
    drifting (parallax) while held."""

    def __init__(self, path, box_w, box_h, cx, bottom, t0, t_out=99, rot=-3,
                 focus=(0.5, 0.6), drift=(-20, 0), label=None, overlay=None, progress=None):
        src = Image.open(path).convert("RGB")
        sw, sh = src.size
        tw, th = box_w, box_h
        sc = max(tw / sw, th / sh)
        rs = src.resize((int(sw * sc) + 1, int(sh * sc) + 1), Image.LANCZOS)
        ox = int((rs.width - tw) * focus[0])
        oy = int((rs.height - th) * focus[1])
        photo = rs.crop((ox, oy, ox + tw, oy + th))
        b = 18
        card = Image.new("RGBA", (tw + 2 * b, th + 2 * b), WHITE)
        card.paste(photo, (b, b))
        if label:
            d = ImageDraw.Draw(card)
            f = font(MARKER, label[1])
            d.text((b + 26, b + 14), label[0], font=f, fill=WHITE,
                   stroke_width=8, stroke_fill=NAVY)
        if overlay:
            overlay(card, b, tw, th)
        # progress bar track geometry inside self.img (only valid for rot=0)
        self.progress = progress
        self.bar = (40 + b + 30, 40 + b + th - 40, 40 + b + tw - 30, 40 + b + th - 28)
        m = Image.new("L", card.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, card.width - 1, card.height - 1), 26, fill=255)
        card.putalpha(m)
        sh_ = Image.new("RGBA", (card.width + 80, card.height + 80), (0, 0, 0, 0))
        sm = Image.new("L", sh_.size, 0)
        sm.paste(m, (40, 52))
        sh_.putalpha(sm.filter(ImageFilter.GaussianBlur(18)).point(lambda v: v * 0.45))
        sh_.alpha_composite(card, (40, 40))
        self.img = sh_.rotate(rot, resample=Image.BICUBIC, expand=True)
        self.cx, self.bottom = cx, bottom
        self.t0, self.t_out, self.drift = t0, t_out, drift

    def draw(self, canvas, t):
        if t < self.t0 or t > self.t_out + 0.25:
            return
        p = (t - self.t0) / 0.42
        dy = int(520 * (1 - e_out_back(p, 1.5)))
        sc = 0.86 + 0.14 * e_out_back(p, 1.5)
        img = self.img
        if self.progress and t > self.progress[0]:
            x0, y0, x1, y1 = self.bar
            k = e_cos((t - self.progress[0]) / (self.progress[1] - self.progress[0]))
            img = img.copy()
            dd = ImageDraw.Draw(img)
            xe = x0 + (x1 - x0) * k
            dd.rounded_rectangle((x0, y0, max(x0 + 12, xe), y1), 6, fill=RED)
            dd.ellipse((xe - 14, (y0 + y1) / 2 - 14, xe + 14, (y0 + y1) / 2 + 14), fill=WHITE)
        if abs(sc - 1) > 0.005:
            img = img.resize((int(img.width * sc), int(img.height * sc)), Image.BICUBIC)
        a = c01(p * 3)
        if t > self.t_out:
            q = e_in_cubic((t - self.t_out) / 0.25)
            dy += int(-180 * q)
            a *= 1 - q
        img = with_alpha(img, a)
        dx = int(self.drift[0] * (t - self.t0))
        ddy = int(self.drift[1] * (t - self.t0))
        canvas.alpha_composite(img, (int(self.cx - img.width // 2 + dx),
                                     int(self.bottom - img.height + dy + ddy)))




# ------------------------------------------------- motion-graphic elements
GREY = (110, 116, 140, 255)
INK = (24, 28, 48, 255)


def rounded_card(w, h, r, fill, shadow=0.35, blur=18, off=(0, 14)):
    """White-ish rounded card with a soft drop shadow. Returns (img, (ox, oy))
    where (ox, oy) is the card's top-left inside img."""
    pad = blur * 2 + max(abs(off[0]), abs(off[1]))
    img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((pad + off[0], pad + off[1], pad + off[0] + w,
                                         pad + off[1] + h), r, fill=int(255 * shadow))
    sh = Image.new("RGBA", img.size, (10, 8, 60, 255))
    sh.putalpha(m.filter(ImageFilter.GaussianBlur(blur)))
    img.alpha_composite(sh)
    ImageDraw.Draw(img).rounded_rectangle((pad, pad, pad + w, pad + h), r, fill=fill)
    return img, (pad, pad)


def envelope(d, cx, cy, s, color, width=6):
    x0, y0, x1, y1 = cx - s, cy - s * 0.68, cx + s, cy + s * 0.68
    d.rounded_rectangle((x0, y0, x1, y1), 8, outline=color, width=width)
    d.line([(x0 + 4, y0 + 6), (cx, cy + s * 0.12), (x1 - 4, y0 + 6)], fill=color, width=width,
           joint="curve")


class NotifCard:
    """Phone-style push notification that drops in from above with a
    back-ease, holds (slight drift) and flicks back up."""

    def __init__(self, title, sub, cx, top, t0, t_out=99, w=900, accent=NAVY):
        h = 168
        img, (ox, oy) = rounded_card(w, h, 40, (255, 255, 255, 250))
        d = ImageDraw.Draw(img)
        d.ellipse((ox + 30, oy + 29, ox + 140, oy + 139), fill=accent)
        envelope(d, ox + 85, oy + 84, 30, WHITE, 6)
        d.ellipse((ox + 118, oy + 26, ox + 146, oy + 54), fill=RED)          # unread dot
        d.text((ox + 170, oy + 30), title, font=font(POP, 44), fill=INK)
        d.text((ox + 170, oy + 96), sub, font=font(POP, 30), fill=GREY)
        d.text((ox + w - 34, oy + 34), "now", font=font(POP, 26), fill=GREY, anchor="ra")
        self.img, self.cx, self.top, self.oy = img, cx, top, oy
        self.t0, self.t_out = t0, t_out

    def draw(self, canvas, t):
        if t < self.t0 or t > self.t_out + 0.2:
            return
        p = (t - self.t0) / 0.42
        dy = -340 * (1 - e_out_back(p, 1.25))
        a = c01(p * 3)
        if t > self.t_out:
            q = e_in_cubic((t - self.t_out) / 0.2)
            dy -= 300 * q
            a *= 1 - q
        canvas.alpha_composite(with_alpha(self.img, a),
                               (int(self.cx - self.img.width / 2),
                                int(self.top - self.oy + dy)))


class Stamp:
    """Rubber-stamp slam: double-bordered ink stamp, scales down from 2.3x
    onto the frame with a hard landing, a short shake, and an ink-speckle
    texture so it reads as printed rather than typed."""

    def __init__(self, lines, color, cx, cy, t0, rot=-8, size=78, t_out=99, seed=3, bg=None):
        fs = [font(POP, size if i == 0 else int(size * 0.55)) for i in range(len(lines))]
        dd = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        boxes = [dd.textbbox((0, 0), ln, font=f) for ln, f in zip(lines, fs)]
        tw = max(b[2] - b[0] for b in boxes)
        th = sum(b[3] - b[1] for b in boxes) + 18 * (len(lines) - 1)
        pw, ph = tw + 110, th + 90
        img = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if bg:
            d.rounded_rectangle((6, 6, pw - 6, ph - 6), 22, fill=bg)
        d.rounded_rectangle((6, 6, pw - 6, ph - 6), 22, outline=color, width=10)
        d.rounded_rectangle((22, 22, pw - 22, ph - 22), 14, outline=color, width=4)
        y = 45
        for ln, f, b in zip(lines, fs, boxes):
            d.text(((pw - (b[2] - b[0])) / 2 - b[0], y - b[1]), ln, font=f, fill=color)
            y += b[3] - b[1] + 18
        r = np.random.default_rng(seed)
        holes = (r.random((ph, pw)) > 0.93).astype(np.float32)
        holes = np.asarray(Image.fromarray((holes * 255).astype(np.uint8))
                           .filter(ImageFilter.GaussianBlur(1.1)), np.float32) / 255
        a = np.asarray(img.getchannel("A"), np.float32) * (1 - 0.85 * np.clip(holes * 3, 0, 1))
        img.putalpha(Image.fromarray((a * 0.92).astype(np.uint8)))
        self.img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
        self.cx, self.cy, self.t0, self.t_out = cx, cy, t0, t_out

    def draw(self, canvas, t):
        if t < self.t0 or t > self.t_out + 0.18:
            return
        p = c01((t - self.t0) / 0.14)
        sc = 2.3 - 1.3 * e_in_cubic(p)
        a = c01(p * 2.2)
        sx = sy = 0
        if p >= 1 and t - self.t0 < 0.30:
            k = (t - self.t0 - 0.14) / 0.16
            sx = int(9 * math.sin(k * 30) * (1 - k))
            sy = int(6 * math.cos(k * 26) * (1 - k))
        if t > self.t_out:
            a *= 1 - (t - self.t_out) / 0.18
        img = self.img
        if abs(sc - 1) > 0.01:
            img = img.resize((int(img.width * sc), int(img.height * sc)), Image.BICUBIC)
        img = with_alpha(img, a)
        canvas.alpha_composite(img, (int(self.cx - img.width / 2 + sx),
                                     int(self.cy - img.height / 2 + sy)))


class CommentCard:
    """A comment bubble that types itself. `lines` = [(label, value, t_type)]:
    the bold label appears with the line, the value types out at ~22 cps
    with a blinking caret. Pops in at t0; send button pulses at t_send."""

    def __init__(self, lines, cx, top, t0, t_send=99, t_out=99, w=900, prefilled=0):
        self.lines, self.cx, self.top = lines, cx, top
        self.t0, self.t_send, self.t_out, self.w = t0, t_send, t_out, w
        self.prefilled = prefilled
        h = 96 + 62 * len(lines)
        base, (ox, oy) = rounded_card(w, h, 36, (255, 255, 255, 250))
        d = ImageDraw.Draw(base)
        d.ellipse((ox + 28, oy + 20, ox + 92, oy + 84), fill=CYAN)            # avatar
        d.ellipse((ox + 48, oy + 30, ox + 72, oy + 54), fill=WHITE)
        d.pieslice((ox + 38, oy + 56, ox + 82, oy + 100), 180, 360, fill=WHITE)
        d.text((ox + 112, oy + 30), "Add a comment...", font=font(POP, 34), fill=GREY)
        pill = "e.g."
        d.rounded_rectangle((ox + w - 120, oy + 26, ox + w - 30, oy + 70), 22, fill=GOLD)
        d.text((ox + w - 75, oy + 48), pill, font=font(POP, 28), fill=NAVY, anchor="mm")
        self.base, self.ox, self.oy, self.h = base, ox, oy, h

    def draw(self, canvas, t):
        if t < self.t0 or t > self.t_out + 0.2:
            return
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        ox, oy = self.ox, self.oy
        fl, fv = font(POP, 38), font(POP_IT, 38)
        caret = None
        for i, (label, value, tt) in enumerate(self.lines):
            y = oy + 92 + 62 * i
            if i >= self.prefilled and t < tt:
                continue
            d.text((ox + 40, y), label, font=fl, fill=NAVY)
            lw = d.textlength(label + " ", font=fl)
            n = len(value) if i < self.prefilled else int(max(0, t - tt - 0.12) * 22)
            shown = value[:n]
            d.text((ox + 40 + lw, y), shown, font=fv, fill=RED)
            if n < len(value) or i == len(self.lines) - 1:
                caret = (ox + 44 + lw + d.textlength(shown, font=fv), y)
        if caret and int(t * 3) % 2 == 0:
            d.rectangle((caret[0], caret[1] + 6, caret[0] + 5, caret[1] + 46), fill=NAVY)
        # send button (paper plane) bottom-right, pulses at t_send
        bx, by = ox + self.w - 76, oy + self.h - 52
        k = 1.0
        if t >= self.t_send:
            k = 1 + 0.35 * math.sin(math.pi * c01((t - self.t_send) / 0.35))
        r = 30 * k
        d.ellipse((bx - r, by - r, bx + r, by + r),
                  fill=GREEN if t >= self.t_send else NAVY)
        d.polygon([(bx - 15 * k, by - 14 * k), (bx + 18 * k, by), (bx - 15 * k, by + 14 * k),
                   (bx - 8 * k, by)], fill=WHITE)
        p = (t - self.t0) / 0.38
        sc = 0.7 + 0.3 * e_out_back(p, 1.6)
        a = c01(p * 3)
        if t > self.t_out:
            q = e_in_cubic((t - self.t_out) / 0.2)
            sc *= 1 - 0.2 * q
            a *= 1 - q
        if abs(sc - 1) > 0.005:
            img = img.resize((int(img.width * sc), int(img.height * sc)), Image.BICUBIC)
        canvas.alpha_composite(with_alpha(img, a),
                               (int(self.cx - img.width / 2),
                                int(self.top - self.oy * sc)))


class LivePill:
    """Red 'LIVE NOW' pill: pops in, white dot pulses with an expanding ring."""

    def __init__(self, text, cx, cy, t0, t_out=99, size=40):
        f = font(POP, size)
        tw = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(text, font=f)
        self.w, self.h = int(tw + 110), int(size * 1.9)
        self.text, self.f = text, f
        self.cx, self.cy, self.t0, self.t_out = cx, cy, t0, t_out

    def draw(self, canvas, t):
        if t < self.t0 or t > self.t_out + 0.18:
            return
        w, h = self.w, self.h
        img = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((40, 40, 40 + w, 40 + h), h // 2, fill=RED)
        dx, dy = 40 + h * 0.55, 40 + h / 2
        ph = ((t - self.t0) % 0.8) / 0.8
        rr = 10 + 26 * ph
        d.ellipse((dx - rr, dy - rr, dx + rr, dy + rr), outline=(255, 255, 255, int(200 * (1 - ph))),
                  width=4)
        d.ellipse((dx - 11, dy - 11, dx + 11, dy + 11), fill=WHITE)
        d.text((40 + h * 0.55 + 30, dy), self.text, font=self.f, fill=WHITE, anchor="lm")
        p = (t - self.t0) / 0.3
        sc = e_out_back(p, 2.2)
        a = c01(p * 3)
        if t > self.t_out:
            a *= 1 - (t - self.t_out) / 0.18
        if sc < 0.02:
            return
        img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))), Image.BICUBIC)
        canvas.alpha_composite(with_alpha(img, a), (int(self.cx - img.width / 2),
                                                    int(self.cy - img.height / 2)))


class Confetti:
    """Deterministic confetti: n flakes drop from above the frame with sway
    and tumble (the tumble is a cosine squash of each flake's height)."""

    def __init__(self, t0, dur=2.4, n=90, seed=7, x_range=(0, W), y_max=1100):
        r = random.Random(seed)
        cols = [GOLD, CYAN, GREEN, RED, NAVY, WHITE]
        self.f = [dict(x=r.uniform(*x_range), d=r.uniform(0, 0.6), v=r.uniform(520, 900),
                       sw=r.uniform(20, 60), sf=r.uniform(2, 5), ph=r.uniform(0, 6.3),
                       tr=r.uniform(4, 11), w=r.uniform(14, 24), h=r.uniform(8, 14),
                       rot=r.uniform(0, 180), c=r.choice(cols)) for _ in range(n)]
        self.t0, self.dur, self.y_max = t0, dur, y_max

    def draw(self, canvas, t):
        if t < self.t0 or t > self.t0 + self.dur + 0.6:
            return
        d = ImageDraw.Draw(canvas)
        for f in self.f:
            u = t - self.t0 - f["d"]
            if u < 0:
                continue
            y = -40 + f["v"] * u
            if y > self.y_max + 200:
                continue
            fade = c01((self.y_max + 200 - y) / 200)
            x = f["x"] + f["sw"] * math.sin(f["sf"] * u + f["ph"])
            hh = f["h"] * abs(math.cos(f["tr"] * u + f["ph"])) + 1.5
            a = math.radians(f["rot"] + 90 * u)
            ca, sa = math.cos(a), math.sin(a)
            pts = [(x + px * ca - py * sa, y + px * sa + py * ca)
                   for px, py in ((-f["w"] / 2, -hh / 2), (f["w"] / 2, -hh / 2),
                                  (f["w"] / 2, hh / 2), (-f["w"] / 2, hh / 2))]
            d.polygon(pts, fill=f["c"][:3] + (int(255 * fade),))


def player_overlay(title):
    """PhotoCard overlay -> video-player look: darken, big play button,
    title chip, empty progress track (the fill is drawn per frame)."""
    def deco(card, b, tw, th):
        sh = Image.new("RGBA", (tw, th), (8, 6, 50, 110))
        card.alpha_composite(sh, (b, b))
        d = ImageDraw.Draw(card)
        cx, cy = b + tw // 2, b + th // 2 - 10
        d.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), fill=(255, 255, 255, 235))
        d.polygon([(cx - 22, cy - 36), (cx + 40, cy), (cx - 22, cy + 36)], fill=RED)
        f = font(POP, 40)
        tl = d.textlength(title, font=f)
        d.rounded_rectangle((b + 26, b + 24, b + 26 + tl + 44, b + 24 + 64), 32, fill=GOLD)
        d.text((b + 48, b + 56), title, font=f, fill=NAVY, anchor="lm")
        d.rounded_rectangle((b + 30, b + th - 40, b + tw - 30, b + th - 28), 6,
                            fill=(255, 255, 255, 90))
    return deco


# ------------------------------------------------------------- the spec
def strokes_layer(strokes, t):
    """Draw Stroke objects at 2x then downsample -> anti-aliased RGBA."""
    live = [s for s in strokes if s.t0 <= t <= s.t_out + 0.2]
    if not live:
        return None
    big = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(big)
    for s in live:
        s.draw(d2, t)
    return big.resize((W, H), Image.BOX)


def head_out(cam0, HT, HX):
    """Head-top (x, y) in OUTPUT space for the segment's first camera key."""
    z, cx, cy = cam0[1:]
    hw, hh = W / (2 * z), H / (2 * z)
    cx = min(max(cx, hw), W - hw)
    cy = min(max(cy, hh), H - hh)
    return 540 + (HX - cx) * z, 960 + (HT - cy) * z


def spec(seg, HT, HX):
    """Return the FX dict for segment `seg`. HT/HX = head top / centre-x in
    the clean frame. Times are LOCAL to the segment (assembled transcript
    minus the segment start; starts 0 2.66 4.08 6.34 7.84 9.44 11.26 13.92)."""
    S = {"cam": [(0, 1.0, 540, 960)], "behind": [], "bstrokes": [], "front": [],
         "fstrokes": [], "par": None, "vin": None, "vout": False}
    # wall-side camera: centre him a little and push in so the wall above
    # and to the right of his head is the stage
    def cam(z, dy=330, dx=0):
        return (z, HX + 90 + dx, HT + dy)

    if seg == 0:   # "finally, 190 invitation round is happening now."  (2.66)
        # IMAGE BEHIND: Parliament House card rises behind him on frame 1;
        # 190 slams onto it on "190"; INVITATION ROUND lands on "invitation";
        # LIVE NOW pill on "happening now". Parallax push-in, whip out.
        S["cam"] = [(0,) + cam(1.08, 360), (2.66,) + cam(1.14, 360)]
        hx, ht = head_out(S["cam"][0], HT, HX)
        S["par"] = [(0, 1.0), (2.66, 1.06)]
        mid = (hx + 540) / 2 + 40
        S["behind"] = [
            PhotoCard(os.path.join(PHOTOS, "parliament_raw.jpg"), 800, 330, mid, ht + 215,
                      0.0, rot=-3, focus=(0.5, 0.55), drift=(-22, -6)),
            Word("190", 210, GOLD, POP_IT, cx=mid + 30, bottom=ht - 10, t_in=0.66, t_out=99,
                 stagger=0.07, enter="slam", shadow=NAVY, depth=14, dur_in=0.22, drift=(-22, -6)),
        ]
        inv = Word("INVITATION", 70, WHITE, POP, cx=835, bottom=ht + 250, t_in=1.36,
                   t_out=99, stagger=0.02, enter="rise", track=-2, dur_in=0.24)
        rnd = Word("ROUND", 70, WHITE, POP, cx=835, bottom=ht + 345, t_in=1.62,
                   t_out=99, stagger=0.03, enter="rise", track=-2, dur_in=0.24)
        S["front"] = [Highlight(inv, RED, 1.28, seed=4), inv, Highlight(rnd, NAVY, 1.54, seed=5),
                      rnd, LivePill("LIVE NOW", 835, ht + 450, 2.06)]
        S["vout"] = True

    elif seg == 1:  # "If you have received your invitation,"  (1.42)
        S["vin"] = 0.0
        S["cam"] = [(0,) + cam(1.22, 300), (1.42,) + cam(1.26, 300)]
        hx, ht = head_out(S["cam"][0], HT, HX)
        S["front"] = [NotifCard("Invitation received", "Subclass 190  ·  Skilled Nominated",
                                540, 228, 0.30)]
        S["fstrokes"] = [tick(860, ht + 120, 90, 0.92, GREEN, width=16, seed=11)]

    elif seg == 2:  # "you can contact our team for visa lodgment."  (2.26)
        # IMAGE BEHIND: the user's screenshot of the 190 visa page header rises
        # behind his head on frame 1; 'contact our team!' is written on the
        # right wall; VISA LODGMENT stamp slams ONTO the visa page on "visa".
        S["cam"] = [(0,) + cam(1.15, 330, -60), (2.26,) + cam(1.19, 330, -60)]
        hx, ht = head_out(S["cam"][0], HT, HX)
        S["par"] = [(0, 1.0), (2.26, 1.04)]
        S["behind"] = [PhotoCard(os.path.join(PHOTOS, "visa190_screenshot.png"), 760, 291, 540,
                                 ht + 120, 0.0, rot=-2, focus=(0.5, 0.5), drift=(-14, 0))]
        S["front"] = [Marker("contact", 88, NAVY, 830, ht + 250, 0.30, dur=0.25, rot=-4),
                      Marker("our team!", 88, NAVY, 840, ht + 350, 0.70, dur=0.25, rot=-4),
                      Stamp(["VISA", "LODGMENT"], RED, 830, ht + 60, 1.50, rot=-9, size=74,
                            bg=(255, 255, 255, 235))]
        S["fstrokes"] = [Stroke(squiggle(690, 990, ht + 410, 9, 4), 1.0, 0.25, GOLD, 11, seed=21)]

    elif seg == 3:  # "And if you have received an invitation,"  (1.50)
        # TEXT BEHIND: INVITED? slams behind his head; hand-drawn envelope
        S["vin"] = 0.0
        S["cam"] = [(0,) + cam(1.06, 360), (1.50,) + cam(1.10, 360)]
        hx, ht = head_out(S["cam"][0], HT, HX)
        S["par"] = [(0, 1.0), (1.50, 1.04)]
        S["behind"] = [Word("INVITED?", 180, NAVY, POP_IT, cx=540, bottom=ht + 70,
                            t_in=0.62, t_out=99, stagger=0.04, enter="slam", shadow=GOLD,
                            depth=13, track=-6, dur_in=0.2)]
        ex, ey = 880, ht + 330
        env = [(ex - 110, ey - 70), (ex + 110, ey - 74), (ex + 112, ey + 72), (ex - 108, ey + 74),
               (ex - 110, ey - 70), (ex, ey + 6), (ex + 110, ey - 74)]
        S["fstrokes"] = [Stroke(env, 0.95, 0.4, RED, 11, smooth=False, seed=31)]

    elif seg == 4:  # "please comment your occupation"  (1.60)
        S["cam"] = [(0,) + cam(1.12, 330), (1.60,) + cam(1.16, 330)]
        S["front"] = [CommentCard([("Occupation:", "Civil Engineer", 1.0),
                                   ("Points:", "85", 99)], 540, 222, 0.30)]

    elif seg == 5:  # "and points below in the comment section."  (1.82)
        S["cam"] = [(0,) + cam(1.16, 330), (1.82,) + cam(1.10, 330)]
        hx, ht = head_out(S["cam"][0], HT, HX)
        S["front"] = [CommentCard([("Occupation:", "Civil Engineer", 0),
                                   ("Points:", "85", 0.20)], 540, 222, -1.0, t_send=1.36,
                                  prefilled=1),
                      Marker("below!", 110, RED, 860, ht + 260, 0.50, dur=0.25, rot=-6)]
        S["fstrokes"] = arrow_strokes(860, ht + 340, 900, ht + 640, 0.62, RED, bend=-0.3,
                                      width=13, seed=51)

    elif seg == 6:  # "Congrats to all who have received these invites,"  (2.66)
        S["cam"] = [(0,) + cam(1.06, 360), (2.66,) + cam(1.12, 360)]
        hx, ht = head_out(S["cam"][0], HT, HX)
        S["par"] = [(0, 1.0), (2.66, 1.06)]
        mid = (hx + 540) / 2 + 40
        S["behind"] = [
            PhotoCard(os.path.join(PHOTOS, "fireworks_raw.jpg"), 800, 330, mid, ht + 215,
                      0.0, rot=3, focus=(0.5, 0.3), drift=(-20, -4)),
            Word("CONGRATS!", 108, GOLD, POP_IT, cx=mid, bottom=ht - 25, t_in=0.06, t_out=99,
                 stagger=0.04, enter="slam", shadow=NAVY, depth=12, dur_in=0.22, drift=(-20, -4)),
        ]
        S["front"] = [Confetti(0.10, dur=2.4, n=110, seed=61),
                      Marker("to all", 80, NAVY, 850, ht + 260, 1.40, dur=0.25, rot=-4),
                      Marker("invitees!", 80, RED, 860, ht + 360, 1.62, dur=0.3, rot=-4)]
        S["vout"] = True

    elif seg == 7:  # "and we will come up with a detailed video very soon."  (2.64)
        # IMAGE BEHIND as a video-player card: Harbour Bridge thumbnail,
        # play button, progress bar filling; COMING SOON on "very soon".
        S["vin"] = 0.0
        S["cam"] = [(0,) + cam(1.06, 360), (2.64,) + cam(1.12, 360)]
        hx, ht = head_out(S["cam"][0], HT, HX)
        S["par"] = [(0, 1.0), (2.64, 1.05)]
        mid = (hx + 540) / 2 + 40
        S["behind"] = [PhotoCard(os.path.join(PHOTOS, "harbour_raw.jpg"), 800, 330, mid,
                                 ht + 215, 0.90, rot=0, focus=(0.5, 0.5), drift=(-18, 0),
                                 overlay=player_overlay("DETAILED VIDEO"),
                                 progress=(1.2, 2.6))]
        S["front"] = [Stamp(["COMING", "SOON"], NAVY, 850, ht + 380, 2.02, rot=-7, size=70)]
    else:
        return None
    return S


SEGS = [0, 1, 2, 3, 4, 5, 6, 7]
VEL_N_OUT, VEL_N_IN = 5, 6      # frames of whip either side of a velocity cut


# ------------------------------------------------------------- renderer
def needs_matte(S):
    return bool(S["behind"] or S["bstrokes"] or S["par"])


def compose(src, cut, S, t, n_frames):
    """One output frame."""
    z, cx, cy = keyed(S["cam"], t)
    # velocity ramps multiply the camera zoom and add radial blur
    vz, blur = 1.0, 0.0
    dur = n_frames / FPS
    if S["vout"] and t > dur - VEL_N_OUT / FPS:
        q = e_in_expo((t - (dur - VEL_N_OUT / FPS)) / (VEL_N_OUT / FPS))
        vz, blur = 1 + 0.32 * q, 0.16 * q
    if S["vin"] is not None and S["vin"] <= t < S["vin"] + VEL_N_IN / FPS:
        q = 1 - e_out_expo((t - S["vin"]) / (VEL_N_IN / FPS))
        vz, blur = 1 + 0.32 * q, 0.16 * q
    zz = z * vz
    out = cam_xform(src, zz, cx, cy).convert("RGBA")
    if cut is not None:
        plate = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for b in S["behind"]:
            b.draw(plate, t)
        sl = strokes_layer(S["bstrokes"], t)
        if sl is not None:
            plate.alpha_composite(sl)
        par = keyed(S["par"], t)[0] if S["par"] else 1.0
        if plate.getbbox() or abs(par - 1) > 0.002:
            out.alpha_composite(plate)
            fg = cam_xform(cut, zz, cx, cy, extra=par, ax=W / 2, ay=H * 0.86)
            out.alpha_composite(fg)
    for m in S["front"]:
        m.draw(out, t)
    sl = strokes_layer(S["fstrokes"], t)
    if sl is not None:
        out.alpha_composite(sl)
    out = out.convert("RGB")
    if blur > 0:
        out = zoom_blur(out, blur)
    return out


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


def head_top(sess, img):
    """(HT, HX): head-top y and the head's centre x (mean x of the top 120
    matte rows) in the clean frame."""
    from rembg import remove
    a = np.asarray(remove(img, session=sess).getchannel("A")) > 128
    rows = np.where(a.any(1))[0]
    if not len(rows):
        return 600, 540
    ht = int(rows[0])
    xs = np.where(a[ht:ht + 120].any(0))[0]
    return ht, int(xs.mean())


def bake(seg, preview_times=None):
    from rembg import new_session, remove
    sess = new_session("u2net_human_seg")
    src_mp4 = os.path.join(ORIGDIR, f"seg_{seg:02d}.mp4")
    tmp = os.path.join(REEL, "work", f"fx_tmp_{seg}")
    shutil.rmtree(tmp, ignore_errors=True)
    fdir, odir = os.path.join(tmp, "f"), os.path.join(tmp, "o")
    os.makedirs(fdir)
    os.makedirs(odir)
    run(["-i", src_mp4, os.path.join(fdir, "f_%05d.png")])
    files = sorted(os.listdir(fdir))
    first = Image.open(os.path.join(fdir, files[0])).convert("RGB")
    HT, HX = head_top(sess, first)
    S = spec(seg, HT, HX)
    mat = needs_matte(S)
    n = len(files)
    idxs = range(n) if preview_times is None else [min(n - 1, int(t * FPS)) for t in preview_times]
    tiles = []
    for k, i in enumerate(idxs):
        fn = files[i]
        src = Image.open(os.path.join(fdir, fn)).convert("RGB")
        cut = None
        if mat:
            cut = remove(src, session=sess)
            cut.putalpha(cut.getchannel("A").filter(ImageFilter.GaussianBlur(1.2)))
        frame = compose(src, cut, S, i / FPS, n)
        if preview_times is None:
            frame.save(os.path.join(odir, fn))
            if (k + 1) % 30 == 0 or k + 1 == n:
                print(f"  seg {seg}: {k + 1}/{n}", flush=True)
        else:
            tiles.append(frame)
    if preview_times is not None:
        os.makedirs(os.path.join(REEL, "check"), exist_ok=True)
        sheet = Image.new("RGB", (W * len(tiles), H))
        for i, im in enumerate(tiles):
            sheet.paste(im, (W * i, 0))
        dest = os.path.join(REEL, "check", f"fx_seg{seg:02d}.jpg")
        sheet.resize((sheet.width // 4, sheet.height // 4)).save(dest, quality=88)
        shutil.rmtree(tmp, ignore_errors=True)
        print("wrote", dest, "HT", HT, "HX", HX)
        return
    audio = os.path.join(tmp, "a.aac")
    run(["-i", src_mp4, "-vn", "-c:a", "copy", audio])
    out = os.path.join(tmp, "out.mp4")
    run(["-framerate", str(FPS), "-i", os.path.join(odir, "f_%05d.png"), "-i", audio,
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
         "-crf", "17", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-color_range", "tv",
         "-c:a", "copy", "-video_track_timescale", "90000", out])
    shutil.copy2(out, os.path.join(SEGDIR, f"seg_{seg:02d}.mp4"))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"baked seg {seg} (HT={HT}, matte={mat})", flush=True)


PREVIEW_T = {0: (0.3, 1.0, 1.7, 2.4), 1: (0.05, 0.8, 1.2), 2: (0.9, 1.75, 2.1),
             3: (0.05, 0.9, 1.4), 4: (0.6, 1.5), 5: (0.5, 1.0, 1.6), 6: (0.4, 1.2, 2.0),
             7: (0.05, 1.3, 2.0, 2.5)}

if __name__ == "__main__":
    args = sys.argv[1:]
    segs = [int(a) for a in args if a.isdigit()] or SEGS
    prev = "--preview" in args
    jobs = int(os.environ.get("FX_JOBS", "3"))
    if jobs <= 1 or len(segs) == 1:
        for s in segs:
            bake(s, PREVIEW_T.get(s, (0.5,)) if prev else None)
    else:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            list(ex.map(bake, segs, [PREVIEW_T.get(s, (0.5,)) if prev else None for s in segs]))
