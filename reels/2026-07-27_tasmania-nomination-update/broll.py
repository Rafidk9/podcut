"""Two 1.5s B-roll cutaways over this reel's two genuine connecting/filler
spans (see reels/README.md's B-roll placement rule -- never over a moment
carrying key information):

  segment 1 (index 1): "Compared to the last year," -- pure connective tissue
    bridging the subclass breakdown into the increase reveal. Cuts to
    Wineglass Bay (a second, distinct Tasmania landmark for visual variety).
  segment 2 (index 2): "Tasmania has also confirmed" -- pure connective
    tissue leading into the reopening announcement. Cuts to Cradle Mountain --
    the SAME photo bg_swap.py later plays behind him for the rest of this
    segment, so the cutaway reads as "revealing" the location he then
    appears to be standing in front of, rather than two unrelated visuals.

Real, freely-licensed landmark photography (Wikimedia Commons, CC BY-SA --
see assets/tasmania/CREDITS.txt), not generic stock or invented motion
graphics -- an explicit user request for this reel, overriding this file's
own usual "no real scenery photography" default (see module docstring in
build_broll.py) because the footage is genuinely, specifically Tasmania.
Each: Ken Burns slow zoom-in on the photo + a location pill that pops in and
back out, brand-navy vignette top/bottom for legibility and consistency."""
import base64
import os

REEL = os.path.dirname(os.path.abspath(__file__))


def _data_uri(rel_path):
    path = os.path.join(REEL, "assets", "tasmania", rel_path)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _stinger(img_uri, label, dur):
    return f"""
<style>
  html,body{{background:#000}}
  #photo{{position:absolute;inset:0;overflow:hidden}}
  #photo img{{position:absolute;left:50%;top:50%;width:1080px;height:1920px;
     object-fit:cover;transform:translate(-50%,-50%) scale(1.0)}}
  #vig{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(16,7,150,.55) 0%,
     transparent 18%,transparent 72%,rgba(0,0,0,.6) 100%)}}
  #pin{{position:absolute;left:50%;bottom:200px;transform:translateX(-50%);opacity:0;
     display:flex;align-items:center;gap:12px;background:rgba(16,7,150,.9);
     border:2px solid #FFC500;border-radius:999px;padding:14px 30px;
     box-shadow:0 14px 34px rgba(0,0,0,.5)}}
  #pin .ico{{font-size:28px}}
  #pin .lbl{{font-family:"Poppins",sans-serif;font-weight:800;font-size:26px;color:#fff;
     letter-spacing:.04em}}
</style>
<div id="photo"><img src="{img_uri}"/></div>
<div id="vig"></div>
<div id="pin"><span class="ico">\U0001F4CD</span><span class="lbl">{label}</span></div>
<script>
(function(){{
  window.__timelines = window.__timelines || {{}};
  var tl = gsap.timeline({{paused:true}});
  var D = {dur};
  tl.fromTo("#photo img", {{scale:1.0}}, {{scale:1.14, duration:D, ease:"none"}}, 0);
  tl.fromTo("#pin", {{opacity:0, y:16}}, {{opacity:1, y:0, duration:0.28, ease:"back.out(2.2)"}}, 0.18);
  tl.to("#pin", {{opacity:0, y:-10, duration:0.2, ease:"power2.in"}}, D - 0.28);
  window.__timelines["main"] = tl;
}})();
</script>
"""


WINEGLASS_URI = _data_uri("wineglass_small.jpg")
CRADLE_URI = _data_uri("cradle_small.jpg")

STINGERS = [
    ("broll_wineglass", 1.5, _stinger(WINEGLASS_URI, "WINEGLASS BAY, TAS", 1.5)),
    ("broll_cradle", 1.5, _stinger(CRADLE_URI, "CRADLE MOUNTAIN, TAS", 1.5)),
]
