"""B-roll stingers for the Salman / Just Ask Expo (Sydney) promo.

ONE cutaway only, which is what the user asked for and also what this script
supports. Per reels/README.md the count is judged from the reel's own
transcript, and this 25.0s is dense with hard information -- the hook
question, the campaign name, the date, the time, the three cities, the three
roles on site. insert_broll.py can only splice at a SEGMENT OPENING, which
narrows the candidates to five moments:

  seg0 @ 0.00  "Oh, are you also stuck?"        -- the hook; nothing to cut to yet.
  seg1 @ 5.80  "One event, one afternoon..."     -- the punch line, and his
               walk-toward-camera IS the visual.
  seg2 @ 9.10  "Is the Just Ask Expo by PFEC..." -- the campaign name, then the
               date/time, which date_behind.py already owns.
  seg3 @ 15.55 "in our Melbourne, Sydney and..." -- the three cities, and the
               expo banner already lands here.
  seg4 @ 18.65 "There will be university rep..." -- CHOSEN.

seg4 opens on "There will be" (18.740-19.219), a pure connecting phrase
carrying no fact of its own, and runs straight into the one genuine LIST in
the script. That makes it the only segment opening where a cutaway costs the
viewer nothing on entry.

Splice length is 4.45s (18.65 -> 23.10), which deliberately covers the whole
list rather than just the connector. This follows the exception the
2026-08-11 Tushar reel documented for its match cut: the B-roll rule exists
to stop graphics obscuring spoken facts, and here the graphic IS the fact
being spoken -- each role card lands on the words naming that role, so the
cutaway presents the list instead of hiding it. Nothing is lost on the way
out either: the splice returns to him at 23.10, in the 0.06s gap before
"There will be a real conversation" (23.159), so he delivers the closing line
and the CTA on camera.

Card entrances are keyed to the output-timeline word times, minus the 18.65
splice start:

    "university representative"  19.559 -> 0.909 local
    "migration agent"            20.979 -> 2.329 local
    "and education counsellor"   21.839 -> 3.189 local
    list ends                    23.099 -> 4.449 local

Rendered at 4.7s so there is tail to spare if the splice is ever lengthened.
"""

# --------------------------------------------------------------------------- #
# broll_1: WHO'S IN THE ROOM -- three role cards deal in from alternating
# sides onto a navy field, each one arriving exactly as Salman names it.
#
# The three cards take cyan / gold / green rather than one repeated colour so
# they read as three genuinely different people to talk to, matching how the
# badges elsewhere in this reel are coloured. Each card keeps a fat left rule
# in its own colour and a simple glyph, so the row scans as a list even at
# thumbnail size. No claims, no scenery, no wordmark -- pure on-brand motion
# graphics, and every word on screen is a word he says.
#
# Cards do NOT clear one at a time: they stack and hold, so by the end of the
# cutaway all three are on screen together as a single "here's who you get"
# frame, which is the payoff the list is building to. The whole stack clears
# at 4.20-4.38 so the return to camera at 4.45 lands on a settled frame.
# --------------------------------------------------------------------------- #
BROLL_1 = """
<style id="s1">
  html,body{background:#0a0a1a}
  #bg{position:absolute;inset:0;
      background:radial-gradient(130% 85% at 50% 10%,#1b1499 0%,#0a0a1a 70%)}
  /* Two soft brand orbs drifting behind the cards -- same trick as the reel's
     decor layer, so the cutaway doesn't read as a flat slide dropped in. */
  .orb{position:absolute;border-radius:50%;filter:blur(70px);opacity:.30}
  #o1{width:520px;height:520px;left:-140px;top:180px;background:#00B3E3}
  #o2{width:460px;height:460px;right:-120px;bottom:220px;background:#FFC500}
  #head{position:absolute;left:0;right:0;top:16.5%;text-align:center;
        font-family:Poppins,sans-serif;font-weight:900;font-size:74px;color:#fff;
        letter-spacing:.01em;opacity:0;text-shadow:0 8px 26px rgba(0,0,0,.55)}
  #rule{position:absolute;left:50%;top:23.2%;width:0;height:10px;border-radius:5px;
        background:#FFC500;transform:translateX(-50%)}
  .card{position:absolute;left:70px;width:940px;height:236px;border-radius:34px;
        background:rgba(255,255,255,.97);opacity:0;
        box-shadow:0 22px 60px rgba(0,0,0,.45);overflow:hidden;
        display:flex;align-items:center;gap:34px;padding:0 42px}
  .card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:20px}
  #c1{top:32.0%}
  #c2{top:48.5%}
  #c3{top:65.0%}
  #c1::before{background:#00B3E3}
  #c2::before{background:#FFC500}
  #c3::before{background:#31EB7C}
  .ico{flex:0 0 128px;height:128px;border-radius:28px;display:flex;
       align-items:center;justify-content:center;font-size:66px;margin-left:14px}
  #c1 .ico{background:rgba(0,179,227,.16)}
  #c2 .ico{background:rgba(255,197,0,.20)}
  #c3 .ico{background:rgba(49,235,124,.18)}
  /* nowrap + 58px: at the first pass's 72px "MIGRATION AGENTS" wrapped to two
     lines while "UNIVERSITY REPS" stayed on one, so the three cards scanned as
     three different shapes. 58px fits both those labels on one line inside the
     ~680px the icon and padding leave. "EDUCATION COUNSELLORS" is too long for
     any size that keeps the others readable, so it stays two DELIBERATE lines
     (marked up as two .lbl divs) rather than being left to wrap by accident. */
  .lbl{font-family:Poppins,sans-serif;font-weight:900;font-size:58px;
       line-height:1.04;color:#100796;letter-spacing:-.01em;white-space:nowrap}
  .sub{font-family:Poppins,sans-serif;font-weight:700;font-size:34px;
       color:#5a5f7a;margin-top:8px;letter-spacing:.01em}
  /* Balances the stack: without it the bottom quarter of the frame is empty,
     which reads as an unfinished slide on a 1080x1920 canvas. Echoes his own
     line earlier in the reel ("one event, one afternoon"). */
  #foot{position:absolute;left:0;right:0;top:79%;text-align:center;
        font-family:Poppins,sans-serif;font-weight:900;font-size:52px;
        color:#FFC500;letter-spacing:.04em;opacity:0;
        text-shadow:0 6px 22px rgba(0,0,0,.5)}
</style>
<div id="bg"></div>
<div class="orb" id="o1"></div>
<div class="orb" id="o2"></div>
<div id="head">WHO'S IN THE ROOM</div>
<div id="rule"></div>
<div class="card" id="c1">
  <div class="ico">&#127891;</div>
  <div><div class="lbl">UNIVERSITY REPS</div>
       <div class="sub">Ask them directly</div></div>
</div>
<div class="card" id="c2">
  <div class="ico">&#128203;</div>
  <div><div class="lbl">MIGRATION AGENTS</div>
       <div class="sub">Free consultation</div></div>
</div>
<div class="card" id="c3">
  <div class="ico">&#128172;</div>
  <div><div class="lbl">EDUCATION</div>
       <div class="lbl">COUNSELLORS</div></div>
</div>
<div id="foot">ALL IN ONE AFTERNOON</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});

  tl.fromTo("#head",{opacity:0,y:26},
    {opacity:1,y:0,duration:.30,ease:"power3.out"},0.10);
  tl.to("#rule",{width:300,duration:.34,ease:"power2.out"},0.24);

  // Orbs drift for the whole cutaway so the background never sits still.
  tl.to("#o1",{x:70,y:-50,duration:4.4,ease:"sine.inOut"},0);
  tl.to("#o2",{x:-60,y:40,duration:4.4,ease:"sine.inOut"},0);

  // One card per role, alternating entry side, each landing on the words that
  // name it. They stack rather than replacing each other.
  [["#c1",0.80,-620],["#c2",2.25,620],["#c3",3.15,-620]].forEach(function(p){
    tl.fromTo(p[0],{opacity:0,x:p[2],rotation:p[2]<0?-3:3},
      {opacity:1,x:0,rotation:0,duration:.42,ease:"back.out(1.5)"},p[1]);
    // a small settle-bounce so the card lands with weight
    tl.to(p[0],{scale:1.03,duration:.10,ease:"sine.out"},p[1]+0.40);
    tl.to(p[0],{scale:1,duration:.14,ease:"sine.inOut"},p[1]+0.50);
  });

  // Footer lands once all three cards are down, so it reads as the summary of
  // the stack rather than a fourth item.
  tl.fromTo("#foot",{opacity:0,y:20},
    {opacity:1,y:0,duration:.26,ease:"power3.out"},3.72);

  // Everything clears before the splice ends (4.45s) so the cut back to
  // Salman is on a clean frame, not mid-animation.
  tl.to(["#c1","#c2","#c3"],{opacity:0,y:-30,duration:.18,ease:"power2.in"},4.20);
  tl.to(["#head","#rule","#foot"],{opacity:0,duration:.16,ease:"power2.in"},4.22);

  window.__timelines["main"]=tl;
})();
</script>
"""

STINGERS = [
    ("broll_1", 4.7, BROLL_1),
]
