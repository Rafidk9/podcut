"""Generate 4 DISTINCT, topically-relevant B-roll stingers via HyperFrames --
each one ties to the specific moment it cuts away from/into, rather than a
generic brand wordmark repeated. Niyama is Sydney-based, so broll_2 uses a
Sydney skyline motif (Opera House + Harbour Bridge silhouette) tying the
"pathway to Australia" theme to something personal. No claims, no real scenery
photography -- pure on-brand motion graphics, safe for any connecting phrase.
Opaque render (full-frame replacement, no alpha needed)."""
import os, shutil, subprocess, json, importlib.util

from reel_paths import WORK, REEL, hyperframes_cli  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"


def load_stingers():
    """Per-reel B-roll content: <reel>/broll.py defining STINGERS =
    [(name, duration, body_html), ...]. Falls back to the Lakemba defaults
    below if the reel has no override (so that reel keeps building as-is)."""
    override = os.path.join(REEL, "broll.py")
    if os.path.isfile(override):
        spec = importlib.util.spec_from_file_location("reel_broll", override)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.STINGERS
    return [("broll_1", 1.3, BROLL_1), ("broll_2", 1.4, BROLL_2),
            ("broll_3", 1.4, BROLL_3), ("broll_4", 1.3, BROLL_4)]


def render(name, dur, body_html, extra_css=""):
    proj = os.path.join(WORK, f"broll_proj_{name}")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)
    html = f"""<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ width:1080px; height:1920px; overflow:hidden; }}
  {extra_css}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{dur}"
     data-width="1080" data-height="1920" style="position:relative;width:1080px;height:1920px">
{body_html}
</div>
</body></html>
"""
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(html)
    json.dump({"id": name, "name": name}, open(os.path.join(proj, "meta.json"), "w"))

    out = os.path.join(WORK, f"{name}.mp4")
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(out),
                    "-f", "30", "-q", "standard", "--quiet"],
                   cwd=proj, check=True, env=env)
    print("rendered", out)


# --------------------------------------------------------------------------- #
# broll_1: STAKES -- "one wrong course, a costly detour" (after the hook,
# before "choosing the wrong course can cost you lots")
# --------------------------------------------------------------------------- #
BROLL_1 = """
<style id="s1">
  #bg1{position:absolute;inset:0;background:linear-gradient(160deg,#1a0a0a,#100796 70%)}
  .path{position:absolute;top:50%;left:50%;height:10px;border-radius:6px;transform-origin:0 50%}
  #pathWrong{width:0px;background:#555;transform:translate(0,-90px) rotate(-18deg)}
  #pathRight{width:0px;background:#31EB7C;transform:translate(0,40px) rotate(10deg);
             box-shadow:0 0 24px 4px rgba(49,235,124,.7)}
  .badge{position:absolute;border-radius:50%;display:flex;align-items:center;justify-content:center;
         font-family:Poppins,sans-serif;font-weight:900;color:#fff;opacity:0;transform:scale(0)}
  #xBadge{width:74px;height:74px;background:#E84B37;font-size:40px;top:calc(50% - 130px);left:78%}
  #tick{width:74px;height:74px;background:#31EB7C;font-size:40px;top:calc(50% + 20px);left:80%}
  .h1{position:absolute;left:0;right:0;top:38%;text-align:center;font-family:Poppins,sans-serif;
      font-weight:900;font-size:74px;color:#fff;opacity:0;letter-spacing:.01em}
  .h2{position:absolute;left:0;right:0;top:66%;text-align:center;font-family:Poppins,sans-serif;
      font-weight:700;font-size:44px;color:#FFC500;opacity:0}
</style>
<div id="bg1"></div>
<div class="path" id="pathWrong"></div>
<div class="path" id="pathRight"></div>
<div class="badge" id="xBadge">&#10005;</div>
<div class="badge" id="tick">&#10003;</div>
<div class="h1" id="h1a">ONE WRONG COURSE.</div>
<div class="h2" id="h2a">A COSTLY DETOUR.</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.to("#pathWrong",{width:340,duration:.35,ease:"power2.out"},0);
  tl.to("#pathRight",{width:420,duration:.35,ease:"power2.out"},0.05);
  tl.to("#xBadge",{opacity:1,scale:1,duration:.2,ease:"back.out(2.4)"},0.32);
  tl.to("#tick",{opacity:1,scale:1,duration:.2,ease:"back.out(2.4)"},0.4);
  tl.fromTo("#h1a",{opacity:0,y:16},{opacity:1,y:0,duration:.26,ease:"back.out(1.8)"},0.15);
  tl.fromTo("#h2a",{opacity:0,y:16},{opacity:1,y:0,duration:.26,ease:"back.out(1.8)"},0.4);
  tl.to(["#h1a","#h2a","#xBadge","#tick"],{opacity:0,duration:.2,ease:"power2.in"},1.05);
  window.__timelines["main"]=tl;
})();
</script>
"""

# --------------------------------------------------------------------------- #
# broll_2: SYDNEY / "YOUR PATHWAY TO AUSTRALIA" (after "...in Australia.")
# Real SVG silhouette: Harbour Bridge coathanger arch + Opera House sails
# (curved bezier "shells", not triangles) -- recognizable, not abstract.
# --------------------------------------------------------------------------- #
BROLL_2 = """
<style id="s2">
  #bg2{position:absolute;inset:0;background:linear-gradient(180deg,#052049 0%,#100796 100%)}
  #skylineWrap{position:absolute;left:50%;bottom:24%;transform:translateX(-50%) scale(0);
               transform-origin:bottom center}
  #bridgeGroup{opacity:0}
  #sailsGroup path{opacity:0;transform-origin:bottom center}
  .h3{position:absolute;left:0;right:0;top:16%;text-align:center;font-family:Poppins,sans-serif;
      font-weight:900;font-size:70px;color:#fff;opacity:0}
  .h4{position:absolute;left:0;right:0;top:24.5%;text-align:center;font-family:Poppins,sans-serif;
      font-weight:700;font-size:40px;color:#FFC500;opacity:0}
</style>
<div id="bg2"></div>
<div id="skylineWrap">
  <svg width="820" height="420" viewBox="0 0 820 420">
    <g id="bridgeGroup">
      <path d="M40,400 Q410,120 780,400" stroke="#FFC500" stroke-width="16" fill="none" stroke-linecap="round"/>
      <path d="M40,400 L780,400" stroke="#FFC500" stroke-width="12" fill="none"/>
      <line x1="150" y1="400" x2="150" y2="298" stroke="#FFC500" stroke-width="7"/>
      <line x1="260" y1="400" x2="260" y2="222" stroke="#FFC500" stroke-width="7"/>
      <line x1="410" y1="400" x2="410" y2="188" stroke="#FFC500" stroke-width="7"/>
      <line x1="560" y1="400" x2="560" y2="222" stroke="#FFC500" stroke-width="7"/>
      <line x1="670" y1="400" x2="670" y2="298" stroke="#FFC500" stroke-width="7"/>
      <rect x="26" y="330" width="30" height="72" fill="#FFC500"/>
      <rect x="764" y="330" width="30" height="72" fill="#FFC500"/>
    </g>
    <g id="sailsGroup" fill="#fff">
      <path id="sailA" d="M300,402 C300,402 296,300 340,255 C372,290 372,402 372,402 Z"/>
      <path id="sailB" d="M355,402 C355,402 350,270 405,215 C448,262 448,402 448,402 Z"/>
      <path id="sailC" d="M425,402 C425,402 418,240 480,178 C532,235 532,402 532,402 Z"/>
      <path id="sailD" d="M500,402 C500,402 495,285 545,235 C582,272 582,402 582,402 Z"/>
    </g>
  </svg>
</div>
<div class="h3" id="h3a">YOUR PATHWAY</div>
<div class="h4" id="h4a">TO AUSTRALIA</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.to("#skylineWrap",{scale:1,duration:.4,ease:"power2.out"},0);
  tl.to("#bridgeGroup",{opacity:1,duration:.25,ease:"power1.out"},0.1);
  tl.fromTo("#sailA",{opacity:0,scaleY:.6},{opacity:1,scaleY:1,duration:.22,ease:"back.out(1.6)"},0.28);
  tl.fromTo("#sailB",{opacity:0,scaleY:.6},{opacity:1,scaleY:1,duration:.22,ease:"back.out(1.6)"},0.36);
  tl.fromTo("#sailC",{opacity:0,scaleY:.6},{opacity:1,scaleY:1,duration:.22,ease:"back.out(1.6)"},0.44);
  tl.fromTo("#sailD",{opacity:0,scaleY:.6},{opacity:1,scaleY:1,duration:.22,ease:"back.out(1.6)"},0.52);
  tl.fromTo("#h3a",{opacity:0,y:-14},{opacity:1,y:0,duration:.3,ease:"back.out(1.8)"},0.62);
  tl.fromTo("#h4a",{opacity:0,y:-10},{opacity:1,y:0,duration:.3,ease:"back.out(1.8)"},0.76);
  tl.to(["#h3a","#h4a"],{opacity:0,duration:.2,ease:"power2.in"},1.2);
  window.__timelines["main"]=tl;
})();
</script>
"""

# --------------------------------------------------------------------------- #
# broll_3: CROSSROADS -- "which way is right for you?" (after "...bachelor
# in IT?", before "Or masters by research")
# --------------------------------------------------------------------------- #
BROLL_3 = """
<style id="s3">
  #bg3{position:absolute;inset:0;background:linear-gradient(200deg,#100796,#0a0664 60%)}
  #pole{position:absolute;left:50%;bottom:20%;width:14px;height:420px;background:#fff;
        margin-left:-7px;border-radius:6px;transform:scaleY(0);transform-origin:bottom}
  .sign{position:absolute;left:50%;height:84px;background:#00B3E3;border-radius:8px;
        display:flex;align-items:center;padding:0 26px;font-family:Poppins,sans-serif;
        font-weight:800;font-size:34px;color:#fff;opacity:0;white-space:nowrap;
        box-shadow:0 8px 20px rgba(0,0,0,.35)}
  #sign1{bottom:56%;transform:translateX(-10%) rotate(-8deg) scale(.7)}
  #sign2{bottom:44%;background:#FFC500;color:#100796;transform:translateX(-90%) rotate(7deg) scale(.7)}
  #sign3{bottom:34%;background:#E84B37;transform:translateX(-15%) rotate(-4deg) scale(.7)}
  .q{position:absolute;left:0;right:0;top:20%;text-align:center;font-family:Poppins,sans-serif;
     font-weight:900;font-size:60px;color:#fff;opacity:0}
</style>
<div id="bg3"></div>
<div class="q" id="qa">WHICH WAY IS RIGHT?</div>
<div id="pole"></div>
<div class="sign" id="sign1">TEACHING</div>
<div class="sign" id="sign2">IT</div>
<div class="sign" id="sign3">RESEARCH</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.fromTo("#qa",{opacity:0,y:-14},{opacity:1,y:0,duration:.28,ease:"back.out(1.8)"},0);
  tl.to("#pole",{scaleY:1,duration:.3,ease:"power2.out"},0.12);
  tl.to("#sign1",{opacity:1,scale:1,duration:.26,ease:"back.out(2)"},0.34);
  tl.to("#sign2",{opacity:1,scale:1,duration:.26,ease:"back.out(2)"},0.46);
  tl.to("#sign3",{opacity:1,scale:1,duration:.26,ease:"back.out(2)"},0.58);
  tl.to(["#qa","#sign1","#sign2","#sign3"],{opacity:0,duration:.2,ease:"power2.in"},1.15);
  window.__timelines["main"]=tl;
})();
</script>
"""

# --------------------------------------------------------------------------- #
# broll_4: PFEC GLOBAL reveal -- aligns with "this is where our experts come
# in" (kept close to the original brand-bars treatment; this is the one spot
# a straight brand reveal is the RIGHT content, not filler)
# --------------------------------------------------------------------------- #
BROLL_4 = """
<style id="s4">
  html,body{background:#100796}
  .bar{position:absolute;top:-10%;height:120%;width:220px;transform:skewX(-12deg) translateX(-1400px)}
  .word{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);text-align:center;
        font-family:"Poppins",sans-serif;font-weight:800;color:#fff;opacity:0}
  .word .line1{font-size:62px;letter-spacing:.03em}
  .word .line2{font-size:40px;font-weight:700;color:#31EB7C;margin-top:14px;letter-spacing:.06em}
</style>
<div class="bar" id="b1" style="left:10%;background:#00B3E3"></div>
<div class="bar" id="b2" style="left:32%;background:#31EB7C"></div>
<div class="bar" id="b3" style="left:54%;background:#FFC500"></div>
<div class="word" id="w">
  <div class="line1">PFEC GLOBAL EXPERTS</div>
  <div class="line2">GUIDING YOUR PATHWAY</div>
</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.to("#b1",{x:2400,duration:1.3,ease:"power1.inOut"},0);
  tl.to("#b2",{x:2400,duration:1.3,ease:"power1.inOut"},0.05);
  tl.to("#b3",{x:2400,duration:1.3,ease:"power1.inOut"},0.10);
  tl.fromTo("#w",{opacity:0,y:16,scale:.92},{opacity:1,y:0,scale:1,duration:.28,ease:"back.out(1.6)"},0.22);
  tl.to("#w",{opacity:0,duration:.18,ease:"power2.in"},1.08);
  window.__timelines["main"]=tl;
})();
</script>
"""


if __name__ == "__main__":
    for name, dur, html in load_stingers():
        render(name, dur, html)
