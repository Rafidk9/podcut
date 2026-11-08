"""B-roll stingers for the Rahul Dhanda / NSW skills list unit-group reel.

Two cutaways, both over CONNECTING phrases (house rule), both PARALLAX scenes
with VELOCITY ramps (user brief: "velocity edits and parallax motion"):

  nsw_q        seg 2 "What does NSW do?"  -- a rhetorical question that only
               bridges into the answer; 1.08s splice of a 1.14s segment.
               Depth layers: dotted grid (slowest) -> skyline silhouette ->
               giant "NSW" -> marker "?" scribble (fastest). Velocity: expo
               whip IN, slow drift, expo whip OUT to the left into the cut.

  more_examples  seg 12 "And if you will take this example further, for
               example," -- pure filler before the coaches example; 2.95s
               splice (speech ends 2.88 local, "they have published" starts
               3.46). A camera trucks along a row of cards at three depths:
               MARKETING (ticked) -> ENGINEERING (ticked) -> COACHING? which
               lands and scales up. Velocity: fast-slow-fast-slow truck
               (each hop is expo.inOut so it whips between cards and settles).

Seek-safe: every tween is fromTo/explicit or set on a paused timeline.
"""

FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Permanent+Marker'
         '&family=Poppins:wght@600;800;900&display=swap" rel="stylesheet"/>')

SKYLINE = (
    # simple hand-built Sydney silhouette: towers, bridge arch, opera sails
    '<svg viewBox="0 0 1600 420" width="1600" height="420">'
    '<g fill="currentColor">'
    '<rect x="40" y="170" width="70" height="250"/><rect x="120" y="110" width="56" height="310"/>'
    '<rect x="186" y="200" width="80" height="220"/><rect x="276" y="60" width="44" height="360"/>'
    '<rect x="282" y="20" width="8" height="44"/><rect x="330" y="150" width="90" height="270"/>'
    '<rect x="430" y="230" width="70" height="190"/>'
    '<path d="M520 420 L520 300 Q760 90 1000 300 L1000 420 L980 420 L980 310 Q760 130 540 310 L540 420 Z"/>'
    '<rect x="510" y="250" width="34" height="170"/><rect x="976" y="250" width="34" height="170"/>'
    '<rect x="520" y="300" width="480" height="14"/>'
    '<path d="M1060 420 L1130 250 L1180 420 Z"/><path d="M1120 420 L1215 210 L1275 420 Z"/>'
    '<path d="M1200 420 L1300 260 L1350 420 Z"/><path d="M1290 420 L1360 300 L1400 420 Z"/>'
    '<rect x="1040" y="400" width="400" height="20"/>'
    '<rect x="1460" y="190" width="60" height="230"/><rect x="1530" y="250" width="50" height="170"/>'
    '</g></svg>')

NSW_Q = FONTS + """
<style>
  #bg{position:absolute;inset:0;background:radial-gradient(120% 80% at 50% 40%,#1b14b8 0%,#100796 55%,#08034f 100%)}
  #grid{position:absolute;left:-200px;top:-200px;width:1480px;height:2320px;
        background-image:radial-gradient(rgba(255,255,255,.16) 3px,transparent 3.5px);
        background-size:54px 54px}
  #sky{position:absolute;left:-60px;top:1060px;color:#00B3E3;opacity:.55}
  #sky2{position:absolute;left:-300px;top:1210px;color:#0a0570;opacity:1;transform:scale(1.25);transform-origin:0 100%}
  #nsw{position:absolute;left:0;top:520px;width:1080px;text-align:center;
       font:900 400px/1 Poppins,sans-serif;color:#fff;letter-spacing:-14px;
       text-shadow:14px 14px 0 #FFC500}
  #ask{position:absolute;left:0;top:300px;width:1080px;text-align:center;
       font:400 92px/1 'Permanent Marker',cursive;color:#FFC500;transform:rotate(-4deg)}
  #q{position:absolute;left:770px;top:330px;width:300px;height:520px}
  #q path{fill:none;stroke:#E84B37;stroke-width:30;stroke-linecap:round;stroke-linejoin:round}
  #ul{position:absolute;left:150px;top:960px;width:780px;height:80px}
  #ul path{fill:none;stroke:#FFC500;stroke-width:16;stroke-linecap:round}
</style>
<div id="bg"></div><div id="grid"></div>
<div id="sky">""" + SKYLINE + """</div>
<div id="sky2">""" + SKYLINE + """</div>
<div id="ask">so what does</div>
<div id="nsw">NSW</div>
<svg id="ul" viewBox="0 0 780 80"><path d="M10 50 C 140 18, 260 70, 390 40 S 640 22, 770 46"/></svg>
<svg id="q" viewBox="0 0 300 520"><path d="M60 140 C 50 40, 250 20, 250 140 C 250 230, 150 230, 150 330"/>
  <path d="M150 430 L152 446"/></svg>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  var q = document.querySelectorAll('#q path'), ul = document.querySelector('#ul path');
  [].forEach.call(q,function(p){var L=p.getTotalLength();gsap.set(p,{strokeDasharray:L,strokeDashoffset:L});});
  var UL = ul.getTotalLength(); gsap.set(ul,{strokeDasharray:UL,strokeDashoffset:UL});
  // velocity whip IN: every layer enters from the right, nearer = further/faster
  tl.fromTo('#grid',{x:160},{x:0,duration:1.4,ease:'none'},0);
  tl.fromTo('#sky',{x:500},{x:-120,duration:1.4,ease:'expo.out'},0);
  tl.fromTo('#sky2',{x:900},{x:-260,duration:1.4,ease:'expo.out'},0);
  tl.fromTo('#nsw',{x:1300,skewX:-28},{x:0,skewX:0,duration:.42,ease:'expo.out'},0);
  tl.fromTo('#ask',{x:900,opacity:0},{x:0,opacity:1,duration:.36,ease:'expo.out'},.04);
  tl.to(ul,{strokeDashoffset:0,duration:.30,ease:'power2.out'},.30);
  tl.to(q[0],{strokeDashoffset:0,duration:.34,ease:'power1.inOut'},.36);
  tl.to(q[1],{strokeDashoffset:0,duration:.06,ease:'none'},.72);
  // slow parallax drift while held
  tl.to('#nsw',{x:-40,duration:.5,ease:'none'},.42);
  tl.to('#q',{x:-70,y:-12,rotation:-4,duration:.6,ease:'none'},.36);
  // velocity whip OUT (accelerating) into the cut
  tl.to(['#nsw','#ask','#ul','#q'],{x:'-=1400',skewX:22,duration:.30,ease:'expo.in'},.98);
  tl.to(['#sky','#sky2'],{x:'-=600',duration:.30,ease:'expo.in'},.98);
  window.__timelines["main"]=tl;
})();
</script>
"""

# ---------------------------------------------------------------------------
CARD_W, PITCH = 760, 980          # card width, centre-to-centre spacing (px)
CARDS = [("MARKETING", "#00B3E3", "&#128227;", True),
         ("ENGINEERING", "#31EB7C", "&#9881;&#65039;", True),
         ("COACHING", "#FFC500", "&#127951;", False)]


def _cards():
    out = []
    for i, (lbl, col, ico, done) in enumerate(CARDS):
        x = 160 + i * PITCH
        mark = ('<svg class="tick" viewBox="0 0 160 140"><path d="M14 74 L60 120 L148 16"/></svg>'
                if done else '<div class="qq">?</div>')
        out.append(
            f'<div class="card" id="k{i}" style="left:{x}px;border-color:{col}">'
            f'<div class="ico">{ico}</div><div class="lbl" style="color:{col}">{lbl}</div>'
            f'<div class="sub">UNIT GROUP</div>{mark}</div>')
    return "".join(out)


MORE_EXAMPLES = (FONTS + """
<style>
  #bg{position:absolute;inset:0;background:linear-gradient(180deg,#100796 0%,#0a0560 100%)}
  #dots{position:absolute;left:0;top:0;width:4200px;height:1920px;
        background-image:radial-gradient(rgba(255,255,255,.14) 3px,transparent 3.5px);background-size:60px 60px}
  #far{position:absolute;left:0;top:0;width:5200px;height:1920px}
  .orb{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(0,179,227,.30),rgba(0,179,227,0) 70%)}
  #track{position:absolute;left:0;top:640px;width:4000px;height:700px}
  .card{position:absolute;top:0;width:""" + str(CARD_W) + """px;height:640px;border-radius:44px;
        background:#fff;border:14px solid;box-shadow:0 30px 80px rgba(0,0,0,.45);
        display:flex;flex-direction:column;align-items:center;justify-content:center}
  .ico{font-size:170px;line-height:1}
  .lbl{font:900 92px/1 Poppins,sans-serif;margin-top:26px;letter-spacing:-2px;
       -webkit-text-stroke:3px #100796}
  .sub{font:800 40px/1 Poppins,sans-serif;color:#100796;margin-top:18px;letter-spacing:6px}
  .tick{position:absolute;right:-30px;top:-60px;width:200px;height:175px}
  .tick path{fill:none;stroke:#31EB7C;stroke-width:30;stroke-linecap:round;stroke-linejoin:round;
             filter:drop-shadow(4px 6px 0 #100796)}
  .qq{position:absolute;right:-24px;top:-90px;font:400 230px/1 'Permanent Marker',cursive;color:#E84B37;
      text-shadow:5px 7px 0 #100796}
  #head{position:absolute;left:0;top:250px;width:1080px;text-align:center;
        font:400 104px/1 'Permanent Marker',cursive;color:#FFC500;transform:rotate(-3deg)}
  #arrow{position:absolute;left:300px;top:1420px;width:480px;height:160px}
  #arrow path{fill:none;stroke:#fff;stroke-width:18;stroke-linecap:round;stroke-linejoin:round}
  #near{position:absolute;left:0;top:1560px;width:6200px;height:300px}
  .ring{position:absolute;width:120px;height:120px;border-radius:50%;border:12px solid rgba(255,197,0,.55)}
</style>
<div id="bg"></div><div id="dots"></div>
<div id="far"><span class="orb" style="left:120px;top:180px;width:260px;height:260px"></span><span class="orb" style="left:740px;top:700px;width:420px;height:420px"></span><span class="orb" style="left:1360px;top:1220px;width:260px;height:260px"></span><span class="orb" style="left:1980px;top:180px;width:420px;height:420px"></span><span class="orb" style="left:2600px;top:700px;width:260px;height:260px"></span><span class="orb" style="left:3220px;top:1220px;width:420px;height:420px"></span><span class="orb" style="left:3840px;top:180px;width:260px;height:260px"></span><span class="orb" style="left:4460px;top:700px;width:420px;height:420px"></span></div>
<div id="track">__CARDS__</div>
<div id="head">another example&#8230;</div>
<svg id="arrow" viewBox="0 0 480 160"><path d="M20 90 C 140 30, 300 140, 440 70"/><path d="M380 40 L444 70 L392 124"/></svg>
<div id="near"><span class="ring" style="left:60px;top:0px"></span><span class="ring" style="left:440px;top:120px"></span><span class="ring" style="left:820px;top:0px"></span><span class="ring" style="left:1200px;top:120px"></span><span class="ring" style="left:1580px;top:0px"></span><span class="ring" style="left:1960px;top:120px"></span><span class="ring" style="left:2340px;top:0px"></span><span class="ring" style="left:2720px;top:120px"></span><span class="ring" style="left:3100px;top:0px"></span><span class="ring" style="left:3480px;top:120px"></span><span class="ring" style="left:3860px;top:0px"></span><span class="ring" style="left:4240px;top:120px"></span><span class="ring" style="left:4620px;top:0px"></span><span class="ring" style="left:5000px;top:120px"></span><span class="ring" style="left:5380px;top:0px"></span><span class="ring" style="left:5760px;top:120px"></span></div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  var P = """ + str(PITCH) + """;
  var ticks = document.querySelectorAll('.tick path');
  [].forEach.call(ticks,function(p){var L=p.getTotalLength();gsap.set(p,{strokeDasharray:L,strokeDashoffset:L});});
  var ar = document.querySelectorAll('#arrow path');
  [].forEach.call(ar,function(p){var L=p.getTotalLength();gsap.set(p,{strokeDasharray:L,strokeDashoffset:L});});
  // camera truck, three depths: track 1.0x, far text 0.35x, dots 0.15x, near text 1.6x.
  // fast-slow-fast-slow: each hop is expo.inOut -> whips between cards, settles on them.
  var stops=[[0,0],[0.05,0],[0.85,-P],[1.65,-2*P]];       // [time, trackX]
  gsap.set('#track',{x:-P*0.35}); gsap.set('#far',{x:0}); gsap.set('#dots',{x:0}); gsap.set('#near',{x:0});
  tl.fromTo('#track',{x:-P*0.35-900},{x:0,duration:.40,ease:'expo.out'},0);
  tl.fromTo('#near',{x:-1440},{x:0,duration:.40,ease:'expo.out'},0);
  for (var i=1;i<stops.length-1;i++){
    var t0=stops[i][0], x0=stops[i][1], x1=stops[i+1][1], d=stops[i+1][0]-t0;
    tl.fromTo('#track',{x:x0},{x:x1,duration:d,ease:'expo.inOut'},t0+0.42);
    tl.fromTo('#far',{x:x0*0.35},{x:x1*0.35,duration:d,ease:'expo.inOut'},t0+0.42);
    tl.fromTo('#dots',{x:x0*0.15},{x:x1*0.15,duration:d,ease:'expo.inOut'},t0+0.42);
    tl.fromTo('#near',{x:x0*1.6},{x:x1*1.6,duration:d,ease:'expo.inOut'},t0+0.42);
  }
  // motion-blur feel on the whips: skew the cards with velocity
  tl.fromTo('.card',{skewX:0},{skewX:-10,duration:.35,ease:'power2.in',yoyo:true,repeat:1},0.55);
  tl.fromTo('.card',{skewX:0},{skewX:-10,duration:.35,ease:'power2.in',yoyo:true,repeat:1},1.35);
  tl.fromTo('#head',{opacity:0,y:-60},{opacity:1,y:0,duration:.3,ease:'back.out(2)'},0.10);
  tl.to(ticks[0],{strokeDashoffset:0,duration:.22,ease:'power2.out'},0.38);
  tl.to(ticks[1],{strokeDashoffset:0,duration:.22,ease:'power2.out'},1.26);
  // land on COACHING: scale punch, ? wiggles, arrow draws in
  tl.fromTo('#k2',{scale:1},{scale:1.12,duration:.28,ease:'back.out(3)'},2.12);
  tl.fromTo('#k2 .qq',{rotation:-18,scale:.2},{rotation:8,scale:1,duration:.32,ease:'back.out(3)'},2.14);
  tl.to(ar[0],{strokeDashoffset:0,duration:.28,ease:'power2.out'},2.20);
  tl.to(ar[1],{strokeDashoffset:0,duration:.12,ease:'power2.out'},2.46);
  tl.fromTo('#k2',{rotation:0},{rotation:-2.5,duration:.6,ease:'sine.inOut'},2.40);
  window.__timelines["main"]=tl;
})();
</script>
""").replace("__CARDS__", _cards())

STINGERS = [
    ("nsw_q", 1.4, NSW_Q),
    ("more_examples", 3.2, MORE_EXAMPLES),
]
