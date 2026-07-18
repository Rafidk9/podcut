"""B-roll stingers for the Tushar / Migration360 Roadshow promo. 3 cutaways,
each tied to a genuine connecting/filler beat in THIS transcript (see
broll_plan.json for the judged boundaries):

  broll_1 @ 4.70s (P1->P2 cut, over "And go."): reinforces the "stop
  scrolling" hook that just landed -- a scroll feed physically skids to a halt.
  broll_2 @ 20.40s (P3->P4 cut, over "And that's why"): the PFEC Global /
  Migration360 Roadshow brand reveal, landing as he actually says the name.
  broll_3 @ 26.05s (P4->P5 cut, over "And for one day only"): urgency stamp
  on the one-day-only free consultation offer.

Deliberately SKIPPED: the P2->P3 cut ("One move...") and P5->P6 cut ("A real
conversation...") are stakes/reassurance beats delivered as a spoken pause by
Tushar himself -- cutting away there would blunt the moment. The P6->P7 cut
("There are limited spots...") is where the persistent roadshow city card
takes over as the visual interest -- no need to also cut to a full-frame
stinger right as that lands."""

# --------------------------------------------------------------------------- #
# broll_1: STOP SCROLLING -- a feed of ghost caption lines scrolls fast then
# slams to a halt with a red brake-flash, right as "And go." (pure connector)
# plays under it.
# --------------------------------------------------------------------------- #
BROLL_1 = """
<style id="s1">
  #bg1{position:absolute;inset:0;background:linear-gradient(165deg,#0a0a1a,#100796 75%)}
  #feed{position:absolute;left:0;right:0;top:0;display:flex;flex-direction:column;
        align-items:center;gap:26px;padding-top:120px}
  #feed .ln{width:640px;height:46px;border-radius:10px;background:rgba(255,255,255,.14)}
  #flash{position:absolute;inset:0;background:#E84B37;opacity:0}
  .h1{position:absolute;left:0;right:0;top:40%;text-align:center;font-family:Poppins,sans-serif;
      font-weight:900;font-size:96px;color:#fff;opacity:0;letter-spacing:.01em;
      text-shadow:0 8px 24px rgba(0,0,0,.5)}
  .h2{position:absolute;left:0;right:0;top:52%;text-align:center;font-family:Poppins,sans-serif;
      font-weight:700;font-size:38px;color:#FFC500;opacity:0}
</style>
<div id="bg1"></div>
<div id="feed">
  <div class="ln"></div><div class="ln"></div><div class="ln"></div>
  <div class="ln"></div><div class="ln"></div><div class="ln"></div>
</div>
<div id="flash"></div>
<div class="h1" id="h1a">STOP.</div>
<div class="h2" id="h2a">THIS COULD BE YOU.</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.fromTo("#feed",{y:-260},{y:280,duration:.34,ease:"power3.in"},0);
  tl.to("#feed",{y:296,duration:.5,ease:"elastic.out(1,0.4)"},0.34);
  tl.to("#flash",{opacity:.55,duration:.06,ease:"power1.out"},0.34);
  tl.to("#flash",{opacity:0,duration:.22,ease:"power2.out"},0.4);
  tl.fromTo("#h1a",{opacity:0,scale:.6,rotation:-4},
    {opacity:1,scale:1,rotation:0,duration:.26,ease:"back.out(2.6)"},0.4);
  tl.fromTo("#h2a",{opacity:0,y:14},{opacity:1,y:0,duration:.24,ease:"power2.out"},0.58);
  tl.to(["#h1a","#h2a"],{opacity:0,duration:.18,ease:"power2.in"},1.02);
  window.__timelines["main"]=tl;
})();
</script>
"""

# --------------------------------------------------------------------------- #
# broll_2: PFEC GLOBAL / MIGRATION360 ROADSHOW brand reveal -- a map pin drops
# in, brand colour bars sweep, wordmark lands right as "PFEC Global" is said.
# --------------------------------------------------------------------------- #
BROLL_2 = """
<style id="s2">
  html,body{background:#100796}
  .bar{position:absolute;top:-10%;height:120%;width:220px;transform:skewX(-12deg) translateX(-1400px)}
  #pinWrap{position:absolute;left:50%;top:26%;transform:translateX(-50%) translateY(-40px) scale(0);
           transform-origin:bottom center}
  #pinWrap svg{width:120px;height:150px}
  .word{position:absolute;left:0;right:0;top:46%;transform:translateY(-50%);text-align:center;
        font-family:"Poppins",sans-serif;font-weight:800;color:#fff;opacity:0}
  .word .line1{font-size:64px;letter-spacing:.02em}
  .word .line2{font-size:38px;font-weight:700;color:#FFC500;margin-top:12px;letter-spacing:.05em}
</style>
<div class="bar" id="b1" style="left:10%;background:#00B3E3"></div>
<div class="bar" id="b2" style="left:32%;background:#31EB7C"></div>
<div class="bar" id="b3" style="left:54%;background:#FFC500"></div>
<div id="pinWrap">
  <svg viewBox="0 0 120 150" fill="none">
    <path d="M60 4C31 4 8 27 8 56c0 40 52 88 52 88s52-48 52-88C112 27 89 4 60 4z" fill="#E84B37"/>
    <circle cx="60" cy="56" r="24" fill="#fff"/>
  </svg>
</div>
<div class="word" id="w">
  <div class="line1">PFEC GLOBAL</div>
  <div class="line2">MIGRATION360 ROADSHOW</div>
</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.to("#b1",{x:2400,duration:.5,ease:"power1.inOut"},0);
  tl.to("#b2",{x:2400,duration:.5,ease:"power1.inOut"},0.04);
  tl.to("#b3",{x:2400,duration:.5,ease:"power1.inOut"},0.08);
  tl.to("#pinWrap",{scale:1,y:0,duration:.34,ease:"bounce.out"},0.1);
  tl.fromTo("#w",{opacity:0,y:16,scale:.92},
    {opacity:1,y:0,scale:1,duration:.26,ease:"back.out(1.6)"},0.46);
  tl.to("#w",{opacity:0,duration:.16,ease:"power2.in"},1.06);
  tl.to("#pinWrap",{opacity:0,duration:.16,ease:"power2.in"},1.06);
  window.__timelines["main"]=tl;
})();
</script>
"""

# --------------------------------------------------------------------------- #
# broll_3: ONE DAY ONLY -- a stopwatch hand sweeps once around and a red
# urgency stamp slams down, landing on "one day only".
# --------------------------------------------------------------------------- #
BROLL_3 = """
<style id="s3">
  #bg3{position:absolute;inset:0;background:linear-gradient(200deg,#100796,#0a0664 60%)}
  #watchWrap{position:absolute;left:50%;top:30%;transform:translateX(-50%) scale(0)}
  #watchWrap svg{width:220px;height:220px}
  #handSweep{transform-origin:60px 60px}
  .stamp{position:absolute;left:50%;top:58%;transform:translateX(-50%) rotate(-6deg) scale(0);
         background:#E84B37;color:#fff;font-family:Poppins,sans-serif;font-weight:900;
         font-size:56px;letter-spacing:.03em;padding:14px 40px;border-radius:10px;
         box-shadow:0 14px 34px rgba(0,0,0,.4);white-space:nowrap}
  .sub{position:absolute;left:0;right:0;top:72%;text-align:center;font-family:Poppins,sans-serif;
       font-weight:700;font-size:32px;color:#FFC500;opacity:0}
</style>
<div id="bg3"></div>
<div id="watchWrap">
  <svg viewBox="0 0 120 120" fill="none">
    <circle cx="60" cy="60" r="52" stroke="#fff" stroke-width="8"/>
    <circle cx="60" cy="60" r="4" fill="#FFC500"/>
    <line id="handSweep" x1="60" y1="60" x2="60" y2="18" stroke="#FFC500" stroke-width="7" stroke-linecap="round"/>
  </svg>
</div>
<div class="stamp" id="stamp">ONE DAY ONLY</div>
<div class="sub" id="sub">FREE 1-ON-1 CONSULT</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.to("#watchWrap",{scale:1,duration:.3,ease:"back.out(2)"},0);
  tl.to("#handSweep",{rotation:360,duration:.6,ease:"power1.inOut"},0.05);
  tl.fromTo("#stamp",{opacity:0,scale:1.6,rotate:-6},
    {opacity:1,scale:1,rotate:-6,duration:.24,ease:"power3.out"},0.5);
  tl.fromTo("#sub",{opacity:0,y:10},{opacity:1,y:0,duration:.22,ease:"power2.out"},0.68);
  tl.to(["#watchWrap","#stamp","#sub"],{opacity:0,duration:.16,ease:"power2.in"},1.02);
  window.__timelines["main"]=tl;
})();
</script>
"""

STINGERS = [
    ("broll_1", 1.3, BROLL_1),
    ("broll_2", 1.3, BROLL_2),
    ("broll_3", 1.3, BROLL_3),
]
