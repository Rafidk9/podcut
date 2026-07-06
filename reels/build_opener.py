"""Cold-open map zoom (~2.3s): dotted world map -> dive to Australia ->
Sydney pin -> street-level Lakemba pin drop + hook pill. Brand navy/gold/red,
same HyperFrames design language as the B-roll stingers.

Renders WORK/opener.mp4 (1080x1920/30, bt709-tagged, silent stereo track) which
build_composite.py prepends ahead of the captioned content when present.
Delete WORK/opener.mp4 to ship without the cold open."""
import os, json, shutil, subprocess

from reel_paths import WORK, hyperframes_cli  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"

DUR = 2.3

# 60x28 equirectangular landmass grid ('#'=land, 'a'=Australia, drawn as dots).
# Stylized on purpose -- it reads as "world map" for ~0.8s of fast zoom.
WORLD = [
    "............................................................",
    "..####..............#####...........########################",
    "...#######..........####...####....########################.",
    "....########.........##...######..#########################.",
    "....#########.............#####...########################..",
    ".....#######...............###....######################....",
    "......######................##.....#######..##########......",
    ".......####.................###....######....#######........",
    "........###................#####...#####......#####.........",
    "........####..............########..####.......###..........",
    ".........###..............#########..##........####.........",
    "..........##...............########............#####........",
    "..........###..............#######.............######.......",
    "...........####............#######.............#####........",
    "............######.........######...............###.........",
    "............#######.........#####................##..........",
    "............########.........####................#...........",
    ".............#######..........###............................",
    "..............######...........#...............aaaa..........",
    "..............#####............................aaaaaaa.......",
    "...............####...........................aaaaaaaa.......",
    "...............###............................aaaaaaaa......",
    "................##.............................aaaaaa........",
    "................##...............................a...........",
    ".................#.........................................#.",
    "...........................................................#.",
    "............................................................",
    "............................................................",
]

_HTML = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1080px;height:1920px;overflow:hidden;background:#0A0533}
  .stage{position:absolute;inset:0}
  /* vignette so the dive feels like depth, not a flat scale */
  #vig{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 42%,transparent 55%,rgba(0,0,0,.55) 100%);z-index:9}

  /* stage 1: dotted world */
  #world{transform-origin:__AUX__px __AUY__px}
  #world .d{position:absolute;width:9px;height:9px;border-radius:50%;background:#8f8ad6}
  #world .d.au{background:#FFC500;box-shadow:0 0 14px #FFC500}
  #route{position:absolute;left:0;top:0;overflow:visible}

  /* stage 2: Australia silhouette */
  #aus{opacity:0;transform-origin:__SYDX__px __SYDY__px}
  #aus svg{position:absolute;left:190px;top:660px;filter:drop-shadow(0 0 40px rgba(0,179,227,.35))}
  .pin{position:absolute;opacity:0}
  .pin .dot{width:26px;height:26px;border-radius:50%;background:#E84B37;border:5px solid #fff;box-shadow:0 6px 18px rgba(0,0,0,.5)}
  .pin .lbl{position:absolute;left:38px;top:-8px;background:#100796;color:#fff;font-family:"Poppins",sans-serif;
     font-weight:800;font-size:40px;padding:8px 24px;border-radius:999px;white-space:nowrap;
     box-shadow:0 8px 22px rgba(0,0,0,.45)}

  /* stage 3: street level */
  #street{opacity:0;transform-origin:540px 900px}
  #street svg{position:absolute;left:0;top:0}
  #bigpin{position:absolute;left:540px;top:860px;opacity:0}
  #bigpin .head{position:absolute;left:-42px;top:-104px;width:84px;height:84px;border-radius:50% 50% 50% 0;
     transform:rotate(-45deg);background:#E84B37;border:8px solid #fff;box-shadow:0 14px 30px rgba(0,0,0,.5)}
  #bigpin .head::after{content:"";position:absolute;left:24px;top:24px;width:20px;height:20px;border-radius:50%;background:#fff}
  #ring1,#ring2{position:absolute;left:540px;top:880px;width:40px;height:40px;margin:-20px;border-radius:50%;
     border:6px solid #FFC500;opacity:0}
  #lakemba{position:absolute;left:50%;top:1010px;transform:translateX(-50%);opacity:0;
     background:#100796;border-left:14px solid #FFC500;color:#fff;font-family:"Poppins",sans-serif;
     font-weight:900;font-size:76px;letter-spacing:.04em;padding:18px 46px;border-radius:16px;
     box-shadow:0 16px 40px rgba(0,0,0,.5)}
  #hook{position:absolute;left:50%;top:1420px;transform:translateX(-50%);opacity:0;
     background:#E84B37;color:#fff;font-family:"Poppins",sans-serif;font-weight:800;font-size:42px;
     letter-spacing:.05em;padding:24px 52px;border-radius:999px;box-shadow:0 14px 34px rgba(0,0,0,.4);white-space:nowrap}
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="__DUR__" data-fps="30" data-width="1080" data-height="1920">
  <div class="stage" id="world">__DOTS__
    <svg id="route" width="1080" height="1920">
      <path id="arc" d="M 140 520 Q 620 300 __AUX__ __AUY__" fill="none" stroke="#E84B37"
            stroke-width="7" stroke-dasharray="14 14" stroke-linecap="round"/>
      <circle id="plane" r="12" fill="#FFC500"/>
    </svg>
  </div>
  <div class="stage" id="aus">
    <svg width="700" height="600" viewBox="0 0 100 86">
      <path d="M 68 2 L 72 10 L 78 22 L 80 32 L 76 44 L 70 52 L 60 58 L 48 54 L 36 56
               L 20 58 L 12 50 L 8 38 L 10 24 L 16 14 L 26 8 L 34 12 L 40 6 L 48 4
               L 52 14 L 58 12 L 62 2 Z" fill="#1A10C0" stroke="#00B3E3" stroke-width="1.6"/>
      <ellipse cx="66" cy="70" rx="5" ry="4" fill="#1A10C0" stroke="#00B3E3" stroke-width="1.4"/>
    </svg>
    <div class="pin" id="sydpin" style="left:__SYDX__px;top:__SYDY__px">
      <div class="dot"></div><div class="lbl">SYDNEY</div>
    </div>
  </div>
  <div class="stage" id="street">
    <svg width="1080" height="1920">
      <rect width="1080" height="1920" fill="#0D0840"/>
      <g stroke="#2A2380" stroke-width="14" fill="none">
        <path d="M -50 700 L 1130 640"/><path d="M -50 980 L 1130 1040"/>
        <path d="M 300 -50 L 260 1970"/><path d="M 760 -50 L 830 1970"/>
        <path d="M -50 1330 L 1130 1260"/>
      </g>
      <g stroke="#3A33A0" stroke-width="7" fill="none">
        <path d="M -50 820 L 1130 790"/><path d="M 540 -50 L 520 1970"/>
        <path d="M 60 -50 L 100 1970"/><path d="M 980 -50 L 1010 1970"/>
        <path d="M -50 1150 L 1130 1160"/><path d="M -50 480 L 1130 430"/>
      </g>
      <path d="M -50 560 L 1130 520" stroke="#FFC500" stroke-width="9"
            stroke-dasharray="34 22" fill="none" opacity="0.75"/>
      <g fill="#153A2E"><ellipse cx="180" cy="1500" rx="150" ry="100"/>
        <ellipse cx="920" cy="330" rx="130" ry="90"/></g>
    </svg>
    <div id="ring1"></div><div id="ring2"></div>
    <div id="bigpin"><div class="head"></div></div>
    <div id="lakemba">LAKEMBA</div>
    <div id="hook">FREE MIGRATION SEMINAR</div>
  </div>
  <div id="vig"></div>
</div>
<script>
(function(){
  window.__timelines=window.__timelines||{};
  var tl=gsap.timeline({paused:true});
  var world=document.getElementById("world"), aus=document.getElementById("aus"),
      street=document.getElementById("street"), arc=document.getElementById("arc"),
      plane=document.getElementById("plane");
  var L=arc.getTotalLength();
  arc.style.strokeDasharray=L; arc.style.strokeDashoffset=L;

  // stage 1 (0 - 0.85): route draws while the world dives toward Australia
  tl.set(world,{scale:1},0);
  tl.to(arc,{strokeDashoffset:0,duration:0.55,ease:"power1.in"},0.06);
  tl.to({t:0},{t:1,duration:0.55,ease:"power1.in",onUpdate:function(){
      var p=arc.getPointAtLength(L*this.targets()[0].t);
      plane.setAttribute("cx",p.x); plane.setAttribute("cy",p.y);
  }},0.06);
  tl.to(world,{scale:6,duration:0.85,ease:"power3.in"},0);
  tl.to(world,{opacity:0,duration:0.2,ease:"power1.in"},0.66);

  // stage 2 (0.6 - 1.5): Australia silhouette carries the zoom into Sydney
  tl.fromTo(aus,{opacity:0,scale:0.55},{opacity:1,scale:1,duration:0.28,ease:"power2.out"},0.62);
  tl.to(aus,{scale:3.4,duration:0.62,ease:"power3.in"},0.88);
  tl.fromTo("#sydpin",{opacity:0,y:-26},{opacity:1,y:0,duration:0.2,ease:"back.out(2.5)"},0.95);
  tl.to(aus,{opacity:0,duration:0.18,ease:"power1.in"},1.34);

  // stage 3 (1.3 - end): street level, pin drop, pulse, labels
  tl.fromTo(street,{opacity:0,scale:1.16},{opacity:1,scale:1.28,duration:0.9,ease:"power1.out"},1.32);
  tl.fromTo("#bigpin",{opacity:1,y:-560},{y:0,duration:0.3,ease:"power2.in"},1.42);
  tl.to("#bigpin",{y:-46,duration:0.12,ease:"power1.out"},1.72);
  tl.to("#bigpin",{y:0,duration:0.12,ease:"power1.in"},1.84);
  [["#ring1",1.72],["#ring2",1.9]].forEach(function(r){
    tl.fromTo(r[0],{opacity:0.9,scale:0.3},{opacity:0,scale:7,duration:0.55,ease:"power1.out"},r[1]);
  });
  tl.fromTo("#lakemba",{opacity:0,scale:0.7},{opacity:1,scale:1,duration:0.26,ease:"back.out(2.4)"},1.78);
  tl.fromTo("#hook",{opacity:0,y:36},{opacity:1,y:0,duration:0.28,ease:"back.out(2)"},1.98);

  tl.seek(0);
  window.__timelines["main"]=tl;
})();
</script></body></html>
"""


def build_html():
    cell = 17
    mw, mh = 60 * cell, 28 * cell
    ox, oy = (1080 - mw) // 2, 420        # map block sits in the upper-middle
    dots, aux, auy, aun = [], 0.0, 0.0, 0
    for r, row in enumerate(WORLD):
        for c, ch in enumerate(row):
            if ch in "#a":
                x, y = ox + c * cell, oy + r * cell
                dots.append(f'<i class="d{" au" if ch == "a" else ""}" '
                            f'style="left:{x}px;top:{y}px"></i>')
                if ch == "a":
                    aux += x; auy += y; aun += 1
    aux, auy = aux / aun + 4, auy / aun + 4          # dot centres
    # Sydney on the Australia svg: viewBox pt (75,45) -> px within #aus
    sydx = 190 + 75 / 100 * 700
    sydy = 660 + 45 / 86 * 600
    return (_HTML.replace("__DOTS__", "".join(dots))
            .replace("__AUX__", f"{aux:.0f}").replace("__AUY__", f"{auy:.0f}")
            .replace("__SYDX__", f"{sydx:.0f}").replace("__SYDY__", f"{sydy:.0f}")
            .replace("__DUR__", f"{DUR:.3f}"))


def main():
    proj = os.path.join(WORK, "opener_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(build_html())
    json.dump({"id": "opener", "name": "map zoom cold open"},
              open(os.path.join(proj, "meta.json"), "w"))

    raw = os.path.join(WORK, "opener_raw.mp4")
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(raw),
                    "-f", "30", "-q", "standard", "--quiet"],
                   cwd=proj, check=True, env=env)

    # bt709 tags + silent stereo bed so the concat demuxer sees uniform streams
    out = os.path.join(WORK, "opener.mp4")
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", raw,
                    "-f", "lavfi", "-t", f"{DUR:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                    "-map", "0:v", "-map", "1:a", "-shortest",
                    "-vf", "setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-colorspace", "bt709", "-color_range", "tv",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2",
                    "-video_track_timescale", "90000", out], check=True)
    print("opener ready:", out)


if __name__ == "__main__":
    main()
