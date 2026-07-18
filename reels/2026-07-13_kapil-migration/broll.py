"""Kapil / employer-sponsorship reel B-roll stingers.

This reel is a step-by-step explainer of HOW PFEC gets someone employer-
sponsored, so the connecting lead-in at the START of each process clip is the
natural cutaway moment (the substance is spoken over Kapil's face AFTER the
~1.3s stinger, audio continuous throughout). Four genuine step-transitions
exist in this transcript, so there are four stingers -- a numbered STEP series
that reinforces exactly what's being said at that spot and builds to the 482
payoff:

  broll_1  @ P2 start  "At PFEC Global, our agents will assess..."   -> STEP 1 WE ASSESS YOU
  broll_2  @ P3 start  "...we'll refer you to a recruitment partner" -> STEP 2 MATCHED TO A RECRUITER
  broll_3  @ P4 start  "The recruitment consultant will assess..."   -> STEP 3 YOUR ROLE ASSESSED
  broll_4  @ P6 start  "...the employer may consider sponsoring you" -> STEP 4 EMPLOYER SPONSORS YOU (482)

Pure on-brand motion graphics (PFEC navy/cyan/green/gold/red, Poppins), no
claims, no real scenery. Each is a single paused GSAP timeline so every frame
is seek-safe for the deterministic HyperFrames renderer.
"""

# PFEC palette
NAVY = "#100796"
CYAN = "#00B3E3"
GREEN = "#31EB7C"
GOLD = "#FFC500"
RED = "#E84B37"


def _step_card(num, label, title, sub, accent, icon_svg, title_size=82):
    """A numbered STEP stinger. All text lives in the 22%-54% band so it never
    fights the 2-word caption band (top 62%), the intro plate, or the CTA pill,
    which are composited ON TOP later. title_size drops for longer titles so
    they always stay on ONE line (no wrap onto the subtitle)."""
    return f"""
<style>
  #stg{{position:absolute;inset:0;overflow:hidden;
    background:radial-gradient(125% 95% at 50% 32%,#2016d6 0%,{NAVY} 52%,#0a0560 100%)}}
  #stg .bar{{position:absolute;top:-12%;height:124%;width:150px;opacity:.16;
    transform:skewX(-12deg) translateX(-1600px);filter:blur(1px)}}
  #stg .grid{{position:absolute;inset:0;opacity:.10;
    background-image:linear-gradient(rgba(255,255,255,.5) 1px,transparent 1px),
      linear-gradient(90deg,rgba(255,255,255,.5) 1px,transparent 1px);
    background-size:96px 96px;transform-origin:50% 40%}}
  #stg .chip{{position:absolute;left:0;right:0;top:23%;text-align:center;opacity:0;
    font-family:Poppins,sans-serif;font-weight:800;font-size:38px;letter-spacing:.5em;
    color:{accent};text-indent:.5em}}
  #stg .numwrap{{position:absolute;left:0;right:0;top:27%;text-align:center;opacity:0}}
  #stg .num{{font-family:Poppins,sans-serif;font-weight:900;font-size:280px;line-height:1;
    color:#fff;text-shadow:0 12px 40px rgba(0,0,0,.5)}}
  #stg .numline{{width:0;height:12px;border-radius:6px;background:{accent};margin:6px auto 0;
    box-shadow:0 0 26px 3px {accent}}}
  #stg .icon{{position:absolute;left:50%;top:30.5%;margin-left:150px;opacity:0;
    transform-origin:center}}
  #stg .title{{position:absolute;left:0;right:0;top:47%;text-align:center;opacity:0;
    font-family:Poppins,sans-serif;font-weight:900;font-size:{title_size}px;color:#fff;
    letter-spacing:.01em;text-shadow:0 6px 22px rgba(0,0,0,.5);padding:0 40px;white-space:nowrap}}
  #stg .sub{{position:absolute;left:0;right:0;top:55%;text-align:center;opacity:0;
    font-family:Poppins,sans-serif;font-weight:700;font-size:40px;color:{accent};
    letter-spacing:.02em;padding:0 70px}}
</style>
<div id="stg">
  <div class="grid" id="grid"></div>
  <div class="bar" id="bar1" style="left:18%;background:{CYAN}"></div>
  <div class="bar" id="bar2" style="left:44%;background:{accent}"></div>
  <div class="bar" id="bar3" style="left:68%;background:{GOLD}"></div>
  <div class="chip" id="chip">{label}</div>
  <div class="numwrap" id="numwrap"><div class="num">{num}</div><div class="numline" id="numline"></div></div>
  <div class="icon" id="icon">{icon_svg}</div>
  <div class="title" id="title">{title}</div>
  <div class="sub" id="sub">{sub}</div>
</div>
<script>
(function(){{
  window.__timelines = window.__timelines || {{}};
  var tl = gsap.timeline({{paused:true}});
  // slow ken-burns on the grid so the frame is never static
  tl.fromTo("#grid",{{scale:1.12,opacity:.12}},{{scale:1,opacity:.07,duration:1.35,ease:"sine.out"}},0);
  // brand bars sweep through behind
  tl.to("#bar1",{{x:2600,duration:1.2,ease:"power1.inOut"}},0);
  tl.to("#bar2",{{x:2600,duration:1.2,ease:"power1.inOut"}},0.06);
  tl.to("#bar3",{{x:2600,duration:1.2,ease:"power1.inOut"}},0.12);
  // step chip
  tl.fromTo("#chip",{{opacity:0,y:-18,letterSpacing:"1em"}},
    {{opacity:1,y:0,letterSpacing:"0.5em",duration:0.3,ease:"power2.out"}},0.05);
  // big number pops with overshoot, then an accent underline draws
  tl.fromTo("#numwrap",{{opacity:0,scale:0.45,rotation:-6}},
    {{opacity:1,scale:1,rotation:0,duration:0.34,ease:"back.out(2.4)"}},0.10);
  tl.to("#numline",{{width:190,duration:0.28,ease:"power3.out"}},0.34);
  // icon pop
  tl.fromTo("#icon",{{opacity:0,scale:0,rotation:-24}},
    {{opacity:1,scale:1,rotation:0,duration:0.3,ease:"back.out(2.6)"}},0.30);
  // title + subtitle rise in
  tl.fromTo("#title",{{opacity:0,y:26,scale:0.94}},
    {{opacity:1,y:0,scale:1,duration:0.3,ease:"back.out(1.7)"}},0.34);
  tl.fromTo("#sub",{{opacity:0,y:20}},{{opacity:1,y:0,duration:0.28,ease:"power2.out"}},0.46);
  // graceful exit before we cut back to Kapil
  tl.to(["#chip","#numwrap","#icon","#title","#sub"],
    {{opacity:0,y:-16,duration:0.2,ease:"power2.in"}},1.16);
  window.__timelines["main"]=tl;
}})();
</script>
"""


# --- icons (simple, bold, animate as one unit) ------------------------------ #
_IC_ASSESS = (f'<svg width="120" height="120" viewBox="0 0 120 120" fill="none">'
    f'<circle cx="50" cy="50" r="34" stroke="{CYAN}" stroke-width="9"/>'
    f'<line x1="74" y1="74" x2="104" y2="104" stroke="{CYAN}" stroke-width="11" stroke-linecap="round"/>'
    f'<path d="M37 50l9 9 18-19" stroke="#fff" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></svg>')

_IC_MATCH = (f'<svg width="140" height="120" viewBox="0 0 140 120" fill="none">'
    f'<circle cx="34" cy="60" r="24" fill="{GREEN}"/>'
    f'<circle cx="106" cy="60" r="24" fill="#fff"/>'
    f'<path d="M52 60h36" stroke="{GREEN}" stroke-width="10" stroke-linecap="round" stroke-dasharray="2 16"/>'
    f'<path d="M78 48l14 12-14 12" stroke="{GREEN}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>')

_IC_ROLE = (f'<svg width="130" height="120" viewBox="0 0 130 120" fill="none">'
    f'<rect x="22" y="46" width="86" height="60" rx="9" fill="{GOLD}"/>'
    f'<path d="M50 46v-10a8 8 0 018-8h14a8 8 0 018 8v10" stroke="{GOLD}" stroke-width="9" fill="none"/>'
    f'<path d="M48 74l11 11 22-22" stroke="{NAVY}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _step4_html():
    """The payoff. Same series look but the number gives way to a slammed-in
    "482 VISA" stamp with a shockwave ring -- the loudest beat of the reel."""
    return f"""
<style>
  #stg{{position:absolute;inset:0;overflow:hidden;
    background:radial-gradient(125% 95% at 50% 34%,#2016d6 0%,{NAVY} 50%,#0a0560 100%)}}
  #stg .grid{{position:absolute;inset:0;opacity:.10;
    background-image:linear-gradient(rgba(255,255,255,.5) 1px,transparent 1px),
      linear-gradient(90deg,rgba(255,255,255,.5) 1px,transparent 1px);
    background-size:96px 96px;transform-origin:50% 40%}}
  #stg .bar{{position:absolute;top:-12%;height:124%;width:150px;opacity:.16;
    transform:skewX(-12deg) translateX(-1600px);filter:blur(1px)}}
  #stg .chip{{position:absolute;left:0;right:0;top:24%;text-align:center;opacity:0;
    font-family:Poppins,sans-serif;font-weight:800;font-size:38px;letter-spacing:.5em;
    color:{GOLD};text-indent:.5em}}
  #stg .title{{position:absolute;left:0;right:0;top:30%;text-align:center;opacity:0;
    font-family:Poppins,sans-serif;font-weight:900;font-size:58px;color:#fff;
    letter-spacing:.01em;text-shadow:0 6px 22px rgba(0,0,0,.5);padding:0 40px;white-space:nowrap}}
  #stg .stampwrap{{position:absolute;left:0;right:0;top:43%;text-align:center}}
  #stg .stamp{{display:inline-block;position:relative;border:10px solid {RED};border-radius:26px;
    padding:14px 46px 20px;transform:rotate(-9deg) scale(0);
    box-shadow:0 18px 50px rgba(0,0,0,.5)}}
  #stg .stamp .big{{font-family:Poppins,sans-serif;font-weight:900;font-size:210px;line-height:1;
    color:{GOLD};letter-spacing:.02em;text-shadow:0 6px 18px rgba(0,0,0,.35)}}
  #stg .stamp .visa{{font-family:Poppins,sans-serif;font-weight:900;font-size:66px;
    letter-spacing:.34em;color:#fff;text-indent:.34em;margin-top:2px}}
  #stg .ring{{position:absolute;left:50%;top:52%;width:120px;height:120px;margin:-60px 0 0 -60px;
    border:8px solid {GREEN};border-radius:50%;opacity:0}}
</style>
<div id="stg">
  <div class="grid" id="grid"></div>
  <div class="bar" id="bar1" style="left:16%;background:{CYAN}"></div>
  <div class="bar" id="bar2" style="left:46%;background:{RED}"></div>
  <div class="bar" id="bar3" style="left:72%;background:{GOLD}"></div>
  <div class="ring" id="ring"></div>
  <div class="chip" id="chip">STEP 4</div>
  <div class="title" id="title">EMPLOYER SPONSORS YOU</div>
  <div class="stampwrap"><div class="stamp" id="stamp">
    <div class="big">482</div><div class="visa">VISA</div>
  </div></div>
</div>
<script>
(function(){{
  window.__timelines = window.__timelines || {{}};
  var tl = gsap.timeline({{paused:true}});
  tl.fromTo("#grid",{{scale:1.12,opacity:.12}},{{scale:1,opacity:.07,duration:1.4,ease:"sine.out"}},0);
  tl.to("#bar1",{{x:2600,duration:1.2,ease:"power1.inOut"}},0);
  tl.to("#bar2",{{x:2600,duration:1.2,ease:"power1.inOut"}},0.06);
  tl.to("#bar3",{{x:2600,duration:1.2,ease:"power1.inOut"}},0.12);
  tl.fromTo("#chip",{{opacity:0,y:-18,letterSpacing:"1em"}},
    {{opacity:1,y:0,letterSpacing:"0.5em",duration:0.3,ease:"power2.out"}},0.05);
  tl.fromTo("#title",{{opacity:0,y:22,scale:0.94}},
    {{opacity:1,y:0,scale:1,duration:0.3,ease:"back.out(1.7)"}},0.12);
  // the stamp SLAMS in (fast, hard overshoot) -- the climax beat
  tl.fromTo("#stamp",{{scale:0,rotation:-24}},
    {{scale:1,rotation:-9,duration:0.3,ease:"back.out(3)"}},0.34);
  // shockwave ring expands + fades the instant the stamp lands
  tl.fromTo("#ring",{{scale:0.4,opacity:0.9}},
    {{scale:3.4,opacity:0,duration:0.5,ease:"power2.out"}},0.40);
  // tiny settle wobble
  tl.to("#stamp",{{rotation:-6,duration:0.16,ease:"sine.inOut"}},0.66);
  tl.to("#stamp",{{rotation:-9,duration:0.2,ease:"sine.inOut"}},0.82);
  tl.to(["#chip","#title","#stamp"],{{opacity:0,y:-16,duration:0.2,ease:"power2.in"}},1.20);
  window.__timelines["main"]=tl;
}})();
</script>
"""


def _transition_html():
    """A short branded bridge into the closing CTA clip -- sweeping brand bars +
    a 'READY TO GET STARTED?' headline and cascading down-chevrons that hand the
    eye off to the CTA pill that lands right after. Motion-heavy so it reads as a
    transition, not another info card. Text sits high (34-58%) to clear the
    caption band and the CTA pill."""
    return f"""
<style>
  #tr{{position:absolute;inset:0;overflow:hidden;
    background:radial-gradient(125% 95% at 50% 40%,#2016d6 0%,{NAVY} 52%,#0a0560 100%)}}
  #tr .bar{{position:absolute;top:-12%;height:124%;width:170px;opacity:.18;
    transform:skewX(-12deg) translateX(-1700px);filter:blur(1px)}}
  #tr .head{{position:absolute;left:0;right:0;top:34%;text-align:center;opacity:0;
    font-family:Poppins,sans-serif;font-weight:900;font-size:78px;color:#fff;
    letter-spacing:.01em;text-shadow:0 6px 22px rgba(0,0,0,.5);padding:0 50px;white-space:nowrap}}
  #tr .chev{{position:absolute;left:50%;width:120px;height:120px;margin-left:-60px;opacity:0;
    border-right:22px solid;border-bottom:22px solid;transform:rotate(45deg);border-radius:6px}}
  #tr #c1{{top:47%;border-color:{GOLD}}}
  #tr #c2{{top:53%;border-color:{CYAN}}}
  #tr #c3{{top:59%;border-color:{GREEN}}}
</style>
<div id="tr">
  <div class="bar" id="tb1" style="left:14%;background:{CYAN}"></div>
  <div class="bar" id="tb2" style="left:44%;background:{GOLD}"></div>
  <div class="bar" id="tb3" style="left:72%;background:{GREEN}"></div>
  <div class="head" id="thead">READY TO GET STARTED?</div>
  <div class="chev" id="c1"></div>
  <div class="chev" id="c2"></div>
  <div class="chev" id="c3"></div>
</div>
<script>
(function(){{
  window.__timelines = window.__timelines || {{}};
  var tl = gsap.timeline({{paused:true}});
  tl.to("#tb1",{{x:2700,duration:1.15,ease:"power1.inOut"}},0);
  tl.to("#tb2",{{x:2700,duration:1.15,ease:"power1.inOut"}},0.05);
  tl.to("#tb3",{{x:2700,duration:1.15,ease:"power1.inOut"}},0.10);
  tl.fromTo("#thead",{{opacity:0,y:24,scale:0.92}},
    {{opacity:1,y:0,scale:1,duration:0.32,ease:"back.out(1.8)"}},0.10);
  // chevrons cascade downward, then pulse toward the CTA
  [["#c1",0.30],["#c2",0.40],["#c3",0.50]].forEach(function(c){{
    tl.fromTo(c[0],{{opacity:0,y:-16}},{{opacity:0.95,y:0,duration:0.24,ease:"power2.out"}},c[1]);
  }});
  tl.to(["#c1","#c2","#c3"],{{y:16,duration:0.4,ease:"sine.inOut",repeat:1,yoyo:true}},0.72);
  tl.to(["#thead","#c1","#c2","#c3"],{{opacity:0,y:-14,duration:0.2,ease:"power2.in"}},1.16);
  window.__timelines["main"]=tl;
}})();
</script>
"""


STINGERS = [
    ("broll_1", 1.35, _step_card("01", "STEP 1", "WE ASSESS YOU",
                                 "eligibility · qualifications · visa options",
                                 CYAN, _IC_ASSESS)),
    ("broll_2", 1.35, _step_card("02", "STEP 2", "MATCHED TO A RECRUITER",
                                 "referred to our partner consultants",
                                 GREEN, _IC_MATCH, title_size=58)),
    ("broll_3", 1.35, _step_card("03", "STEP 3", "YOUR ROLE ASSESSED",
                                 "checked for an available position",
                                 GOLD, _IC_ROLE)),
    ("broll_4", 1.40, _step4_html()),
    ("broll_5", 1.35, _transition_html()),
]
