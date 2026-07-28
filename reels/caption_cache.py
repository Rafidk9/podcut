"""Content-hash cache for build_captions.py's per-element HyperFrames renders
(caption chunk, hero-word slam, badge, checklist, roadshow card). Each of
these renders as its OWN small transparent webm on a LOCAL 0-based timeline
(duration = that element's own end-start), independently cacheable, then
gets composited onto the footage at its resolved ABSOLUTE timestamp via
ffmpeg -itsoffset -- the same technique insert_broll.py's overlay_wipes()
already uses for the grid-wipe transition (one short reusable clip, placed
at an arbitrary time). decor is NOT cached here -- its GSAP timing (sparkle
repeat counts, drift duration) is derived from the WHOLE video's duration,
so it's timing-baked-into-the-render and excluded per this feature's own
"exclude only those" rule; it stays part of the base composition instead.

CACHE_VERSION: bump this whenever the RENDER LOGIC for any cacheable element
changes (its CSS, its GSAP timeline, its HTML structure). The hash covers
content/config, not the template code itself, so a template-only change
wouldn't otherwise invalidate stale cached assets.
"""
import hashlib
import json
import os
import shutil
import subprocess

CACHE_VERSION = 3  # v2: badge text is now JSON-escaped into JS (v1 broke on
                    # apostrophes/quotes in badge text, e.g. "DON'T RISK IT",
                    # silently rendering a blank badge -- see build_captions.py's
                    # _badge_element()). v3: dm_bubble card repositioned lower
                    # (top:96px -> top:365px) -- it was rendering directly under
                    # the brand logo chip (build_composite.py overlays the logo
                    # at y=38, ~174px tall, so anything above ~215px is hidden
                    # behind it) -- see _dm_bubble_element()/.dm-card CSS.

_ELEMENT_HTML = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1080px;height:1920px;overflow:hidden;background:transparent}
__CSS_EXTRA__
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="__DUR__" data-fps="30" data-width="1080" data-height="1920">
__BODY_HTML__
</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
__JS_BODY__
  tl.seek(0);
  window.__timelines["main"] = tl;
})();
</script></body></html>
"""


def cache_root(reel_dir):
    d = os.path.join(reel_dir, ".cache", "captions")
    os.makedirs(d, exist_ok=True)
    return d


def clear_cache(reel_dir):
    d = os.path.join(reel_dir, ".cache", "captions")
    if os.path.isdir(d):
        shutil.rmtree(d)
        print(f"  [cache] cleared {d}")


def element_hash(element_type, content, duration, brand_tokens=None):
    """Stable hash over content/config + duration (timing-independent -- the
    same graphic placed at a different ABSOLUTE timestamp still hits the
    cache, since only its own local duration is in here, never a start/end
    clock time) + CACHE_VERSION + brand tokens this element type actually
    uses."""
    payload = {
        "type": element_type,
        "content": content,
        "duration": round(duration, 3),
        "cache_version": CACHE_VERSION,
        "brand_tokens": brand_tokens or {},
    }
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def render_element(element_type, content, duration, css_extra, body_html, js_body,
                    work_dir, cache_dir, hyperframes_cli, hf_quality, hf_fps,
                    brand_tokens=None, no_cache=False):
    """Renders one element's isolated composition (LOCAL timeline 0..duration)
    as a transparent webm, reusing a cached asset on a hash hit. Returns
    (webm_path, hit: bool)."""
    h = element_hash(element_type, content, duration, brand_tokens)
    cached_path = os.path.join(cache_dir, f"{h}.webm")
    if not no_cache and os.path.isfile(cached_path):
        return cached_path, True

    proj = os.path.join(work_dir, f"elem_proj_{h}")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)
    html = (_ELEMENT_HTML.replace("__CSS_EXTRA__", css_extra)
                          .replace("__BODY_HTML__", body_html)
                          .replace("__JS_BODY__", js_body)
                          .replace("__DUR__", f"{duration:.3f}"))
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(html)
    json.dump({"id": element_type, "name": f"{element_type} ({h[:8]})"},
              open(os.path.join(proj, "meta.json"), "w"))

    out = os.path.join(work_dir, f"elem_{h}.webm")
    ff = shutil.which("ffmpeg") or "ffmpeg"
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(ff) + os.pathsep + env.get("PATH", "")
    subprocess.run(["node", hyperframes_cli, "render", ".", "-o", os.path.abspath(out),
                    "-f", str(hf_fps), "--format", "webm", "-q", hf_quality, "--quiet"],
                   cwd=proj, check=True, env=env)

    if no_cache:
        return out, False
    os.makedirs(cache_dir, exist_ok=True)
    shutil.copy2(out, cached_path)
    return cached_path, False
