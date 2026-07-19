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


def build():
    proj = os.path.join(WORK, "wipe_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(
        _HTML.replace("__DUR__", str(DUR)))
    json.dump({"id": "wipe", "name": "brand wipe transition"}, open(os.path.join(proj, "meta.json"), "w"))

    out = os.path.join(WORK, "wipe.webm")
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(out),
                    "-f", str(HF_FPS), "--format", "webm", "-q", HF_QUALITY, "--quiet"],
                   cwd=proj, check=True, env=env)
    print("rendered", out)


if __name__ == "__main__":
    build()
