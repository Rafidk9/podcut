"""One-off design-checkpoint build: a 3.4s style preview demonstrating the
per-city block treatment for the Migration 360 Roadshow thank-you reel, using
Perth as the test city. NOT part of the regular per-reel pipeline (build_*.py
in reels/) -- this lives under work/ and is meant to be thrown away once the
style is approved and the real 6-city build begins.

Renders work/style_frame_perth.mp4 (1080x1920/30fps, ~3.4s) via the vendored
HyperFrames CLI, same invocation pattern as reels/build_opener.py.
"""
import base64
import json
import os
import shutil
import subprocess
import sys

_THIS = os.path.abspath(__file__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(_THIS))))  # reels/
from reel_paths import WORK, hyperframes_cli  # noqa: E402

DUR = 3.4
FPS = 30

HERO_JPG = os.path.join(WORK, "style_preview_proj", "perth_hero.jpg")
LOGO_SVG = os.path.normpath(os.path.join(WORK, "..", "..", "..", "assets", "logo",
                                          "pfec-logo-white.svg"))

INK = "#100796"


def data_uri(path, mime):
    with open(path, "rb") as f:
        b = f.read()
    return f"data:{mime};base64,{base64.b64encode(b).decode()}"


_HTML = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800;900&family=Playfair+Display:wght@700;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1080px;height:1920px;overflow:hidden;background:#0A0730}
  .stage{position:absolute;inset:0}

  /* ---------- background: abstract flat map mood ---------- */
  #bg{position:absolute;inset:0;
      background:
        radial-gradient(ellipse 900px 700px at 50% 8%, rgba(255,255,255,.08), transparent 60%),
        linear-gradient(160deg,#140B5C 0%,#0A0730 46%,#050318 100%);}
  #bg svg{position:absolute;left:-60px;top:120px;opacity:.16}

  /* ---------- top zone: logo + passport stamp (0 - 380px) ---------- */
  #stampZone{position:absolute;left:0;top:0;width:1080px;height:380px;
             display:flex;align-items:center;justify-content:center}
  #logoWrap{position:absolute;left:50%;top:16px;transform:translateX(-50%) scale(0.001);
             opacity:0}
  #logoWrap img{display:block;height:34px;width:auto}
  #stampWrap{position:absolute;left:50%;top:215px;width:300px;height:300px;
             transform:translate(-50%,-50%) rotate(-6deg) scale(0.001);}
  #stampFilter{position:absolute;inset:-30px}
  #stampRing{position:absolute;inset:0;border-radius:50%;
             filter:url(#inkbleed);}
  #stampRing .ringInner{position:absolute;inset:0;border-radius:50%;
             border:7px solid __INK__;box-shadow:inset 0 0 0 3px __INK__;opacity:.92}
  #stampRing .ringOuter{position:absolute;inset:22px;border-radius:50%;
             border:3px solid __INK__;opacity:.55}
  #stampPlane{position:absolute;left:50%;top:50%;width:74px;height:74px;
             transform:translate(-50%,-50%) rotate(45deg);color:__INK__}
  #stampFooter{position:absolute;left:50%;bottom:38px;transform:translateX(-50%);
             font-family:"Poppins",sans-serif;font-weight:800;font-size:15px;letter-spacing:.22em;
             color:__INK__;opacity:.92;white-space:nowrap}
  #cityArc{position:absolute;inset:0}
  #cityArc text{font-family:"Poppins",sans-serif;font-weight:900;font-size:35px;
             letter-spacing:.14em;fill:__INK__}

  /* ---------- middle/hero zone (380 - 1480px, 1100 tall) ---------- */
  #heroZone{position:absolute;left:0;top:380px;width:1080px;height:1100px;overflow:hidden;
            background:#050318}
  #heroBlur{position:absolute;left:-80px;top:-80px;width:1240px;height:1260px;
            background-image:url('__HERO__');background-size:cover;background-position:center;
            filter:blur(34px) saturate(1.25) brightness(1.02);transform:scale(1.1)}
  #heroBlurTint{position:absolute;inset:0;background:linear-gradient(180deg,rgba(10,7,48,.18),rgba(5,3,24,.05) 22%,rgba(5,3,24,.05) 78%,rgba(10,7,48,.22))}
  #heroSharpWrap{position:absolute;left:0;top:50%;width:1080px;transform:translateY(-50%)}
  #heroSharpWrap img{display:block;width:1080px;height:auto;
            box-shadow:0 30px 90px rgba(0,0,0,.55)}
  #heroEdgeTop,#heroEdgeBot{position:absolute;left:0;width:1080px;height:36px}
  #heroEdgeTop{top:0;background:linear-gradient(180deg,#050318,transparent)}
  #heroEdgeBot{bottom:0;background:linear-gradient(0deg,#050318,transparent)}

  /* ---------- bottom zone: stamp-stack progress only (1480 - 1920px) ---------- */
  #bottomZone{position:absolute;left:0;top:1480px;width:1080px;height:440px}
  #progressRow{position:absolute;left:50%;top:96px;transform:translateX(-50%);
             display:flex;gap:22px}
  .pdot{width:28px;height:28px;border-radius:50%;border:3px solid rgba(255,255,255,.4);
             box-sizing:border-box}
  .pdot.filled{background:__INK__;border-color:__INK__;box-shadow:0 0 18px rgba(16,7,150,.7)}
  #progressLabel{position:absolute;left:50%;top:150px;transform:translateX(-50%);
             font-family:"Poppins",sans-serif;font-weight:700;font-size:24px;
             letter-spacing:.12em;color:rgba(255,255,255,.72)}
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="__DUR__" data-fps="__FPS__" data-width="1080" data-height="1920">

  <div class="stage" id="bg">
    <svg width="1200" height="1600" viewBox="0 0 300 400">
      <path d="M 90 30 C 140 20 190 40 210 90 C 230 140 220 200 240 250
               C 255 290 230 330 190 340 C 150 350 120 330 100 300
               C 70 280 40 260 40 220 C 40 180 60 160 55 120
               C 50 80 60 45 90 30 Z"
            fill="none" stroke="__INK__" stroke-width="2.5"/>
    </svg>
  </div>

  <div class="stage" id="heroZone">
    <div id="heroBlur"></div>
    <div id="heroBlurTint"></div>
    <div id="heroSharpWrap"><img src="__HERO__"/></div>
    <div id="heroEdgeTop"></div>
    <div id="heroEdgeBot"></div>
  </div>

  <div class="stage" id="stampZone">
    <div id="logoWrap"><img src="__LOGO__"/></div>
    <div id="stampWrap">
      <svg id="stampFilter" width="0" height="0">
        <filter id="inkbleed" x="-60%" y="-60%" width="220%" height="220%">
          <feTurbulence type="fractalNoise" baseFrequency="0.018 0.03" numOctaves="3" seed="7" result="noise"/>
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="14" xChannelSelector="R" yChannelSelector="G"/>
        </filter>
      </svg>
      <div id="stampRing"><div class="ringInner"></div><div class="ringOuter"></div></div>
      <svg id="cityArc" width="300" height="300" viewBox="0 0 300 300">
        <path id="arcPath" d="M 42 165 A 108 108 0 0 1 258 165" fill="none"/>
        <text><textPath href="#arcPath" startOffset="50%" text-anchor="middle">PERTH</textPath></text>
      </svg>
      <svg id="stampPlane" viewBox="0 0 24 24" fill="currentColor">
        <path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2.5 1.5V22l4-1 4 1v-1.5L13.5 19v-5.5z"/>
      </svg>
      <div id="stampFooter">PFEC GLOBAL</div>
    </div>
  </div>

  <div class="stage" id="bottomZone">
    <div id="progressRow">
      <div class="pdot filled"></div>
      <div class="pdot"></div><div class="pdot"></div><div class="pdot"></div>
      <div class="pdot"></div><div class="pdot"></div>
    </div>
    <div id="progressLabel">1 / 6 CITIES</div>
  </div>

</div>
<script>
(function(){
  window.__timelines=window.__timelines||{};
  var tl=gsap.timeline({paused:true});

  // stamp lands: scale in with overshoot, arriving ~t=0.3s, settling ~0.42s
  tl.to("#stampWrap",{scale:1.10,duration:0.24,ease:"power2.out"},0.06);
  tl.to("#stampWrap",{scale:1.0,duration:0.18,ease:"power2.out"},0.30);

  // hero photo: gentle settle-in behind the stamp landing
  tl.fromTo("#heroZone",{opacity:0},{opacity:1,duration:0.5,ease:"power1.out"},0.10);
  tl.fromTo("#heroSharpWrap img",{scale:1.05},{scale:1.0,duration:0.9,ease:"power2.out"},0.10);

  // progress + logo settle in shortly after
  tl.fromTo(".pdot",{opacity:0,y:14},{opacity:1,y:0,duration:0.3,ease:"power2.out",stagger:0.04},0.55);
  tl.fromTo("#progressLabel",{opacity:0},{opacity:1,duration:0.3},0.7);
  tl.to("#logoWrap",{opacity:1,scale:1.0,duration:0.32,ease:"back.out(2.2)"},0.85);

  tl.seek(0);
  window.__timelines["main"]=tl;
})();
</script></body></html>
"""


def build_html():
    hero_uri = data_uri(HERO_JPG, "image/jpeg")
    logo_uri = data_uri(LOGO_SVG, "image/svg+xml")
    html = (_HTML
            .replace("__DUR__", f"{DUR:.3f}")
            .replace("__FPS__", str(FPS))
            .replace("__INK__", INK)
            .replace("__HERO__", hero_uri)
            .replace("__LOGO__", logo_uri))
    return html


def main():
    proj = os.path.join(WORK, "style_preview_proj")
    os.makedirs(proj, exist_ok=True)
    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_html())
    with open(os.path.join(proj, "meta.json"), "w") as f:
        json.dump({"id": "style_frame_perth", "name": "Migration 360 per-city style checkpoint (Perth)"}, f)

    out = os.path.join(WORK, "style_frame_perth.mp4")
    cli = hyperframes_cli()
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(out),
                     "-f", str(FPS), "-q", "standard", "--quiet"],
                    cwd=proj, check=True)
    print("style frame ready:", out)


if __name__ == "__main__":
    main()
