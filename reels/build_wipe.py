"""A short, reusable grid-pixelate wipe transition (transparent alpha layer),
adapted from HyperFrames' registry `grid-pixelate-wipe` component technique
(explored via `hyperframes add grid-pixelate-wipe`): a grid of cells scales in
from the center to fully cover the frame, holds briefly, then scales out from
the edges to reveal -- recolored to brand Dark Blue so it reads as a designed
transition, not a generic wipe. Overlaid centered on each B-roll cut boundary
to mask the hard cut with a quick, on-brand flourish (~0.5s total)."""
import os, shutil, subprocess, json

from reel_paths import WORK, HF_QUALITY, HF_FPS, hyperframes_cli  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"
DUR = 0.5   # total transition length; peak (full coverage) sits at DUR/2

_HTML = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html,body { width:1080px; height:1920px; overflow:hidden; background:transparent; }
  #wipe { position:absolute; inset:0; display:grid; grid-template-columns:repeat(10,1fr);
          grid-template-rows:repeat(18,1fr); }
  #wipe .cell { background:#100796; transform:scale(0); transform-origin:center center; }
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__DUR__"
     data-width="1080" data-height="1920">
  <div id="wipe"></div>
</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var wipe = document.getElementById("wipe");
  for (var i=0;i<10*18;i++){ var c=document.createElement("div"); c.className="cell"; wipe.appendChild(c); }
  var tl = gsap.timeline({paused:true});
  var HALF = __DUR__/2;
  tl.to("#wipe .cell", {scale:1.05, duration:HALF-0.02, stagger:{amount:HALF-0.05, from:"center"}, ease:"power2.out"}, 0);
  tl.to("#wipe .cell", {scale:0, duration:HALF-0.02, stagger:{amount:HALF-0.05, from:"edges"}, ease:"power2.in"}, HALF);
  window.__timelines["main"] = tl;
})();
</script></body></html>
"""


_SPEED_HTML = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html,body { width:1080px; height:1920px; overflow:hidden; background:transparent; }
  #panel { position:absolute; top:-20%; height:140%; width:1700px; left:-1900px;
           transform:skewX(-14deg);
           background:linear-gradient(100deg,#100796 0%,#7a1a8a 45%,#E84B37 78%,#FFC500 100%); }
  #streak { position:absolute; top:0; height:100%; width:70px; left:-1900px;
            transform:skewX(-14deg); background:rgba(255,255,255,.55); filter:blur(2px); }
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__DUR__"
     data-width="1080" data-height="1920">
  <div id="streak"></div>
  <div id="panel"></div>
</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  var HALF = __DUR__/2;
  // wide skewed panel sweeps L->R, holds fully-covering dead center at HALF
  // (that's where the actual cut happens), then continues off the right --
  // a fast "car passing" swipe, matching the reel's road-tour motif.
  tl.to("#panel", {left:-260, duration:HALF-0.04, ease:"power2.in"}, 0);
  tl.to("#panel", {left:1900, duration:HALF-0.04, ease:"power2.out"}, HALF+0.04);
  tl.to("#streak", {left:-260, duration:(HALF-0.04)*0.7, ease:"power2.in"}, 0);
  tl.to("#streak", {left:1900, duration:(HALF-0.04)*0.7, ease:"power2.out"}, HALF+0.15);
  window.__timelines["main"] = tl;
})();
</script></body></html>
"""

_FLASH_HTML = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html,body { width:1080px; height:1920px; overflow:hidden; background:transparent; }
  #flash { position:absolute; inset:0; background:radial-gradient(circle,#fff 0%,#FFC500 60%,#100796 100%);
           opacity:0; transform:scale(1.4); }
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__DUR__"
     data-width="1080" data-height="1920">
  <div id="flash"></div>
</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  var HALF = __DUR__/2;
  // punchy radial flash: fast in, brief full-white hold at HALF (the cut),
  // fast out -- a quick "impact" beat instead of a directional wipe.
  tl.fromTo("#flash", {opacity:0,scale:1.4}, {opacity:1,scale:1,duration:HALF-0.03,ease:"power3.in"}, 0);
  tl.to("#flash", {opacity:0,scale:0.85,duration:HALF-0.03,ease:"power3.out"}, HALF+0.03);
  window.__timelines["main"] = tl;
})();
</script></body></html>
"""


def _render(html, dur, proj_name, out_name):
    proj = os.path.join(WORK, proj_name)
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(html.replace("__DUR__", str(dur)))
    json.dump({"id": proj_name, "name": "brand wipe transition"}, open(os.path.join(proj, "meta.json"), "w"))

    out = os.path.join(WORK, out_name)
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(out),
                    "-f", str(HF_FPS), "--format", "webm", "-q", HF_QUALITY, "--quiet"],
                   cwd=proj, check=True, env=env)
    print("rendered", out)


def _color_grid_html(color):
    return _HTML.replace("#100796", color)


def build():
    _render(_HTML, DUR, "wipe_proj", "wipe.webm")


def build_red():
    """Optional variant (style "red"): the same grid-pixelate wipe recoloured
    danger-red -- masks a cut INTO a red-flag beat so the reveal itself reads
    as the judgement, not just a plain hard cut."""
    _render(_color_grid_html("#E84B37"), DUR, "wipe_red_proj", "wipe_red.webm")


def build_green():
    """Optional variant (style "green"): the same grid-pixelate wipe
    recoloured brand-green -- masks a cut INTO a green-flag beat."""
    _render(_color_grid_html("#31EB7C"), DUR, "wipe_green_proj", "wipe_green.webm")


def build_speed():
    """Optional variant (opt-in via broll_plan.json "extra_wipes" style
    "speed"): a wide skewed color panel sweeping across, like a car/plane
    passing fast -- matches this project's road-tour motifs when a reel
    wants transition variety instead of the grid-wipe on every cut."""
    _render(_SPEED_HTML, DUR, "wipe_speed_proj", "wipe_speed.webm")


def build_flash():
    """Optional variant (style "flash"): a punchy radial white/gold flash,
    for a cut that wants an impact beat rather than a directional wipe."""
    _render(_FLASH_HTML, DUR, "wipe_flash_proj", "wipe_flash.webm")


if __name__ == "__main__":
    build()
    build_speed()
    build_flash()
    build_red()
    build_green()
