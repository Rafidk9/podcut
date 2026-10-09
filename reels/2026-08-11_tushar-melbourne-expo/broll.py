"""B-roll stingers for the Tushar / Just Ask Expo (Melbourne) promo.

ONE cutaway only. Per reels/README.md the count is judged from this reel's own
script, not fixed -- and this 28.6s is almost wall-to-wall hard information
(hook question, date, time, venue, who's on site, CTA). Exactly one span is
rhetorical rather than factual:

  broll_1 @ 3.10s (seg0->seg1 cut, over "You don't need to guess.")
      -- a connector that sets up the payoff line rather than carrying any
      fact of its own. Cutting away here costs the viewer nothing, and cutting
      BACK lands right before the full-screen "ASK" slam at 4.47s, so the
      stinger reads as the setup and Tushar himself is the punchline.

Deliberately SKIPPED, and why (all are segment openings, which is the only
place insert_broll.py can splice):
  seg2 "At the Just Ask Expo on the 25th of August..." -- the date/time/venue,
       the single most important information in the reel.
  seg3 "Real questions, real answers" -- the promise; it also already carries
       the REAL ANSWERS badge as its visual.
  seg4 "University reps will be here as well" -- a distinct selling point.
  seg5 "Spaces are limited." -- the urgency beat driving the CTA.
Covering any of those would put motion graphics over words the viewer has to
actually hear, which is exactly what the B-roll rule exists to prevent.

Splice length is 1.0s (broll_plan.json "broll_dur"), shorter than the usual
1.1-1.3s: "You don't need to guess." runs 3.22-3.96s on the output timeline,
so 1.0s covers the whole phrase and returns to Tushar at 4.10s -- clear of
both the word "ask" (4.62s) and the hero slam's entrance (4.47s). The stinger
itself is rendered at 1.3s so there is tail to spare if the splice is ever
lengthened.
"""

# --------------------------------------------------------------------------- #
# broll_1: GUESSING -- three dotted paths fork upward from a single point, each
# dead-ending in a question mark that jitters with uncertainty. Visualises the
# exact words underneath it ("You don't need to guess"): many possible routes,
# no answer at the end of any of them. No claims, no scenery, no wordmark --
# pure on-brand motion graphics, safe over a connecting phrase.
#
# The three ? marks use cyan / gold / red rather than one colour so the fork
# reads as three genuinely DIFFERENT options rather than one repeated, and the
# jitter is deliberately unresolved -- nothing here lands or settles, because
# the resolution is Tushar saying "ask someone who actually knows" as we cut
# back to him.
# --------------------------------------------------------------------------- #
BROLL_1 = """
<style id="s1">
  html,body{background:#0a0a1a}
  #bgq{position:absolute;inset:0;background:radial-gradient(120% 90% at 50% 108%,#1b1499 0%,#0a0a1a 68%)}
  #forkwrap{position:absolute;left:0;right:0;top:0;bottom:0}
  /* The ? marks are positioned against the FRAME, but the paths they belong to
     are in the svg's own viewBox -- so their coordinates have to be mapped, not
     eyeballed. With the svg at 900x760, left:50%, top:46%, translate(-50%,-50%)
     in a 1080x1920 frame (viewBox is 1:1 with the px size), the svg's origin
     lands at frame x=90, y=503, so a viewBox point (vx,vy) sits at frame
     (90+vx, 503+vy). That puts the three path tips at:
         p1 (180,360) -> (270, 863) = left 25.0%, top 45.0%
         p2 (450,250) -> (540, 753) = left 50.0%, top 39.2%
         p3 (720,360) -> (810, 863) = left 75.0%, top 45.0%
     Each ? is centred (translate -50%,-50%) 75px above its tip so the glyph
     sits ON the end of its path. The first pass guessed 20/50/80% and 26/17/26%
     and the marks floated ~450px clear of the paths -- they read as unrelated
     decoration rather than the dead-end of each route. */
  #forkwrap svg{position:absolute;left:50%;top:46%;transform:translate(-50%,-50%);
                width:900px;height:760px;overflow:visible}
  .pth{fill:none;stroke-width:9;stroke-linecap:round;stroke-dasharray:22 26;opacity:.85}
  .qm{position:absolute;font-family:Poppins,sans-serif;font-weight:900;font-size:132px;
      opacity:0;text-shadow:0 10px 28px rgba(0,0,0,.55);transform:translate(-50%,-50%)}
  #q1{left:25%;top:41.0%;color:#00B3E3}
  #q2{left:50%;top:35.3%;color:#FFC500}
  #q3{left:75%;top:41.0%;color:#E84B37}
  #ghead{position:absolute;left:0;right:0;top:74%;text-align:center;font-family:Poppins,sans-serif;
         font-weight:900;font-size:82px;color:#fff;opacity:0;letter-spacing:.02em;
         text-shadow:0 8px 24px rgba(0,0,0,.55)}
</style>
<div id="bgq"></div>
<div id="forkwrap">
  <svg viewBox="0 0 900 760">
    <path class="pth" id="p1" stroke="#00B3E3" d="M450 720 C450 560 300 520 180 360"/>
    <path class="pth" id="p2" stroke="#FFC500" d="M450 720 C450 540 450 440 450 250"/>
    <path class="pth" id="p3" stroke="#E84B37" d="M450 720 C450 560 600 520 720 360"/>
  </svg>
</div>
<div class="qm" id="q1">?</div>
<div class="qm" id="q2">?</div>
<div class="qm" id="q3">?</div>
<div id="ghead">GUESSING?</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});

  // Paths draw outward from the single starting point, staggered so the fork
  // reads as a decision opening up rather than three lines appearing at once.
  ["#p1","#p2","#p3"].forEach(function(sel,i){
    var el = document.querySelector(sel);
    var len = el.getTotalLength();
    gsap.set(el,{strokeDasharray:len,strokeDashoffset:len});
    tl.to(el,{strokeDashoffset:0,duration:.42,ease:"power2.out"}, 0.02 + i*0.06);
  });

  // Each ? pops in at the end of its own path, then jitters -- never settling.
  [["#q1",0.34],["#q2",0.40],["#q3",0.46]].forEach(function(pair){
    var sel = pair[0], t = pair[1];
    tl.fromTo(sel,{opacity:0,scale:.5,rotation:-10},
      {opacity:1,scale:1,rotation:0,duration:.24,ease:"back.out(2.8)"}, t);
    tl.to(sel,{rotation:6,duration:.13,ease:"sine.inOut",yoyo:true,repeat:3}, t+0.26);
  });

  tl.fromTo("#ghead",{opacity:0,y:18},{opacity:1,y:0,duration:.22,ease:"power2.out"},0.52);

  // Everything clears before the splice ends so the cut back to Tushar is on
  // a clean frame, not mid-animation.
  tl.to(["#q1","#q2","#q3","#ghead"],{opacity:0,duration:.15,ease:"power2.in"},0.90);
  tl.to("#forkwrap",{opacity:0,duration:.15,ease:"power2.in"},0.92);

  window.__timelines["main"]=tl;
})();
</script>
"""

STINGERS = [
    ("broll_1", 1.3, BROLL_1),
]
