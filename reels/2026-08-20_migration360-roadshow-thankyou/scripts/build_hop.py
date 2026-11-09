"""Reusable "plane hop" transition generator for the Migration 360 Roadshow
thank-you reel -- bridges two already-built city blocks
(work/segment_<city>.mp4) with a short (~1.5-2s) full-screen 1080x1920 clip:
a dotted arc line draws from a departure point to an arrival point in the
ARRIVING city's stamp colour, a small plane glyph banks along that arc, the
abstract background line-motif (same curved-line language as
build_city_block.py's #bg decoration) parallaxes gently opposite the plane's
motion, and a soft radar-ping starts blooming at the arrival point as the
clip cuts -- deliberately BEFORE the ping (or the plane) fully resolves, so
cutting straight into the next city block's own stamp-landing animation
reads as one continuous arrival beat, not two stacked ones.

Public interface:

    build_hop(from_label, to_label, color, output_path, fps=30,
              quality="standard") -> str   # absolute path to the rendered mp4

from_label/to_label are the departure/arrival city names (used only for the
composition id / log line -- this hop is deliberately abstract/minimal, no
on-screen text, so it never collides visually with the arrival stamp's own
city-name text that opens the next block). color is the ARRIVING city's
stamp colour (hex string) -- the arc, plane and arrival ping all use it,
matching "arc line ... in the arriving city's stamp colour" in the brief.

Geometry (fixed, abstract -- NOT a literal map): a quadratic-bezier arc from
a lower-left departure point (280,1480) through a control point (769,1124)
to an upper-right arrival point (800,520) on the 1080x1920 canvas. Bows
right of the straight departure->arrival line, reading as a graceful
great-circle-style sweep without claiming geographic accuracy.

Timing (total ~1.70s at the given fps):
  0.00-0.25  scene fade-in (background, parallax map layers, departure dot)
  0.12-1.30  flight window: arc mask-reveals (dash-offset draw, see below),
             plane travels 0%-96.5% of the path length with autoRotate
             banking, background parallax layers drift opposite the plane's
             net travel direction (roughly 20-30px, subtle)
  1.28-1.70  arrival ping: 3 staggered radar rings bloom+fade at the arrival
             point, overlapping the tail of the flight window as
             anticipation -- clip ends mid-bloom (never fully resolves,
             and the plane itself never fully reaches 100% of the path --
             see module docstring for why).

Dotted-arc-draws implementation: a real dashed stroke (small dasharray, so
it reads as a dotted line at rest, matching the "dotted arc" ask) can't be
progressively revealed just by animating its OWN stroke-dashoffset -- a
short repeating dash pattern just slides in place under a dashoffset tween,
it doesn't grow. Instead this uses the standard SVG "growing mask" trick:
an invisible wide-stroked maskPath (same "d", stroke-width ~70) gets the
classic single-dash-equal-to-path-length reveal (dasharray = dashoffset =
getTotalLength(), then dashoffset animated to 0), and that mask is applied
(via mask="url(#drawMask)") to the actual visible dotted-styled arc path
underneath -- so the visible dotted line is revealed length-by-length as
the invisible mask stroke grows. getTotalLength() is a deterministic,
synchronous read of fixed path geometry (not Date.now/random), so this
stays seek-safe.
"""
import json
import os
import shutil
import subprocess
import sys

_THIS = os.path.abspath(__file__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(_THIS))))  # reels/
from reel_paths import WORK, hyperframes_cli  # noqa: E402

# --- fixed abstract flight geometry (see module docstring) ---
DEP = (280, 1480)
CTRL = (769, 1124)
ARR = (800, 520)
ARC_D = "M {0} {1} Q {2} {3} {4} {5}".format(DEP[0], DEP[1], CTRL[0], CTRL[1], ARR[0], ARR[1])

# Hand-built simplified airplane silhouette (24x24 viewBox), nose pointing
# along local +x (angle 0 deg -- the same reference GSAP's autoRotate uses
# for the direction of travel), so autoRotate:0 needs no extra baseline
# offset (verified against the rendered stills: the nose leads the dashed
# line at every point along the arc, not trailing it).
#
# Five filled subpaths, same fill colour throughout:
#   1. fuselage -- a slim hexagon with a distinct nose cone (x=22, right)
#      and tail cone (x=3, left), staying visible as a spine running the
#      full nose-to-tail length rather than disappearing under the wings.
#   2/3. main wings -- each a 4-point trapezoid (root-leading, tip-leading,
#      tip-trailing, root-trailing), NOT a triangle tapering to a point:
#      real wingtips have width/chord, and keeping that width is what
#      stops the shape reading as an arrow/dagger blade. Root sits forward
#      of the fuselage's midpoint (near the nose) and each wingtip trails
#      well aft of its own root -- a genuine backward sweep, not a
#      perpendicular spar. Full span (y 2-22) is far wider than the
#      fuselage (width ~2.5 at most), matching "wings noticeably wider
#      than the fuselage."
#   4/5. small top+bottom tail planes near the tail, clearly separated
#      from the main wings -- gives the silhouette a "small tail" and
#      breaks the old glyph's dead-centre symmetry, which is what made it
#      collapse into a plain "X"/cross once the glow filter blurred it.
PLANE_D = ("M22 12 L17 10.6 L6 10.9 L3 12 L6 13.1 L17 13.4 Z "
           "M15 11.0 L5 2.0 L7.5 4.0 L11.5 12.3 Z "
           "M15 13.0 L5 22.0 L7.5 20.0 L11.5 11.7 Z "
           "M6.5 11.0 L3 7.0 L5 11.6 Z "
           "M6.5 13.0 L3 17.0 L5 12.4 Z")

# --- timing (seconds) ---
FLIGHT_START = 0.12
FLIGHT_DUR = 1.43          # flight window ends at 1.55 -- deliberately runs
                           # almost to the clip's end so the plane is still
                           # (just barely) approaching when the ping starts,
                           # instead of sitting static at the arrival point
                           # for a stretch before the ping -- see docstring.
PING_START = 1.40          # overlaps the tail of the flight window: the
                           # ping starts blooming while the plane is still
                           # completing its final approach.
TOTAL_DUR = 1.70           # clip ends mid-bloom -- see module docstring

# Quiet backdrop line-motif: two simple, single-sweep open curves (no closed
# loops, no self-crossings) parked in the top and bottom margins of the
# canvas -- well clear of the arc's travel corridor (arc spans roughly
# x:280-800, y:520-1480; see DEP/CTRL/ARR below) so the lines never cross
# through the flight path itself. Plotted directly in full 1080x1920 canvas
# space (not a small scaled-up viewBox) so their gentle sweep is easy to
# reason about and doesn't compound into visual clutter at scale.
CURVE_FAR_D = ("M -60 260 C 220 120 480 340 760 200 "
               "C 900 130 1000 180 1140 140")
CURVE_NEAR_D = ("M -60 1650 C 260 1820 520 1600 800 1760 "
                "C 950 1840 1020 1780 1140 1820")

HTML_TEMPLATE = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/MotionPathPlugin.min.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:1080px;height:1920px;overflow:hidden;background:#0A0730}}
  .stage{{position:absolute;inset:0}}
  #bg{{position:absolute;inset:0;opacity:0;
      background:
        radial-gradient(ellipse 900px 700px at 50% 8%, rgba(255,255,255,.08), transparent 60%),
        linear-gradient(160deg,#140B5C 0%,#0A0730 46%,#050318 100%);}}
  #mapFar,#mapNear{{position:absolute;inset:0;opacity:0}}
  .depDot{{position:absolute;width:22px;height:22px;border-radius:50%;
      transform:translate(-50%,-50%);opacity:0;
      box-shadow:0 0 16px rgba(255,255,255,.35)}}
  .depDot .core{{position:absolute;inset:6px;border-radius:50%;background:rgba(255,255,255,.85)}}
  .depDot .ring{{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(255,255,255,.5)}}
  #plane{{position:absolute;left:0;top:0;width:0;height:0}}
  #planeArt{{position:absolute;left:-30px;top:-30px;width:60px;height:60px}}
  #pingWrap{{position:absolute;left:{arr_x}px;top:{arr_y}px}}
  .ping{{position:absolute;left:0;top:0;width:70px;height:70px;
      transform:translate(-50%,-50%) scale(.2);border-radius:50%;
      border:4px solid {color};opacity:0;box-shadow:0 0 18px {color}66}}
  #pingCore{{position:absolute;left:0;top:0;width:24px;height:24px;
      transform:translate(-50%,-50%) scale(.6);border-radius:50%;
      background:{color};opacity:0;box-shadow:0 0 24px {color}}}
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="{total_dur:.3f}" data-fps="{fps}" data-width="1080" data-height="1920">

  <div class="stage" id="bg"></div>

  <div id="mapFar">
    <svg width="1080" height="1920" viewBox="0 0 1080 1920">
      <path d="{curve_far_d}" fill="none" stroke="{color}" stroke-width="3"
            stroke-linecap="round" opacity=".14"/>
    </svg>
  </div>
  <div id="mapNear">
    <svg width="1080" height="1920" viewBox="0 0 1080 1920">
      <path d="{curve_near_d}" fill="none" stroke="{color}" stroke-width="3.5"
            stroke-linecap="round" opacity=".18"/>
    </svg>
  </div>

  <div class="depDot" style="left:{dep_x}px;top:{dep_y}px">
    <div class="ring"></div><div class="core"></div>
  </div>

  <svg id="arcSvg" width="1080" height="1920" viewBox="0 0 1080 1920" style="position:absolute;inset:0">
    <defs>
      <mask id="drawMask">
        <path id="maskPath" d="{arc_d}" stroke="#fff" stroke-width="70"
              stroke-linecap="round" fill="none"/>
      </mask>
    </defs>
    <path id="arcPath" d="{arc_d}" stroke="{color}" stroke-width="6"
          stroke-dasharray="10 16" stroke-linecap="round" fill="none"
          mask="url(#drawMask)" opacity="0.95"
          style="filter:drop-shadow(0 0 6px {color}99)"/>
  </svg>

  <div id="plane">
    <svg id="planeArt" viewBox="0 0 24 24" style="
         filter:drop-shadow(0 0 10px {color}) drop-shadow(0 6px 14px rgba(0,0,0,.55))">
      <path d="{plane_d}" fill="{color}"/>
    </svg>
  </div>

  <div id="pingWrap">
    <div id="pingCore"></div>
    <div class="ping" id="ping0"></div>
    <div class="ping" id="ping1"></div>
    <div class="ping" id="ping2"></div>
  </div>

</div>
<script>
(function(){{
  window.__timelines = window.__timelines || {{}};
  gsap.registerPlugin(MotionPathPlugin);

  var maskPath = document.getElementById('maskPath');
  var len = maskPath.getTotalLength();
  maskPath.style.strokeDasharray = len;
  maskPath.style.strokeDashoffset = len;

  var tl = gsap.timeline({{paused:true}});

  tl.to("#bg", {{opacity:1, duration:0.28}}, 0);
  tl.to("#mapFar, #mapNear", {{opacity:1, duration:0.28, stagger:0.03}}, 0.02);
  tl.to(".depDot", {{opacity:1, duration:0.22}}, 0.05);

  // parallax drift across the flight window -- opposite the plane's net
  // (lower-left -> upper-right) travel, kept subtle/abstract.
  tl.fromTo("#mapFar", {{x:0, y:0}}, {{x:-22, y:14, duration:{flight_dur:.3f}, ease:"none"}}, {flight_start:.3f});
  tl.fromTo("#mapNear", {{x:0, y:0}}, {{x:30, y:-18, duration:{flight_dur:.3f}, ease:"none"}}, {flight_start:.3f});

  // dotted arc "draws" via the mask-reveal trick (see module docstring)
  tl.to(maskPath, {{strokeDashoffset:0, duration:{flight_dur:.3f}, ease:"none"}}, {flight_start:.3f});

  // plane travels most (not all) of the arc, banking into the curve
  tl.to("#plane", {{
    motionPath: {{path:"#arcPath", align:"#arcPath", alignOrigin:[0.5,0.5], autoRotate:0, start:0, end:0.965}},
    duration:{flight_dur:.3f}, ease:"power1.inOut"
  }}, {flight_start:.3f});

  // arrival: soft radar-ping bloom, deliberately left unresolved at clip end
  tl.fromTo("#pingCore", {{opacity:0, scale:0.6}}, {{opacity:1, scale:1.15, duration:0.22, ease:"power2.out"}}, {ping_start:.3f});
  // each ring: invisible (0 opacity, matching its resting CSS) until its own
  // start, then a quick bright flash, then bloom+fade -- NOT a plain
  // fromTo(visible-state, ...), which would make GSAP hold that "from"
  // value (a small solid ring) for the ENTIRE clip before this tween's
  // start position, wrongly showing a static ring at the arrival point
  // from frame 0.
  tl.to("#ping0", {{keyframes:[
      {{opacity:0, scale:0.2, duration:0}},
      {{opacity:1, scale:0.45, duration:0.08, ease:"power2.out"}},
      {{opacity:0, scale:2.3, duration:0.52, ease:"power1.out"}}]}}, {ping_start:.3f});
  tl.to("#ping1", {{keyframes:[
      {{opacity:0, scale:0.2, duration:0}},
      {{opacity:0.9, scale:0.45, duration:0.08, ease:"power2.out"}},
      {{opacity:0, scale:2.3, duration:0.52, ease:"power1.out"}}]}}, {ping1_start:.3f});
  tl.to("#ping2", {{keyframes:[
      {{opacity:0, scale:0.2, duration:0}},
      {{opacity:0.8, scale:0.45, duration:0.08, ease:"power2.out"}},
      {{opacity:0, scale:2.3, duration:0.52, ease:"power1.out"}}]}}, {ping2_start:.3f});

  tl.seek(0);
  window.__timelines["main"] = tl;
}})();
</script></body></html>
"""


def build_hop(from_label, to_label, color, output_path, fps=30, quality="standard"):
    slug = "{0}-{1}".format(from_label.lower().replace(" ", "-"), to_label.lower().replace(" ", "-"))
    proj = os.path.join(WORK, "hops", "{0}_proj".format(slug))
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)

    html = HTML_TEMPLATE.format(
        total_dur=TOTAL_DUR, fps=fps, color=color,
        curve_far_d=CURVE_FAR_D, curve_near_d=CURVE_NEAR_D,
        arc_d=ARC_D, plane_d=PLANE_D,
        dep_x=DEP[0], dep_y=DEP[1], arr_x=ARR[0], arr_y=ARR[1],
        flight_start=FLIGHT_START, flight_dur=FLIGHT_DUR,
        ping_start=PING_START, ping1_start=PING_START + 0.15, ping2_start=PING_START + 0.30,
    )

    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(proj, "meta.json"), "w") as f:
        json.dump({"id": "hop_{0}".format(slug), "name": "Migration 360 hop: {0} -> {1}".format(from_label, to_label)}, f)

    cli = hyperframes_cli()
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(output_path),
                     "-f", str(fps), "-q", quality, "--sdr", "--quiet"],
                    cwd=proj, check=True)
    print("[build_hop] rendered {0} ({1:.2f}s)".format(output_path, TOTAL_DUR))
    return output_path


if __name__ == "__main__":
    out = build_hop("PERTH", "ADELAIDE", "#E84B37",
                     os.path.join(WORK, "hop_perth_adelaide.mp4"))
    print("Validation hop:", out)
