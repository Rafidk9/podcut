"""Closing end-card segment for the Migration 360 Roadshow thank-you reel.
~4s, 1080x1920/30fps, same HyperFrames render pipeline as the per-city
blocks (build_city_block.py) -- but this one is a standalone static-layout
card (logo + two-line message + website), not a media-driven block, so it
gets its own small builder instead of going through build_city_block().

Layout (top to bottom, all centered in a single flex column):
  - PFEC logo, reasonably prominent (460px wide)
  - "Thank you." (large, white)
  - "See you next year." (smaller, brand yellow accent, staggered in after
    "Thank you.")
  - www.pfecglobal.com.au (small, soft white, letter-spaced)

Background: brand indigo (#100796), same ink used across every other
segment's stamp/accent work (see build_perth.py, build_style_frame.py).

Logo (see assets/logo/README.md): uses pfec-logo-white.svg, a pre-recoloured
all-white variant (.st0/.st1/.st2 all #FFFFFF), so it reads cleanly on a
navy/indigo background with no residual blue tones. (Previously this
inlined pfec-logo-colour.svg and runtime-patched only its .st0 rule to
white -- see ~/.claude/styles/hyperframes/pfec-announcement-sting.md for
that history -- but left the diagonal tint-ramp bars' .st1/.st2 in blue/
lavender, giving a mixed blue+white look. The white SVG file replaces that
workaround.)

Renders work/segment_end.mp4. No audio track (matches build_city_block.py's
segment_*.mp4 outputs -- audio is added later in the composite stage).
"""
import json
import os
import shutil
import subprocess
import sys

_THIS = os.path.abspath(__file__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(_THIS))))  # reels/
from reel_paths import WORK, ASSETS_ROOT, hyperframes_cli  # noqa: E402

DUR = 4.0
FPS = 30

INK = "#100796"       # brand indigo -- background
ACCENT = "#FFC500"    # brand yellow -- accent

LOGO_SVG = os.path.join(ASSETS_ROOT, "logo", "pfec-logo-white.svg")


def _inlined_logo_svg():
    with open(LOGO_SVG, "r", encoding="utf-8") as f:
        raw = f.read()
    # pfec-logo-white.svg is already a pre-recoloured all-white variant
    # (.st0/.st1/.st2 all #FFFFFF -- see assets/logo/README.md), so no
    # runtime colour patching is needed. Just strip the XML prolog/comment
    # so it drops cleanly into the HTML body, and give the root <svg> a
    # display:block sizing hook.
    start = raw.index("<svg")
    svg = raw[start:]
    svg = svg.replace("<svg ", '<svg style="display:block;width:100%;height:auto" ', 1)
    return svg


_HTML = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1080px;height:1920px;overflow:hidden;background:__INK__}
  .stage{position:absolute;inset:0}
  #bg{position:absolute;inset:0;
      background:
        radial-gradient(ellipse 900px 900px at 50% 20%, rgba(255,255,255,.07), transparent 60%),
        __INK__;}

  #content{position:absolute;left:0;top:760px;width:1080px;
            display:flex;flex-direction:column;align-items:center;gap:30px}

  #logoWrap{width:460px;opacity:0;transform:scale(0.85)}

  #thankYou{font-family:"Poppins",sans-serif;font-weight:900;font-size:128px;line-height:1.05;
             color:#FFFFFF;letter-spacing:.005em;text-align:center;white-space:nowrap;
             opacity:0;transform:translateY(26px)}
  #seeYou{font-family:"Poppins",sans-serif;font-weight:700;font-size:60px;line-height:1.1;
           color:__ACCENT__;letter-spacing:.005em;text-align:center;white-space:nowrap;
           opacity:0;transform:translateY(22px)}
  #website{font-family:"Poppins",sans-serif;font-weight:600;font-size:38px;line-height:1.1;
            color:rgba(255,255,255,.82);letter-spacing:.1em;text-align:center;white-space:nowrap;
            margin-top:38px;opacity:0;transform:translateY(18px)}
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="__DUR__" data-fps="__FPS__" data-width="1080" data-height="1920">

  <div class="stage" id="bg"></div>

  <div id="content">
    <div id="logoWrap">__LOGO__</div>
    <div id="thankYou">Thank you.</div>
    <div id="seeYou">See you next year.</div>
    <div id="website">www.pfecglobal.com.au</div>
  </div>

</div>
<script>
(function(){
  window.__timelines=window.__timelines||{};
  var tl=gsap.timeline({paused:true});

  // Calm settle: logo first, then headline, then the staggered sub-line,
  // then the URL -- each a simple fade + small upward drift, nothing
  // frantic (this is the closing beat after an energetic reel).
  tl.to("#logoWrap",{opacity:1,scale:1.0,duration:0.7,ease:"power2.out"},0.15);
  tl.to("#thankYou",{opacity:1,y:0,duration:0.6,ease:"power2.out"},0.5);
  tl.to("#seeYou",{opacity:1,y:0,duration:0.6,ease:"power2.out"},0.9);
  tl.to("#website",{opacity:1,y:0,duration:0.5,ease:"power2.out"},1.3);

  tl.seek(0);
  window.__timelines["main"]=tl;
})();
</script></body></html>
"""


def build_html():
    return (_HTML
            .replace("__DUR__", f"{DUR:.3f}")
            .replace("__FPS__", str(FPS))
            .replace("__INK__", INK)
            .replace("__ACCENT__", ACCENT)
            .replace("__LOGO__", _inlined_logo_svg()))


def main():
    proj = os.path.join(WORK, "end_card_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)
    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_html())
    with open(os.path.join(proj, "meta.json"), "w") as f:
        json.dump({"id": "end_card", "name": "Migration 360 Roadshow thank-you end card"}, f)

    out = os.path.join(WORK, "segment_end.mp4")
    cli = hyperframes_cli()
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(out),
                     "-f", str(FPS), "-q", "standard", "--sdr", "--quiet"],
                    cwd=proj, check=True)
    print(f"[build_end_card] rendered {out} ({DUR:.2f}s)")
    return out


if __name__ == "__main__":
    main()
