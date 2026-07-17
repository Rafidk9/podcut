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

from reel_paths import WORK, OUT, REEL, ASSETS_ROOT, hyperframes_cli  # noqa: E402 -- per-reel folders

FF = shutil.which("ffmpeg") or "ffmpeg"
LOGO = os.path.join(ASSETS_ROOT, "derived", "logo_chip.png")

# Per-reel override via <reel>/content.json -> {"thumbnail": {...}}. Every key
# is optional: with no override you still get a branded still (background
# frame + the persistent logo, composited fresh here) -- kicker/headline just
# add an on-brand hook on top.
DEFAULT_THUMB = {
    "at": 3.0,       # seconds into the main content to grab as the background frame
    "kicker": "",    # small pill above the headline, e.g. "FREE MIGRATION SEMINAR"
    "headline": "",  # big bold line; wrap a word in **stars** for the gold accent
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
    final = os.path.join(OUT, "reel_final.mp4")
    if not os.path.isfile(final):
        raise SystemExit(f"{final} not found -- run build_composite.py first.")

    content = load_thumb_content()

    # 1) background frame grab -- from base_broll.mp4 (pre-caption, same timeline
    # as the main content) rather than reel_final.mp4, so no kinetic caption word
    # can end up frozen into the thumbnail. Logo composited fresh here instead of
    # relying on the one build_composite.py bakes into the captioned video.
    raw_bg = os.path.join(WORK, "thumb_bg_raw.png")
    pre_caption = os.path.join(WORK, "base_broll.mp4")
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{content['at']:.3f}", "-i", pre_caption,
                    "-frames:v", "1", raw_bg], check=True)

    bg = os.path.join(WORK, "thumb_bg.png")
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", raw_bg, "-i", LOGO,
                    "-filter_complex", "[1]scale=432:-1[lg];[0][lg]overlay=(W-w)/2:38[v]",
                    "-map", "[v]", "-frames:v", "1", bg], check=True)

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
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", bg, "-i", overlay,
                    "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
                    "-map", "[v]", "-frames:v", "1", "-q:v", "2", out], check=True)
    print("wrote", out)


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