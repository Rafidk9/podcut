"""B-roll stinger for this reel's cold open: a 1.1s branded "road tour" hit
that plays over segment 0's first 1.1s ("We're comi-ng on tour..." -- ASR
originally misheard this as "shore", corrected via content.json asr_fix),
masked by the standard grid-wipe at the very start of the video (boundary
0.0 in broll_plan.json -- there's no prior footage to mask a cut FROM, so
the wipe just plays as a cold-open reveal instead).

A car drives along the SAME AU silhouette outline used elsewhere in this
reel's brand graphics (build_captions.py's #flightMap uses the identical
path/viewBox) -- literally touring the country's edge, landing 6 city pins
along the way -- matching "coming on tour" rather than a flight motif (the
city list moment later in the video uses its own front-overlay landmark
sweep instead, per user direction: nothing should hide behind the subject)."""

TOUR_OPEN = """
<style id="to">
  html,body{background:linear-gradient(135deg,#100796 0%,#7a1a8a 55%,#E84B37 100%)}
  #stage{position:absolute;left:50%;top:44%;width:820px;height:706px;
         transform:translate(-50%,-50%) scale(.85);opacity:0}
  #stage svg{position:absolute;left:0;top:0;width:820px;height:706px;
             filter:drop-shadow(0 14px 34px rgba(0,0,0,.45))}
  .pin{position:absolute;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;
       background:#FFC500;border:3px solid #fff;opacity:0;transform:scale(0);
       box-shadow:0 4px 12px rgba(0,0,0,.4)}
  .pulse{position:absolute;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;
         border:4px solid #fff;opacity:0}
  #car{position:absolute;width:76px;height:44px;margin:-22px 0 0 -38px;opacity:0;
       filter:drop-shadow(0 6px 12px rgba(0,0,0,.5))}
  #car svg{width:100%;height:100%}
  #dust{position:absolute;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;
        background:rgba(255,255,255,.7);opacity:0}
  #burstFlash{position:absolute;inset:0;background:#fff;opacity:0}
  #impactRing{position:absolute;width:40px;height:40px;margin:-20px 0 0 -20px;
              border-radius:50%;border:7px solid #FFC500;opacity:0}
  #stamp{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);text-align:center;opacity:0}
  #stamp .l1{font-family:"Poppins",sans-serif;font-weight:900;font-size:104px;color:#fff;
             letter-spacing:.01em;text-shadow:0 8px 26px rgba(0,0,0,.5)}
  #stamp .l2{font-family:"Poppins",sans-serif;font-weight:800;font-size:52px;color:#FFC500;
             letter-spacing:.04em;margin-top:6px;text-shadow:0 6px 18px rgba(0,0,0,.5)}
</style>
<div id="burstFlash"></div>
<div id="stage">
  <svg viewBox="0 0 100 86">
    <path d="M 68 2 L 72 10 L 78 22 L 80 32 L 76 44 L 70 52 L 60 58 L 48 54 L 36 56
     L 20 58 L 12 50 L 8 38 L 10 24 L 16 14 L 26 8 L 34 12 L 40 6 L 48 4
     L 52 14 L 58 12 L 62 2 Z" fill="rgba(255,255,255,.14)" stroke="#fff" stroke-width="1.4"/>
    <ellipse cx="66" cy="70" rx="5" ry="4" fill="rgba(255,255,255,.14)" stroke="#fff" stroke-width="1.2"/>
  </svg>
  <div class="pin" id="p0" style="left:640px;top:181px"></div>
  <div class="pulse" id="u0" style="left:640px;top:181px"></div>
  <div class="pin" id="p1" style="left:623px;top:361px"></div>
  <div class="pulse" id="u1" style="left:623px;top:361px"></div>
  <div class="pin" id="p2" style="left:492px;top:476px"></div>
  <div class="pulse" id="u2" style="left:492px;top:476px"></div>
  <div class="pin" id="p3" style="left:295px;top:460px"></div>
  <div class="pulse" id="u3" style="left:295px;top:460px"></div>
  <div class="pin" id="p4" style="left:98px;top:411px"></div>
  <div class="pulse" id="u4" style="left:98px;top:411px"></div>
  <div class="pin" id="p5" style="left:82px;top:197px"></div>
  <div class="pulse" id="u5" style="left:82px;top:197px"></div>
  <div id="dust"></div>
  <div id="impactRing"></div>
  <div id="car">
    <svg viewBox="0 0 60 34">
      <path d="M4 24 Q4 14 14 14 L20 6 L40 6 L46 14 L56 14 Q58 14 58 20 L58 24 Z" fill="#FFC500"/>
      <rect x="4" y="20" width="54" height="6" rx="3" fill="#FFC500"/>
      <rect x="22" y="10" width="16" height="8" rx="2" fill="#100796" opacity="0.55"/>
      <circle cx="16" cy="26" r="6" fill="#1A1A1A"/>
      <circle cx="16" cy="26" r="2.4" fill="#fff"/>
      <circle cx="44" cy="26" r="6" fill="#1A1A1A"/>
      <circle cx="44" cy="26" r="2.4" fill="#fff"/>
    </svg>
  </div>
</div>
<div id="stamp">
  <div class="l1">6 CITIES</div>
  <div class="l2">1 MISSION</div>
</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  // background + map are visible almost instantly -- the DRAMA is the car,
  // which bursts onto screen from frame one, not a slow fade.
  tl.fromTo("#stage",{opacity:0},{opacity:1,duration:.06,ease:"power1.out"},0);
  tl.fromTo("#burstFlash",{opacity:0},{opacity:.85,duration:.05,ease:"power1.out"},0);
  tl.to("#burstFlash",{opacity:0,duration:.16,ease:"power2.out"},0.05);

  var route = [
    {left:558, top:16},
    {left:640, top:181},
    {left:623, top:361},
    {left:492, top:476},
    {left:295, top:460},
    {left:98,  top:411},
    {left:82,  top:197},
    {left:213, top:66}
  ];

  // BURST: the car rockets in from off-screen right, oversized, and slams
  // into its starting position with an overshoot -- the "bursting into the
  // screen" entrance, right at the top of the very first second. Duration
  // is long enough (~0.3s, ~9 frames @30fps) to actually read as motion,
  // not just a pop -- a too-short tween resolves in 1-2 frames and looks
  // like the car simply appears already-landed.
  // "power1.out" (not "back.out") for the travel itself -- back-style easing
  // front-loads almost all its motion into the first third of the tween
  // (it's already overshooting the target by ~30% time), which reads as
  // "just appears" rather than a visible fly-in. power1.out keeps the
  // motion evenly readable across the whole duration; the "impact" character
  // (overshoot/bounce) is a separate quick pulse added once it lands.
  tl.set("#car",{left:1650, top:-40, scale:3.4, opacity:0, rotation:14}, 0);
  tl.to("#car",{opacity:1, duration:.05}, 0);
  tl.to("#car",{left:route[0].left, top:route[0].top, scale:1, rotation:0,
    duration:.32, ease:"power1.out"}, 0.0);
  tl.fromTo("#car",{scale:1},{scale:1.14,duration:.06,ease:"power1.out"},0.32);
  tl.to("#car",{scale:1,duration:.09,ease:"power1.in"},0.38);
  tl.set("#impactRing",{left:route[0].left, top:route[0].top}, 0.32);
  tl.fromTo("#impactRing",{opacity:.9,scale:.3},{opacity:0,scale:3.4,duration:.3,ease:"power1.out"},0.32);
  tl.to("#stage",{x:"+=7",duration:.028,ease:"power1.inOut",yoyo:true,repeat:3},0.32);

  // then it drives the AU outline (same path coords as the SVG above, in
  // px): top-right -> down the east coast -> across the south -> up the
  // west -- literally "touring" the country's edge.
  var carKf = {};
  route.forEach(function(pt, i){
    var pct = Math.round(i / (route.length - 1) * 100) + "%";
    carKf[pct] = {left:pt.left, top:pt.top};
  });
  tl.to("#car",{keyframes:carKf, duration:.42, ease:"power1.inOut"},0.36);
  tl.to("#car",{opacity:0,duration:.12,ease:"power2.in"},0.78);
  // trailing dust puffs: 3 ghost copies lagging slightly behind the car
  for (var d=0; d<3; d++){
    var dust = document.getElementById("dust").cloneNode(true);
    dust.id = "dust"+d;
    document.getElementById("stage").appendChild(dust);
    var lag = 0.05 + d*0.05;
    tl.to(dust, {keyframes:carKf, duration:.42, ease:"power1.inOut"}, 0.36 - lag);
    tl.fromTo(dust, {opacity:.55,scale:.8}, {opacity:0,scale:1.6,duration:.25,ease:"power1.out"}, 0.36-lag+0.02);
  }

  // 6 landing pins pop in a quick ripple as the car passes each one
  var order=[0,1,2,3,4,5];
  order.forEach(function(idx,i){
    var at = 0.40 + i*0.062;
    tl.fromTo("#p"+idx,{opacity:0,scale:0},{opacity:1,scale:1,duration:.14,ease:"back.out(3)"},at);
    tl.fromTo("#u"+idx,{opacity:.9,scale:.4},{opacity:0,scale:4.5,duration:.4,ease:"power1.out"},at);
  });

  tl.fromTo("#stamp",{opacity:0,scale:.8,y:14},
    {opacity:1,scale:1,y:0,duration:.22,ease:"back.out(2.2)"},0.84);
  tl.to("#stamp",{opacity:0,duration:.14,ease:"power2.in"},1.00);
  tl.to("#stage",{opacity:0,duration:.14,ease:"power2.in"},1.00);
  window.__timelines["main"]=tl;
})();
</script>
"""

STINGERS = [
    ("tour_open", 1.1, TOUR_OPEN),
]
