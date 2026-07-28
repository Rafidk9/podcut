"""Three 1.35s Adelaide cutaways, one per genuine connecting/filler span in
this reel's transcript (reels/README.md: B-roll never covers a moment carrying
key information, and the count is script-judged, not fixed):

  segment 1 (5.85s): "Adelaide is widely recognized as..." -- he re-names the
    city, so the cutaway simply SHOWS it. Heritage King William St frontage
    (the "Adelaide Bank" stonework reads the city name in-shot).
  segment 3 (14.30s): "Combine that with the..." -- pure linking phrase into
    the nomination program. Cuts to King William Rd looking toward the
    cathedral spires: the wider "South Australia" establishing beat.
  segment 6 (29.35s): "And hence we are breaking this down in our..." --
    pure linking phrase into the roadshow CTA. Cuts to the CBD at night, all
    light trails and lit facades, to lift the energy going into the ask.

Nothing sits over the visa / eligibility / nomination detail.

Real, freely-licensed Adelaide photography (Wikimedia Commons, CC0 / CC BY
only -- see assets/adelaide/CREDITS.txt for why share-alike was excluded),
not generic stock or invented motion graphics: an explicit request for this
reel, overriding build_broll.py's usual "no real scenery photography"
default, exactly as the 2026-07-27 Tasmania reel did, because the footage is
specifically about this one city.

Per the brief every scene gets its OWN animation, so the three do not share a
move: (1) Ken Burns push in, pill rises from below; (2) Ken Burns pull back,
pill irises open behind a cyan underline that sweeps out; (3) Ken Burns push
with a lateral drift, pill wipes in behind a travelling light streak.
Accent is cyan #00B3E3 on navy #100796 to match this reel's palette shift --
the Tasmania precedent used a gold rim; this one does not.
"""
import base64
import os

REEL = os.path.dirname(os.path.abspath(__file__))
DUR = 1.35


def _data_uri(rel_path):
    path = os.path.join(REEL, "assets", "adelaide", rel_path)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


_BASE_CSS = """
  html,body{background:#000}
  #photo{position:absolute;inset:0;overflow:hidden}
  #photo img{position:absolute;left:50%;top:50%;width:1080px;height:1920px;
     object-fit:cover;transform:translate(-50%,-50%)}
  #vig{position:absolute;inset:0;background:linear-gradient(180deg,rgba(16,7,150,.55) 0%,
     transparent 18%,transparent 70%,rgba(0,0,0,.62) 100%)}
  #pin{position:absolute;left:50%;bottom:200px;transform:translateX(-50%);opacity:0;
     display:flex;align-items:center;gap:12px;background:rgba(16,7,150,.92);
     border:2px solid #00B3E3;border-radius:999px;padding:14px 30px;
     box-shadow:0 14px 34px rgba(0,0,0,.5)}
  #pin .ico{font-size:28px}
  #pin .lbl{font-family:"Poppins",sans-serif;font-weight:800;font-size:26px;color:#fff;
     letter-spacing:.04em}
"""


def _shell(img_uri, label, extra_css, extra_dom, js):
    return f"""
<style>{_BASE_CSS}{extra_css}</style>
<div id="photo"><img src="{img_uri}"/></div>
<div id="vig"></div>
{extra_dom}
<div id="pin"><span class="ico">\U0001F4CD</span><span class="lbl">{label}</span></div>
<script>
(function(){{
  window.__timelines = window.__timelines || {{}};
  var tl = gsap.timeline({{paused:true}});
  var D = {DUR};
{js}
  window.__timelines["main"] = tl;
}})();
</script>
"""


# 1 -- push in, pill rises from below.
def _stinger_rise(img_uri, label):
    js = """
  tl.fromTo("#photo img", {scale:1.0}, {scale:1.15, duration:D, ease:"none"}, 0);
  tl.fromTo("#pin", {opacity:0, y:26}, {opacity:1, y:0, duration:0.30, ease:"back.out(2.2)"}, 0.16);
  tl.to("#pin", {opacity:0, y:-12, duration:0.20, ease:"power2.in"}, D - 0.26);
"""
    return _shell(img_uri, label, "", "", js)


# 2 -- pull back, pill irises open behind a cyan underline that sweeps out.
def _stinger_iris(img_uri, label):
    css = """
  #rule{position:absolute;left:50%;bottom:174px;transform:translateX(-50%) scaleX(0);
     width:360px;height:5px;border-radius:3px;background:#00B3E3;
     box-shadow:0 0 18px rgba(0,179,227,.85)}
"""
    dom = '<div id="rule"></div>'
    js = """
  tl.fromTo("#photo img", {scale:1.16}, {scale:1.0, duration:D, ease:"none"}, 0);
  tl.fromTo("#pin", {opacity:0, scaleX:0.55, scaleY:0.8},
                    {opacity:1, scaleX:1, scaleY:1, duration:0.32, ease:"back.out(2.6)"}, 0.14);
  tl.fromTo("#rule", {scaleX:0}, {scaleX:1, duration:0.30, ease:"power3.out"}, 0.24);
  tl.to("#rule", {opacity:0, duration:0.18, ease:"power2.in"}, D - 0.26);
  tl.to("#pin", {opacity:0, scaleY:0.85, duration:0.20, ease:"power2.in"}, D - 0.26);
"""
    return _shell(img_uri, label, css, dom, js)


# 3 -- push with lateral drift, pill wipes in behind a travelling light streak.
def _stinger_streak(img_uri, label):
    css = """
  #pinwrap{position:absolute;left:0;right:0;bottom:0;height:100%;
     clip-path:inset(0 100% 0 0)}
  #streak{position:absolute;top:0;bottom:0;width:120px;left:-200px;
     background:linear-gradient(90deg,transparent,rgba(0,179,227,.85),transparent);
     filter:blur(6px)}
"""
    dom = '<div id="streak"></div>'
    js = """
  tl.fromTo("#photo img", {scale:1.04, x:-26}, {scale:1.18, x:22, duration:D, ease:"none"}, 0);
  tl.fromTo("#streak", {left:-200}, {left:1180, duration:0.44, ease:"power2.inOut"}, 0.06);
  tl.fromTo("#pin", {opacity:0, x:-38}, {opacity:1, x:0, duration:0.30, ease:"power3.out"}, 0.22);
  tl.to("#pin", {opacity:0, x:26, duration:0.20, ease:"power2.in"}, D - 0.26);
"""
    return _shell(img_uri, label, css, dom, js)


STINGERS = [
    ("broll_adl_city", DUR,
     _stinger_rise(_data_uri("adl_city_small.jpg"), "ADELAIDE, SA")),
    ("broll_adl_square", DUR,
     _stinger_iris(_data_uri("adl_square_small.jpg"), "SOUTH AUSTRALIA")),
    ("broll_adl_night", DUR,
     _stinger_streak(_data_uri("adl_night_small.jpg"), "MIGRATION 360 · ADELAIDE")),
]
