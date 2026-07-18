"""Reel-specific B-roll (2 DISTINCT, topical stingers), placed by the user's
explicit request right after P1 and right after P3 -- both boundaries otherwise
carry load-bearing content, but captions + audio stay continuous underneath
the cutaway (build_captions.py overlays captions on top of base_broll.mp4
regardless of what's playing under them), so nothing she says is lost, only
her on-camera visual is swapped out for ~1.3s.

broll_1 (after P1, before "Many workers believe..."): previews the SPECIFIC
myth about to be stated -- the 12-month trading-history rule -- so the
cutaway sets up the very next sentence rather than being a generic beat.

broll_2 (after P3, before "What matters is..."): bridges the proof case
(10-month-old sponsoring business) into the criteria checklist that follows,
previewing the 3 things that actually matter."""

BROLL_1 = """
<style id="s1">
  #bg1{position:absolute;inset:0;background:linear-gradient(160deg,#100796,#0a0664 65%)}
  #cal{position:absolute;left:50%;top:44%;transform:translate(-50%,-50%) scale(0.6);
       width:420px;background:#fff;border-radius:22px;box-shadow:0 24px 60px rgba(0,0,0,.5);
       opacity:0;overflow:hidden}
  #cal .hd{background:#E84B37;color:#fff;font-family:Poppins,sans-serif;font-weight:800;
       font-size:30px;letter-spacing:.04em;text-align:center;padding:18px 0}
  #cal .bd{padding:34px 0;text-align:center}
  #cal .num{font-family:Poppins,sans-serif;font-weight:900;font-size:120px;color:#100796;line-height:1}
  #cal .lbl{font-family:Poppins,sans-serif;font-weight:700;font-size:28px;color:#555;margin-top:6px;
       letter-spacing:.03em}
  #xmark{position:absolute;left:50%;top:44%;transform:translate(-50%,-50%) scale(0);
       width:180px;height:180px;border-radius:50%;background:rgba(232,75,55,.92);
       display:flex;align-items:center;justify-content:center;box-shadow:0 10px 30px rgba(0,0,0,.4)}
  #xmark svg{width:96px;height:96px}
  .h1{position:absolute;left:0;right:0;top:20%;text-align:center;font-family:Poppins,sans-serif;
      font-weight:900;font-size:56px;color:#fff;opacity:0;letter-spacing:.01em}
  .h2{position:absolute;left:0;right:0;bottom:16%;text-align:center;font-family:Poppins,sans-serif;
      font-weight:700;font-size:36px;color:#FFC500;opacity:0}
</style>
<div id="bg1"></div>
<div class="h1" id="myth1">COMMON MYTH:</div>
<div id="cal">
  <div class="hd">TRADING HISTORY</div>
  <div class="bd"><div class="num">12+</div><div class="lbl">MONTHS REQUIRED?</div></div>
</div>
<div id="xmark"><svg viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="#fff"
     stroke-width="3.4" stroke-linecap="round"/></svg></div>
<div class="h2" id="myth2">NOT ACTUALLY TRUE</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.fromTo("#myth1",{opacity:0,y:-16},{opacity:1,y:0,duration:.24,ease:"back.out(1.8)"},0);
  tl.fromTo("#cal",{opacity:0,scale:0.6},{opacity:1,scale:1,duration:.32,ease:"back.out(2)"},0.14);
  tl.fromTo("#xmark",{scale:0,rotation:-30},{scale:1,rotation:0,duration:.26,ease:"back.out(2.6)"},0.52);
  tl.fromTo("#myth2",{opacity:0,y:16},{opacity:1,y:0,duration:.26,ease:"back.out(1.8)"},0.66);
  tl.to(["#myth1","#myth2","#cal","#xmark"],{opacity:0,duration:.18,ease:"power2.in"},1.12);
  window.__timelines["main"]=tl;
})();
</script>
"""

BROLL_2 = """
<style id="s2">
  #bg2{position:absolute;inset:0;background:linear-gradient(200deg,#0a0664,#100796 60%)}
  .q{position:absolute;left:0;right:0;top:18%;text-align:center;font-family:Poppins,sans-serif;
     font-weight:900;font-size:58px;color:#fff;opacity:0}
  #list{position:absolute;left:50%;top:38%;transform:translateX(-50%);width:760px}
  .item{display:flex;align-items:center;gap:22px;background:rgba(255,255,255,.08);
        border-radius:16px;padding:20px 30px;margin-bottom:22px;opacity:0;transform:translateX(-40px)}
  .item .tick{flex:none;width:56px;height:56px;border-radius:50%;background:#31EB7C;
        display:flex;align-items:center;justify-content:center;transform:scale(0)}
  .item .tick svg{width:30px;height:30px}
  .item .txt{font-family:Poppins,sans-serif;font-weight:800;font-size:38px;color:#fff;letter-spacing:.01em}
</style>
<div id="bg2"></div>
<div class="q" id="qb">WHAT ACTUALLY MATTERS:</div>
<div id="list">
  <div class="item" id="i1"><div class="tick"><svg viewBox="0 0 24 24" fill="none"><path d="M4 12l6 6L20 6"
       stroke="#0A2E1A" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
       <div class="txt">LEGAL BUSINESS</div></div>
  <div class="item" id="i2"><div class="tick"><svg viewBox="0 0 24 24" fill="none"><path d="M4 12l6 6L20 6"
       stroke="#0A2E1A" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
       <div class="txt">GENUINE JOB</div></div>
  <div class="item" id="i3"><div class="tick"><svg viewBox="0 0 24 24" fill="none"><path d="M4 12l6 6L20 6"
       stroke="#0A2E1A" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
       <div class="txt">MEETS TSMIT</div></div>
</div>
<script>
(function(){
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({paused:true});
  tl.fromTo("#qb",{opacity:0,y:-16},{opacity:1,y:0,duration:.24,ease:"back.out(1.8)"},0);
  ["#i1","#i2","#i3"].forEach(function(sel,i){
    var t = 0.2 + i*0.24;
    tl.to(sel,{opacity:1,x:0,duration:.22,ease:"power2.out"},t);
    tl.fromTo(sel+" .tick",{scale:0},{scale:1,duration:.2,ease:"back.out(2.6)"},t+0.08);
  });
  tl.to(["#qb","#i1","#i2","#i3"],{opacity:0,duration:.18,ease:"power2.in"},1.18);
  window.__timelines["main"]=tl;
})();
</script>
"""

STINGERS = [("broll_1", 1.3, BROLL_1), ("broll_2", 1.3, BROLL_2)]
