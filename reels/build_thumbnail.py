"""Reel thumbnail: grab a frame from the FINISHED reel_final.mp4 and stamp a
branded kicker/headline card on top (same card grammar as build_captions.py --
navy kicker pill, bold Poppins headline, gold accent word), so every reel ships
with a designed vertical thumbnail instead of an arbitrary frame grab or none
at all.

Architecture: same as build_captions.py -- render ONE transparent HyperFrames
frame (as a PNG, not a video), then a single ffmpeg composite onto the
extracted background frame. No alpha-video roundtrip needed for a still.

Run after build_composite.py (needs output/reel_final.mp4)."""
import os, json, re, shutil, subprocess

from reel_paths import WORK, OUT, REEL, ASSETS_ROOT, PREVIEW, hyperframes_cli  # noqa: E402 -- per-reel folders
from ffmpeg_util import FF, run  # noqa: E402 -- shared ffmpeg wrappers

LOGO = os.path.join(ASSETS_ROOT, "derived", "logo_chip.png")

# Per-reel override via <reel>/content.json -> {"thumbnail": {...}}. Every key
# is optional: with no override you still get a branded still (background
# frame + the persistent logo, composited fresh here) -- kicker/headline just
# add an on-brand hook on top.
DEFAULT_THUMB = {
    "style": "news",     # "news" (News flash, house default since 2026-10-28:
                          # sharp photo over a diagonal gold block, headline below)
                          # or "poster" (cutout, big headline behind the head), both
                          # in thumb_poster.py; "classic" = frame grab + small
                          # top-left headline (every reel before 2026-10-28)
    "at": "auto",    # seconds into the main content, or "auto" (poster picks the
                     # best face frame; classic falls back to 3.0)
    "sticker": "",   # news/poster: small rotated red tag, e.g. "BIG NEWS" / "NEW RULE"
    "kicker": "",    # small pill above the headline, e.g. "FREE MIGRATION SEMINAR"
    "headline": "",  # big bold line; wrap a word in **stars** for the gold accent
    "logo_card": None,   # path (relative to <reel>/) to a full-canvas RGBA PNG
                          # whose opaque region is a standalone badge/card --
                          # composited as a bottom footer badge with a drop
                          # shadow. Opt-in: None means no card (unaffected).
}


def load_thumb_content():
    c = dict(DEFAULT_THUMB)
    cfg = os.path.join(REEL, "content.json")
    if os.path.isfile(cfg):
        c.update(json.load(open(cfg, encoding="utf-8")).get("thumbnail", {}))
    return c


def _accent_html(text):
    """**word** -> gold-accented span; the rest stays plain white."""
    escaped = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return re.sub(r"\*\*(.+?)\*\*", r'<span class="accent">\1</span>', escaped)


def build():
    if PREVIEW:
        print("build_thumbnail.py: skipped: preview mode")
        return

    final = os.path.join(OUT, "reel_final.mp4")
    if not os.path.isfile(final):
        raise SystemExit(f"{final} not found -- run build_composite.py first.")

    content = load_thumb_content()
    if content.get("style", "news") in ("news", "poster"):
        return build_poster(content)
    if content["at"] == "auto":
        content["at"] = 3.0

    # 1) background frame grab -- from base_broll.mp4 (pre-caption, same timeline
    # as the main content) rather than reel_final.mp4, so no kinetic caption word
    # can end up frozen into the thumbnail. Logo composited fresh here instead of
    # relying on the one build_composite.py bakes into the captioned video.
    raw_bg = os.path.join(WORK, "thumb_bg_raw.png")
    pre_caption = os.path.join(WORK, "base_broll.mp4")
    run(["-ss", f"{content['at']:.3f}", "-i", pre_caption,
         "-frames:v", "1", raw_bg])

    bg = os.path.join(WORK, "thumb_bg.png")
    run(["-i", raw_bg, "-i", LOGO,
         "-filter_complex", "[1]scale=432:-1[lg];[0][lg]overlay=(W-w)/2:38[v]",
         "-map", "[v]", "-frames:v", "1", bg])

    # 2) transparent branded overlay, rendered as a single RGBA PNG frame
    proj = os.path.join(WORK, "thumb_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)

    kicker_html = (f'<div id="kicker">{_accent_html(content["kicker"])}</div>'
                   if content["kicker"] else "")
    headline_html = (f'<div id="headline">{_accent_html(content["headline"])}</div>'
                      if content["headline"] else "")
    html = (_THUMB_HTML.replace("__KICKER__", kicker_html)
                        .replace("__HEADLINE__", headline_html))
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(html)
    json.dump({"id": "thumb", "name": "reel thumbnail overlay"},
              open(os.path.join(proj, "meta.json"), "w"))

    frames_dir = os.path.join(WORK, "thumb_frames")
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir)
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(frames_dir),
                    "--format", "png-sequence", "-f", "30", "-q", "standard", "--quiet"],
                   cwd=proj, check=True, env=env)
    overlay = os.path.join(frames_dir, "frame_000001.png")

    # 3) composite: still image, single frame, no alpha-video decode gymnastics
    out = os.path.join(OUT, "thumbnail.jpg")
    run(["-i", bg, "-i", overlay,
         "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
         "-map", "[v]", "-frames:v", "1", "-q:v", "2", out])

    # 4) optional bottom footer badge (e.g. the campaign wordmark card) with a
    # soft drop shadow, so the thumbnail carries the full logo, not just the
    # small persistent top chip.
    if content["logo_card"]:
        _composite_logo_card(out, os.path.join(REEL, content["logo_card"]))

    print("wrote", out)


def build_poster(content):
    import thumb_poster as tp
    base = os.path.join(WORK, "base.mp4")
    cfg = json.load(open(os.path.join(REEL, "content.json"), encoding="utf-8"))
    headline = content["headline"] or tp.headline_from_title(cfg.get("caption_txt", {}).get("title", ""))
    if content["at"] == "auto":
        cands = tp.pick_distinct(tp.score_frames(base), k=3)
        if not cands:
            raise SystemExit("poster thumbnail: no face found in base.mp4 -- set thumbnail.at")
    else:
        cands = [{"t": float(content["at"]), "face": None}]
    alts = os.path.join(OUT, "thumbnail_alts")
    if os.path.exists(alts):
        shutil.rmtree(alts)
    for i, c in enumerate(cands):
        frame = os.path.join(WORK, f"thumb_frame_{i}.png")
        run(["-ss", f"{c['t']:.3f}", "-i", base, "-frames:v", "1", frame])
        face = c["face"] or _face_or_centre(frame)
        dest = os.path.join(OUT, "thumbnail.jpg") if i == 0 else os.path.join(alts, f"alt_{i}.jpg")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tp.render_poster(frame, face, dest, os.path.join(WORK, "thumb_poster"), headline,
                         kicker=content["kicker"], sticker=content.get("sticker", ""), logo=LOGO,
                         style=content.get("style", "news"))
        print(f"{'wrote' if i == 0 else '  alt'} {dest}  (frame {c['t']:.2f}s)")
    tp.grid_preview(os.path.join(OUT, "thumbnail.jpg"), os.path.join(WORK, "thumb_grid_preview.jpg"))
    if content["logo_card"]:
        _composite_logo_card(os.path.join(OUT, "thumbnail.jpg"), os.path.join(REEL, content["logo_card"]))


def _face_or_centre(frame_png):
    """Face box for a hand-picked frame (falls back to a centred guess)."""
    import cv2
    import thumb_poster as tp
    g = cv2.cvtColor(cv2.imread(frame_png), cv2.COLOR_BGR2GRAY)
    faces = tp._cascades()[0].detectMultiScale(g, 1.1, 6, minSize=(g.shape[1] // 10, g.shape[1] // 10))
    if len(faces):
        return [int(v) for v in max(faces, key=lambda f: f[2] * f[3])]
    w = g.shape[1]
    return [int(w * 0.36), int(g.shape[0] * 0.3), int(w * 0.28), int(w * 0.28)]


def _composite_logo_card(thumb_jpg, card_png, target_width=860, bottom_margin=90):
    """Crop the opaque badge out of a full-canvas RGBA PNG (transparent
    everywhere except a rounded-rect card), scale it to target_width, and
    composite it as a bottom-center footer badge with a soft drop shadow."""
    from PIL import Image, ImageFilter
    import numpy as np

    canvas = Image.open(card_png).convert("RGBA")
    arr = np.array(canvas)
    rows = np.where(arr[..., 3].max(axis=1) > 0)[0]
    cols = np.where(arr[..., 3].max(axis=0) > 0)[0]
    card = canvas.crop((int(cols.min()), int(rows.min()), int(cols.max()) + 1, int(rows.max()) + 1))

    scale = target_width / card.width
    card = card.resize((target_width, round(card.height * scale)), Image.LANCZOS)

    thumb = Image.open(thumb_jpg).convert("RGBA")
    x = (thumb.width - card.width) // 2
    y = thumb.height - bottom_margin - card.height

    shadow = Image.new("RGBA", thumb.size, (0, 0, 0, 0))
    shadow_shape = Image.new("RGBA", card.size, (0, 0, 0, 0))
    shadow_shape.putalpha(card.getchannel("A").point(lambda a: int(a * 0.55)))
    shadow.paste(shadow_shape, (x, y + 14), shadow_shape)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))

    thumb = Image.alpha_composite(thumb, shadow)
    thumb.paste(card, (x, y), card)
    thumb.convert("RGB").save(thumb_jpg, quality=95)


_THUMB_HTML = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800;900&display=swap" rel="stylesheet"/>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1080px;height:1920px;overflow:hidden;background:transparent}
  /* Subtle top shade so white text stays legible over any footage brightness,
     without a flat/opaque band that would look like a bug, not a design. */
  #shade{position:absolute;left:0;right:0;top:0;height:620px;
     background:linear-gradient(180deg,rgba(0,0,0,.6),rgba(0,0,0,0))}
  /* top:228/316 (not 130/216) -- the logo (top:38px, scaled to 432px wide,
     ~174px tall at its 492:198 native ratio) bottoms out at ~212px, so the
     kicker pill needs to clear that or it collides with "Education |
     Migration" underneath the wordmark. */
  #kicker{position:absolute;left:60px;top:228px;display:inline-block;background:#100796;
     color:#fff;font-family:"Poppins",sans-serif;font-weight:700;font-size:32px;
     letter-spacing:.05em;padding:14px 32px;border-radius:999px;
     box-shadow:0 10px 26px rgba(0,0,0,.4)}
  #headline{position:absolute;left:60px;right:60px;top:316px;font-family:"Poppins",sans-serif;
     font-weight:900;font-size:84px;line-height:1.08;color:#fff;letter-spacing:.005em;
     text-shadow:0 8px 26px rgba(0,0,0,.85),0 2px 6px rgba(0,0,0,.95)}
  #headline .accent{color:#FFC500}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="0.1"
     data-width="1080" data-height="1920" style="position:relative;width:1080px;height:1920px">
  <div id="shade"></div>
  __KICKER__
  __HEADLINE__
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script>
(function(){
  // Static card -- still registers a (no-op) timeline; the renderer stalls
  // ~45s waiting for window.__timelines["main"] otherwise.
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.seek(0);
  window.__timelines["main"] = tl;
})();
</script>
</body></html>
"""

if __name__ == "__main__":
    build()