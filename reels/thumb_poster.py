"""Cutout thumbnails for build_thumbnail.py: "news" (News flash, the house default) and "poster".

What it does differently from the classic frame-grab + small headline:

1. Picks the frame itself (`"at": "auto"`, the default). It scores ~30 frames
   of work/base.mp4: the clean talking head, so never a wipe, B-roll or
   caption. Frames with no clear face, eyes not detected (blink / look-away),
   soft focus or mid-gesture motion blur lose. An explicit number still wins.
2. Cuts the presenter out (rembg u2net_human_seg) and stacks:
   brand-washed blurred background -> huge headline -> presenter (with a white
   sticker outline) -> kicker, sticker, logo chip.
   The headline tucks BEHIND the head (text-behind-subject), and the presenter
   is rescaled/placed so every reel's face lands at the same size and spot,
   whether the take was wide or tight.
3. Keeps the hook inside Instagram's 3:4 profile-grid crop (y 240..1680 of the
   1080x1920 cover). work/thumb_grid_preview.jpg shows both crops side by side.
4. Writes the next-best frames as output/thumbnail_alts/alt_N.jpg so a
   different face can be swapped in without re-running anything.

Headline: `thumbnail.headline` (wrap words in **stars** for gold). If empty, it
falls back to caption_txt.title (un-bolded, emoji stripped) with the last
words accented, so no reel ships a bare frame again.
"""
import json
import os
import re
import shutil
import unicodedata

import numpy as np
from PIL import Image, ImageFilter

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "motion-styles", "fonts")
W, H = 1080, 1920


# ------------------------------------------------------------ frame picking
def _cascades():
    import cv2
    d = cv2.data.haarcascades
    return (cv2.CascadeClassifier(d + "haarcascade_frontalface_default.xml"),
            cv2.CascadeClassifier(d + "haarcascade_eye.xml"))   # open eyes only; the eyeglasses one also fires on closed lids


def score_frames(video, n=30, skip_head=0.6, skip_tail=1.0):
    """Return [(score, t, face)] best first. face = (x, y, w, h) in video px."""
    import cv2
    face_c, eye_c = _cascades()
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    out = []
    for i in range(n):
        t = skip_head + (dur - skip_head - skip_tail) * (i + 0.5) / n
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, a = cap.read()
        cap.set(cv2.CAP_PROP_POS_MSEC, (t + 1 / 15) * 1000)
        ok2, b = cap.read()
        if not (ok and ok2):
            continue
        g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        faces = face_c.detectMultiScale(g, 1.1, 6, minSize=(g.shape[1] // 10, g.shape[1] // 10))
        if len(faces) == 0:
            continue
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        roi = g[y:y + h, x:x + w]
        eyes = eye_c.detectMultiScale(roi[h // 6: h // 2], 1.05, 8, minSize=(w // 9, w // 9))
        sharp = cv2.Laplacian(roi, cv2.CV_64F).var()
        gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)[y:y + h, x:x + w]
        motion = float(np.mean(np.abs(roi.astype(np.int16) - gb.astype(np.int16))))
        centred = 1 - abs((x + w / 2) / g.shape[1] - 0.5) * 2
        out.append({"t": round(t, 3), "face": [int(x), int(y), int(w), int(h)], "eyes": int(min(len(eyes), 2)),
                    "sharp": sharp, "motion": motion, "centred": centred})
    cap.release()
    if not out:
        return []
    ms = np.median([o["sharp"] for o in out]) or 1
    for o in out:
        o["score"] = (1.5 * o["eyes"] + min(o["sharp"] / ms, 1.6) - 0.12 * o["motion"] + 0.5 * o["centred"])
    return sorted(out, key=lambda o: -o["score"])


def pick_distinct(cands, k=3, gap=2.0):
    """Top k candidates at least `gap` seconds apart (alternates should differ)."""
    picked = []
    for c in cands:
        if all(abs(c["t"] - p["t"]) >= gap for p in picked):
            picked.append(c)
        if len(picked) == k:
            break
    return picked


# ------------------------------------------------------------ headline text
_BOLD = {}
for base, start in (("A", 0x1D5D4), ("a", 0x1D5EE), ("0", 0x1D7EC)):   # sans-serif bold
    for i in range(26 if base != "0" else 10):
        _BOLD[chr(start + i)] = chr(ord(base) + i)


def headline_from_title(title):
    """caption_txt.title (unicode bold + emoji) -> plain caps, last words gold."""
    s = "".join(_BOLD.get(ch, ch) for ch in title)
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] in "LNPZ" or ch in "&'")
    s = re.sub(r"\s+", " ", s).strip().upper()
    s = re.split(r"\s*[:—–|]\s*|\s+-\s+", s)[0]          # first clause only
    words = s.split(" ")
    n = 2 if len(words) > 3 else 1
    return " ".join(words[:-n]) + " **" + " ".join(words[-n:]) + "**" if len(words) > 1 else f"**{s}**"


def _accent_html(text):
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r'<span class="g">\1</span>', esc)


# ------------------------------------------------------------ layers
def cutout(frame_png, out_png, outline=9):
    """Presenter RGBA cutout + a white sticker outline baked under it."""
    from rembg import new_session, remove
    src = Image.open(frame_png).convert("RGB")
    cut = remove(src, session=new_session("u2net_human_seg"))
    a = cut.getchannel("A")
    if outline <= 0:                                     # plain cutout (MaxFilter(1) crashes PIL)
        cut.save(out_png)
        rows = np.where(np.array(a).max(axis=1) > 128)[0]
        return int(rows.min()) if len(rows) else 0
    ring = a.filter(ImageFilter.MaxFilter(outline * 2 + 1)).filter(ImageFilter.GaussianBlur(1.2))
    sticker = Image.new("RGBA", cut.size, (255, 255, 255, 0))
    sticker.putalpha(ring)
    Image.alpha_composite(sticker, cut).save(out_png)
    arr = np.array(a)
    rows = np.where(arr.max(axis=1) > 128)[0]
    return int(rows.min()) if len(rows) else 0          # top of hair, video px


def background(frame_png, out_png):
    im = Image.open(frame_png).convert("RGB").resize((W, H), Image.LANCZOS)
    im.filter(ImageFilter.GaussianBlur(14)).save(out_png)


_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:P;font-weight:700;src:url("__FONTS__/Poppins-Bold.ttf")}
@font-face{font-family:P;font-weight:800;src:url("__FONTS__/Poppins-ExtraBold.ttf")}
@font-face{font-family:P;font-weight:900;src:url("__FONTS__/Poppins-Black.ttf")}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden}
#s{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:P,sans-serif;background:#0a0560}
.abs{position:absolute;left:0;top:0}
#bg{width:1080px;height:1920px;opacity:.55}
#wash{width:1080px;height:1920px;background:
  radial-gradient(ellipse 70% 40% at 50% 62%,rgba(0,179,227,.30),rgba(0,179,227,0) 70%),
  linear-gradient(180deg,rgba(10,5,96,.92) 0%,rgba(16,7,150,.55) 45%,rgba(10,5,96,.35) 70%,rgba(10,5,96,.9) 100%)}
#grid{width:1080px;height:1920px;opacity:.6;background-image:
  linear-gradient(rgba(255,255,255,.05) 2px,transparent 2px),linear-gradient(90deg,rgba(255,255,255,.05) 2px,transparent 2px);
  background-size:90px 90px}
#hl{left:50px;width:980px;top:__HLTOP__px;text-align:center;font-weight:900;color:#fff;line-height:.98;
  letter-spacing:-.01em;text-transform:uppercase;text-wrap:balance;text-shadow:0 10px 40px rgba(0,0,0,.45)}
#hl .g{color:#FFC500}
#sub{transform-origin:0 0;filter:drop-shadow(0 30px 40px rgba(0,0,0,.45))}
#kick{left:50%;top:250px;transform:translateX(-50%);background:#FFC500;color:#100796;font-weight:900;font-size:36px;
  letter-spacing:.06em;padding:12px 34px;border-radius:999px;white-space:nowrap;box-shadow:0 10px 26px rgba(0,0,0,.35)}
#stk{background:#E84B37;color:#fff;font-weight:900;font-size:46px;letter-spacing:.04em;padding:14px 34px;border-radius:18px;
  white-space:nowrap;transform:rotate(-6deg);box-shadow:0 14px 30px rgba(0,0,0,.4);border:5px solid #fff}
#fade{left:0;top:1380px;width:1080px;height:540px;background:linear-gradient(180deg,rgba(10,5,96,0),rgba(10,5,96,.88) 70%,#0a0560)}
#logo{left:324px;top:38px;width:432px}
</style></head><body><div id="s">
<img id="bg" class="abs" src="bg.png"><div id="wash" class="abs"></div><div id="grid" class="abs"></div>
<div id="hl" class="abs">__HEADLINE__</div>
<img id="sub" class="abs" src="cut.png"><div id="fade" class="abs"></div>
__KICKER__
__STICKER__
<img id="logo" class="abs" src="logo.png">
</div><script>
const F = __FACE__;                 // face box + hair top in frame px, frame size
Promise.all(["900 100px P", "700 34px P"].map(f => document.fonts.load(f))).then(() => {
// (layout runs after the fonts load so text is measured in Poppins)
const hl = document.getElementById("hl");
// largest size that keeps the headline to <= 3 balanced lines with no overflow
let fs = 180;
for (; fs > 96; fs -= 4) {
  hl.style.fontSize = fs + "px";
  const lines = Math.round(hl.getBoundingClientRect().height / (fs * 0.98));
  if (lines <= 3 && hl.scrollWidth <= 982) break;
}
const r = hl.getBoundingClientRect();
// presenter: face width -> 300px, centred, hair top tucked a quarter into the
// headline's last line (text behind subject) so most of the words still read;
// #fade hides where a wide take's cutout ends above the frame bottom
const base = 1080 / F.W, k = Math.min(2.2 * base, Math.max(0.9 * base, 300 / F.fw));
const fcx = (F.fx + F.fw / 2) * k, hair = F.hair * k;
const tuck = r.bottom - fs * 0.24;
const sub = document.getElementById("sub");
sub.style.width = F.W * k + "px";
sub.style.transform = `translate(${540 - fcx}px,${tuck - hair}px)`;
const stk = document.getElementById("stk");
if (stk) { stk.style.left = "620px"; stk.style.top = Math.min(1500, tuck - hair + (F.fy + F.fh * 1.9) * k) + "px"; }
window.__done = true;
});
</script></body></html>"""


# News flash (house default since 2026-10-28): an editorial breaking-news cover.
# - The sharp photo, punched in on the face, sits above a diagonal edge, with a
#   solid gold block below. The presenter cutout shares the photo's transform,
#   so he lines up with himself, and breaks out over the edge to his chest.
# - Big navy left-aligned headline; **words** are reversed out of navy boxes.
# - The red tab is `sticker`, on the edge. The kicker is a small line under the
#   headline.
# Everything stays inside the 3:4 grid crop (y 240..1680).
_NEWS_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:P;font-weight:700;src:url("__FONTS__/Poppins-Bold.ttf")}
@font-face{font-family:P;font-weight:900;src:url("__FONTS__/Poppins-Black.ttf")}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden}
#s{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:P,sans-serif;background:#FFC500}
.abs{position:absolute;left:0;top:0}
#clip{width:1080px;height:1920px;overflow:hidden;clip-path:polygon(0 0,100% 0,100% 58%,0 66%)}
#photo,#sub{transform-origin:0 0}
#shade{width:1080px;height:1920px;background:linear-gradient(180deg,rgba(10,5,96,.5),rgba(10,5,96,0) 20%)}
#bar{width:1080px;height:1920px;background:#100796;clip-path:polygon(0 66%,100% 58%,100% 59.4%,0 67.4%)}
#sub{filter:drop-shadow(0 24px 30px rgba(0,0,0,.35))}
#gold{width:1080px;height:1920px;background:#FFC500;clip-path:polygon(0 69.5%,100% 66.5%,100% 100%,0 100%)}
#tab{left:60px;top:1180px;background:#E84B37;color:#fff;font-weight:900;font-size:40px;letter-spacing:.08em;padding:10px 28px;
  border-radius:10px;transform:rotate(-3.5deg);box-shadow:0 10px 24px rgba(0,0,0,.3);white-space:nowrap}
#hl{left:60px;width:950px;top:1345px;font-weight:900;color:#100796;line-height:1.12;text-transform:uppercase;text-wrap:balance}
#hl .g{color:#fff;background:#100796;padding:0 16px;border-radius:10px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
#kick{left:60px;font-weight:700;font-size:34px;letter-spacing:.04em;color:#100796;white-space:nowrap}
#site{left:60px;top:1740px;font-weight:700;font-size:30px;letter-spacing:.06em;color:rgba(16,7,150,.75)}
#logo{left:324px;top:38px;width:432px}
</style></head><body><div id="s">
<div id="clip" class="abs"><img id="photo" class="abs" src="photo.png"><div id="shade" class="abs"></div></div>
<div id="bar" class="abs"></div>
<img id="sub" class="abs" src="cut.png"><div id="gold" class="abs"></div>
__STICKER__
<div id="hl" class="abs">__HEADLINE__</div>
__KICKER__
<div id="site" class="abs">WWW.PFECGLOBAL.COM.AU</div>
<img id="logo" class="abs" src="logo.png">
</div><script>
const F = __FACE__;
Promise.all(["900 100px P", "700 34px P"].map(f => document.fonts.load(f))).then(() => {
// (layout runs after the fonts load so text is measured in Poppins)
// punch in so the face is ~380px wide and centred at y 640; photo + cutout share
// the transform, clamped so the photo always covers the frame down to the edge
const k = Math.max(1080 / F.W, 1270 / F.H, 380 / F.fw);
const fcx = (F.fx + F.fw / 2) * k, fcy = (F.fy + F.fh / 2) * k;
const ox = Math.min(0, Math.max(1080 - F.W * k, 540 - fcx));
const oy = Math.min(0, Math.max(1270 - F.H * k, 640 - fcy));
for (const id of ["photo", "sub"]) { const e = document.getElementById(id);
  e.style.width = F.W * k + "px"; e.style.transform = `translate(${ox}px,${oy}px)`; }
// headline: largest size that fits <= 3 lines inside the gold block
const hl = document.getElementById("hl");
let fs = 156;
for (; fs > 64; fs -= 4) {
  hl.style.fontSize = fs + "px";
  const b = hl.getBoundingClientRect(), lines = Math.round(b.height / (fs * 1.12));
  if (lines <= 3 && hl.scrollWidth <= 952 && b.bottom <= 1630) break;
}
const kick = document.getElementById("kick");
if (kick) kick.style.top = hl.getBoundingClientRect().bottom + 14 + "px";
window.__done = true;
});
</script></body></html>"""


def render_poster(frame_png, face, out_jpg, workdir, headline, kicker="", sticker="", logo=None, style="poster"):
    os.makedirs(workdir, exist_ok=True)
    fw, fh = Image.open(frame_png).size
    news = style == "news"
    hair = cutout(frame_png, os.path.join(workdir, "cut.png"), outline=0 if news else 9)
    if news:
        shutil.copy(frame_png, os.path.join(workdir, "photo.png"))
    else:
        background(frame_png, os.path.join(workdir, "bg.png"))
    shutil.copy(logo, os.path.join(workdir, "logo.png"))
    x, y, w, h = face
    html = ((_NEWS_HTML if news else _HTML).replace("__FONTS__", "file:///" + FONT_DIR.replace("\\", "/"))
            .replace("__HLTOP__", "330" if kicker else "270")
            .replace("__HEADLINE__", _accent_html(headline))
            .replace("__KICKER__", f'<div id="kick" class="abs">{_accent_html(kicker)}</div>' if kicker else "")
            .replace("__STICKER__", f'<div id="{"tab" if news else "stk"}" class="abs">{_accent_html(sticker)}</div>'
                     if sticker else "")
            .replace("__FACE__", json.dumps({"W": fw, "H": fh, "fx": x, "fy": y, "fw": w, "fh": h, "hair": hair})))
    page = os.path.join(workdir, "poster.html")
    open(page, "w", encoding="utf-8").write(html)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto("file:///" + page.replace("\\", "/"))
        pg.wait_for_function("window.__done === true")
        pg.evaluate("document.fonts.ready")
        png = os.path.join(workdir, "poster.png")
        pg.screenshot(path=png)
        b.close()
    Image.open(png).convert("RGB").save(out_jpg, quality=93)


def grid_preview(cover_jpg, out_jpg):
    """Cover at feed size next to its Instagram 3:4 grid crop."""
    im = Image.open(cover_jpg)
    full = im.resize((360, 640))
    crop = im.crop((0, 240, 1080, 1680)).resize((360, 480))
    sheet = Image.new("RGB", (760, 660), (235, 235, 240))
    sheet.paste(full, (10, 10))
    sheet.paste(crop, (390, 90))
    sheet.save(out_jpg, quality=90)
