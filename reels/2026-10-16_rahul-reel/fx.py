"""Per-segment FX pass for the Rahul NSW-unit-group reel.

Brief (user, 2026-10-16): kinetic text, text behind subject, image behind
subject, zoom-ins to different parts, scribble / hand-drawn animations,
velocity edits, parallax motion. None of these exist as shared pipeline
steps, so -- like 2026-10-12_tushar-fast/text_behind.py -- this bakes them
into work/segments/seg_XX.mp4 in place, AFTER build_base.py and BEFORE
insert_broll.py. Clean copies live in work/segments_orig/ and every run
starts from those, so re-running is idempotent.

Per frame, layers bottom -> top:
    1. footage, through a virtual CAMERA (zoom + focus point, cosine-eased
       keyframes) -> "zoom ins to different parts" (face, off-centre thirds)
    2. BEHIND plates: kinetic glyph words, photo cards, hand-drawn strokes
       that live on the wall (screen-space with their own parallax drift)
    3. rembg u2net_human_seg CUTOUT of Rahul, through the same camera times
       an extra scale about his desk line -> PARALLAX (he moves at a
       different rate than the plates and the wall). Scaling the cutout UP
       about a point inside him always covers his original silhouette, so
       no clean plate / inpainting is needed.
    4. FRONT scribbles: marker handwriting written on left->right, boiling
       hand-drawn strokes (circles, arrows, ticks, magnifier, gear, list)
    5. VELOCITY: whip-zoom ramps with a radial zoom blur on the frames
       either side of selected cuts (out: accelerate in, in: decelerate)

Layout is relative to HT, the head-top y of the segment's first frame
(probed by rembg at bake time), so plates tuck behind his head correctly in
every segment even though he leans in and out across the take.

    python fx.py            # all segments in SPEC
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
                 focus=(0.5, 0.6), drift=(-20, 0), label=None):
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


def spec(seg, HT):
    """Return a dict for segment `seg`. HT = head-top y in the clean frame.
    Times are LOCAL to the segment. Word times are from
    work/assembled.transcript.json minus the segment's start."""
    S = {"cam": [(0, 1.0, 540, 960)], "behind": [], "bstrokes": [], "front": [],
         "fstrokes": [], "par": None, "vin": None, "vout": False}
    hb = HT + 120          # glyph bottom: lowest part tucked behind his head

    if seg == 0:   # "Your occupation is not on the NSW skills list?"  (dur 2.62)
        # IMAGE BEHIND: Sydney card rises from behind his head on frame 1;
        # kinetic NSW / SKILLS LIST lands on it; PARALLAX: card drifts left,
        # he grows toward camera, wall pushes in slowly.
        S["cam"] = [(0, 1.0, 540, 900), (2.62, 1.06, 540, 860)]
        S["par"] = [(0, 1.0), (2.62, 1.055)]
        S["behind"] = [
            PhotoCard(os.path.join(PHOTOS, "sydney_raw.jpg"), 860, 480, 540, HT + 250,
                      0.0, rot=-3, focus=(0.55, 0.75), drift=(-26, -6)),
            Word("NSW", 210, GOLD, POP_IT, cx=540, bottom=HT - 110, t_in=1.55, t_out=99,
                 stagger=0.06, enter="slam", shadow=NAVY, depth=12, dur_in=0.22, drift=(-26, -6)),
            Word("SKILLS LIST", 104, WHITE, POP, cx=540, bottom=HT + 10, t_in=1.80, t_out=99,
                 stagger=0.025, enter="rise", shadow=NAVY, depth=7, track=-2, drift=(-26, -6)),
        ]
        S["fstrokes"] = [Stroke([(860, HT + 120), (880, HT + 10), (980, HT - 20), (1020, HT + 70),
                                 (950, HT + 150), (935, HT + 240)], 2.12, 0.26, RED, 16, seed=21),
                         Stroke([(934, HT + 320), (936, HT + 336)], 2.36, 0.05, RED, 20,
                                smooth=False, seed=22)]
        S["vout"] = True

    elif seg == 1:  # "but please check carefully."  (dur 1.64) -> tight on his face
        S["vin"] = 0.0
        S["cam"] = [(0, 1.32, 520, HT + 230), (1.64, 1.38, 520, HT + 230)]
        S["front"] = [Marker("CHECK", 150, NAVY, 540, 300, 0.60, dur=0.25, rot=-4),
                      Marker("carefully!", 112, RED, 600, 450, 1.05, dur=0.3, rot=-4)]
        S["fstrokes"] = magnifier(905, 690, 90, 0.85, NAVY, seed=31) + [
            Stroke(squiggle(330, 860, 545, 12, 5), 1.30, 0.28, GOLD, 11, seed=33)]

    elif seg == 3:  # "They don't publish individual occupation codes. What they do is" (3.98)
        # TEXT BEHIND: an ANZSCO-style 6-digit code (225113 = Marketing
        # Specialist, the example he gives next) drops in on "individual",
        # gets scribbled out on "codes" -- the scribble is ALSO behind him.
        S["cam"] = [(0, 1.0, 540, 960), (3.98, 1.09, 530, HT + 300)]
        S["behind"] = [
            Marker("occupation code", 84, NAVY, 540, HT - 330, 1.20, dur=0.35, rot=-2,
                   t_out=2.58),
            Word("225113", 250, NAVY, POP_IT, cx=540, bottom=hb, t_in=1.27, t_out=3.10,
                 stagger=0.05, enter="drop", shadow=GOLD, depth=14, track=-8, exit="up"),
        ]
        S["bstrokes"] = [Stroke(zigzag(150, 930, HT - 140, HT + 30, 9), 2.62, 0.30, RED, 15,
                                t_out=3.10, smooth=False, seed=41)]
        S["front"] = [Marker("NOT published!", 96, RED, 540, HT - 340, 2.70, dur=0.3, rot=-4,
                             t_out=3.10)]
        S["vout"] = True

    elif seg == 4:  # "they publish unit group."  (1.80)
        # UNIT stays BEHIND (it clears his head, so it reads); GROUP sat
        # behind his head and lost its O -> FRONT, above his head, highlighted.
        S["vin"] = 0.0
        S["cam"] = [(0, 1.0, 540, 960), (1.10, 1.0, 540, 960), (1.40, 1.12, 530, HT + 260),
                    (1.80, 1.14, 530, HT + 260)]
        S["behind"] = [
            Word("UNIT", 230, GOLD, POP_IT, cx=540, bottom=HT - 230, t_in=1.12, t_out=99,
                 stagger=0.05, enter="slam", shadow=NAVY, depth=14, dur_in=0.2),
        ]
        group = Word("GROUP", 170, NAVY, POP, cx=540, bottom=HT - 20, t_in=1.40, t_out=99,
                     stagger=0.035, enter="slam", shadow=None, depth=0, dur_in=0.2)
        S["front"] = [Highlight(group, GOLD, 1.32, seed=44), group]
        S["bstrokes"] = [Stroke(ellipse_pts(540, HT - 230, 470, 260, seed=43), 1.42, 0.34, RED,
                                13, seed=43)]

    elif seg == 5:  # "So for example,"  (0.98) -> off-centre third framing
        S["cam"] = [(0, 1.24, 660, HT + 300), (0.98, 1.28, 660, HT + 300)]
        S["front"] = [Marker("e.g.", 150, RED, 210, 520, 0.30, dur=0.25, rot=-8)]
        S["fstrokes"] = [Stroke(squiggle(110, 320, 620, 9, 3), 0.45, 0.22, NAVY, 11, seed=51)]

    elif seg == 6:  # "for marketing they have published a unit group and under that" (3.58)
        # MARKETING was behind his head and lost letters -> FRONT above his
        # head on a cyan highlighter swipe. PARALLAX kept: the word + box
        # drift left while he grows toward camera.
        S["cam"] = [(0, 1.0, 540, 960), (3.58, 1.05, 540, 920)]
        S["par"] = [(0, 1.0), (3.58, 1.06)]
        # user v3: the unit group's real name, not just "MARKETING"
        items, u = title_stack(["ADVERTISING AND", "MARKETING", "PROFESSIONALS"], NAVY, CYAN, HT,
                               0.22, drift=(-24, 0), seed=62, size=76, gap=1.14)
        S["front"] = items + [Marker("= UNIT GROUP", 84, NAVY, 540, max(220, u[1] - 100), 2.05,
                                     dur=0.35, rot=-3)]
        S["fstrokes"] = [Stroke(box_pts(u), 1.98, 0.5, RED, 12, smooth=False, seed=61,
                                drift=(-24, 0))]
        S["fstrokes"] += arrow_strokes(930, HT - 120, 980, HT + 330, 2.95, RED, bend=-0.35,
                                       seed=63)

    elif seg == 7:  # "there is a marketing specialist,"  (1.52) -> he shifts right
        S["cam"] = [(0, 1.15, 430, HT + 330), (1.52, 1.18, 425, HT + 330)]
        S["front"] = [Marker("Marketing", 92, NAVY, 40, 470, 0.40, dur=0.3, rot=-4, anchor="l"),
                      Marker("Specialist", 92, NAVY, 40, 580, 0.80, dur=0.3, rot=-4, anchor="l")]
        S["fstrokes"] = (arrow_strokes(560, 230, 230, 380, 0.08, RED, bend=0.2, seed=71)
                         + [tick(300, 700, 80, 1.10, GREEN, seed=73)])

    elif seg == 8:  # "content creators as well"  (1.42) -> he shifts left
        S["cam"] = [(0, 1.15, 650, HT + 330), (1.42, 1.18, 655, HT + 330)]
        S["front"] = [Marker("Content", 96, NAVY, 615, 470, 0.08, dur=0.3, rot=4, anchor="l"),
                      Marker("Creator", 96, NAVY, 622, 585, 0.45, dur=0.3, rot=4, anchor="l"),
                      Marker("(Marketing)", 64, RED, 630, 682, 0.70, dur=0.3, rot=4, anchor="l")]
        S["fstrokes"] = (arrow_strokes(520, 230, 820, 370, 0.0, RED, bend=-0.2, seed=81)
                         + [tick(920, 800, 70, 0.95, GREEN, seed=83)])

    elif seg == 9:  # "and there are other marketing occupations as well."  (2.52)
        S["cam"] = [(0, 1.10, 540, 900), (2.52, 1.0, 540, 960)]
        S["front"] = [Marker("+ more", 120, RED, 540, 300, 0.85, dur=0.3, rot=-5)]
        S["fstrokes"] = [Stroke(squiggle(360 + 120 * i, 440 + 120 * i, 420, 8, 2),
                                1.30 + 0.18 * i, 0.16, NAVY, 11, seed=91 + i) for i in range(3)] + [
            Stroke(ellipse_pts(540, 360, 300, 130, seed=95), 1.6, 0.35, GOLD, 11, seed=95)]
        S["vout"] = True

    elif seg == 10:  # "Same with the engineers. So they have published"  (3.04)
        S["vin"] = 0.0
        S["cam"] = [(0, 1.0, 540, 960), (0.95, 1.0, 540, 960), (1.25, 1.10, 540, HT + 300),
                    (3.04, 1.13, 540, HT + 300)]
        # user v3: the unit group's name + "= UNIT GROUP" like the marketing beat
        items, u = title_stack(["OTHER ENGINEERING", "PROFESSIONALS"], NAVY, GREEN, HT, 0.95,
                               path=POP_IT, enter="slam", seed=102)
        S["front"] = items + [Marker("= UNIT GROUP", 84, NAVY, 540, max(220, u[1] - 100), 1.55,
                                     dur=0.35, rot=-3)]
        gy = HT + 160            # gears beside his head, clear of the title stack
        g = gear_pts(900, gy, 80)
        g2 = gear_pts(165, gy + 40, 52, 7)
        S["fstrokes"] = [Stroke(g + [g[0]], 1.30, 0.5, NAVY, 10, smooth=False, seed=101),
                         Stroke(ellipse_pts(900, gy, 30, 30, seed=103), 1.7, 0.2, RED, 10,
                                seed=103),
                         Stroke(g2 + [g2[0]], 1.55, 0.45, CYAN, 9, smooth=False, seed=105)]

    elif seg == 11:  # "other engineering professionals. So under if you will go to that
        #              group, there will be more occupations there."  (6.48)
        # zoom tour: face tight -> eases out and across to free the left wall,
        # where a hand-drawn unit-group box fills with occupation lines.
        S["cam"] = [(0, 1.28, 540, HT + 230), (2.10, 1.30, 540, HT + 230),
                    (2.60, 1.12, 430, HT + 330), (6.48, 1.15, 430, HT + 330)]
        S["front"] = [Marker("UNIT GROUP", 52, NAVY, 212, 300, 3.45, dur=0.3, rot=-2)]
        bx = [(30, 230), (395, 222), (402, 900), (34, 905), (28, 225)]
        S["fstrokes"] = [Stroke(bx, 3.30, 0.4, RED, 11, smooth=False, seed=111)]
        for i in range(3):
            y = 430 + 140 * i
            S["fstrokes"].append(Stroke([(80, y), (98, y + 4)], 4.40 + 0.25 * i, 0.06, NAVY, 16,
                                        smooth=False, seed=113 + i))
            S["fstrokes"].append(Stroke(squiggle(130, 340, y, 7, 3), 4.45 + 0.25 * i, 0.22,
                                        NAVY, 10, seed=117 + i))
        S["front"].append(Marker("more!", 96, RED, 230, 860, 5.36, dur=0.3, rot=-6))
        S["fstrokes"] += arrow_strokes(560, HT + 30, 380, 560, 5.30, GOLD, bend=0.3, seed=121)

    elif seg == 12:  # B-roll covers 0-2.95; footage tail "they have published" (4.36)
        S["vin"] = 2.95
        S["cam"] = [(0, 1.2, 540, HT + 260), (4.36, 1.24, 540, HT + 260)]

    elif seg == 13:  # coaches example (7.54)
        # TEXT BEHIND "COACHES" on "coaches"; then IMAGE BEHIND: the cricket
        # card rises behind him on "cricket"; tennis gets a hand-drawn ball.
        S["cam"] = [(0, 1.0, 540, 960), (3.6, 1.0, 540, 960), (3.95, 1.10, 470, HT + 330),
                    (4.6, 1.10, 470, HT + 330), (5.0, 1.04, 540, 930), (7.54, 1.07, 540, 910)]
        S["par"] = [(0, 1.0), (4.6, 1.0), (7.54, 1.05)]
        S["behind"] = [
            PhotoCard(os.path.join(PHOTOS, "cricket_lords_raw.jpg"), 820, 470, 540, HT + 250,
                      4.66, rot=3, focus=(0.3, 0.55), drift=(-22, -4),
                      label=("CRICKET COACH", 64)),
        ]
        # user v3: the unit group's real name + "= UNIT GROUP"
        coach_front, u = title_stack(["SPORTS COACHES,", "INSTRUCTORS", "AND OFFICIALS"], WHITE,
                                     RED, HT, 0.62, path=POP_IT, enter="drop", t_out=3.70,
                                     seed=132, size=76, gap=1.14)
        coach_ring = [Stroke(box_pts(u), 2.0, 0.45, NAVY, 11, smooth=False, seed=131,
                             t_out=3.70)]
        S["front"] = coach_front + [Marker("= UNIT GROUP", 84, NAVY, 540, max(220, u[1] - 100), 1.95, dur=0.35, rot=-3,
                             t_out=3.70),
                      Marker("Tennis", 96, NAVY, 50, 420, 3.90, dur=0.25, rot=-5, anchor="l",
                             t_out=4.62),
                      Marker("Coach", 96, NAVY, 60, 530, 4.15, dur=0.25, rot=-5, anchor="l",
                             t_out=4.62),
                      Marker("+ other coaches", 66, RED, 540, 225, 6.30, dur=0.35, rot=-3)]
        S["fstrokes"] = [Stroke(ellipse_pts(150, 730, 70, 70, turns=1.0, seed=135), 3.95, 0.25,
                                GREEN, 11, seed=135, t_out=4.62),
                         Stroke([(95, 690), (150, 730), (205, 775)], 4.15, 0.15, WHITE, 8,
                                seed=136, t_out=4.62),
                         tick(400, 600, 64, 4.30, GREEN, seed=137, t_out=4.62),
                         tick(850, HT - 300, 80, 5.25, GREEN, seed=139)] + coach_ring

    elif seg == 14:  # "So if you are one of them, please contact us."  (2.16)
        S["vin"] = 0.0
        S["cam"] = [(0, 1.0, 540, 960), (1.35, 1.0, 540, 960), (1.65, 1.18, 530, HT + 270),
                    (2.16, 1.2, 530, HT + 270)]
        S["front"] = [Marker("that's YOU?", 118, RED, 540, 330, 0.55, dur=0.3, rot=-5)]
        S["fstrokes"] = (arrow_strokes(880, 520, 930, 1000, 1.50, RED, bend=-0.4, width=13,
                                       seed=141)
                         + [Stroke(squiggle(310, 770, 420, 10, 4), 0.85, 0.25, GOLD, 11,
                                   seed=143)])

    elif seg == 15:  # "We can help you to assess your profile."  (2.22)
        S["cam"] = [(0, 1.16, 540, 900), (2.22, 1.0, 540, 960)]
        S["par"] = [(0, 1.04), (2.22, 1.0)]
        S["front"] = [Marker("we can help!", 110, NAVY, 540, 330, 0.30, dur=0.35, rot=-4)]
        S["fstrokes"] = [tick(800, 520, 120, 1.18, GREEN, width=17, seed=151),
                         Stroke(ellipse_pts(540, 330, 360, 120, seed=153), 0.70, 0.35, RED, 11,
                                seed=153)]
        # sparkles
        for i, (x, y) in enumerate([(160, 260), (950, 240), (190, 760)]):
            S["fstrokes"].append(Stroke([(x - 30, y), (x + 30, y)], 1.4 + 0.1 * i, 0.1, GOLD, 9,
                                        smooth=False, seed=155 + i))
            S["fstrokes"].append(Stroke([(x, y - 30), (x, y + 30)], 1.45 + 0.1 * i, 0.1, GOLD, 9,
                                        smooth=False, seed=158 + i))
    else:
        return None
    return S


SEGS = [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
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
    from rembg import remove
    a = np.asarray(remove(img, session=sess).getchannel("A")) > 128
    rows = np.where(a.any(1))[0]
    return int(rows[0]) if len(rows) else 600


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
    HT = head_top(sess, first)
    S = spec(seg, HT)
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
        print("wrote", dest, "HT", HT)
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


PREVIEW_T = {0: (0.3, 1.2, 1.9, 2.5), 1: (0.05, 0.9, 1.5), 3: (1.6, 2.8, 3.5), 4: (0.05, 1.5, 1.75),
             5: (0.6,), 6: (0.8, 2.4, 3.3), 7: (1.3,), 8: (1.3,), 9: (2.0, 2.45),
             10: (0.05, 1.6, 2.6), 11: (1.0, 3.9, 5.8), 12: (3.0, 3.6), 13: (1.0, 2.6, 4.4, 5.6, 7.0),
             14: (0.05, 1.0, 2.0), 15: (0.6, 1.9)}

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
