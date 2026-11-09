"""Reusable "persistent route map" transition generator for the Migration
360 Roadshow thank-you reel -- REPLACES the 5 isolated build_hop.py "fly
between just 2 cities" clips with ONE continuous map that builds up
progressively across the whole reel: each reveal clip shows the FULL 5-pin
route (same pin positions/colours/dotted-arc technique as
build_payoff.py's end-of-video "whole journey" beat, extracted/generalised
here so it can render at any intermediate state, not just "all 5 lit"),
with:

  - cities BEFORE the current one already lit, labelled and connected by a
    SOLID settled arc, rendered in that final state from frame 0 (no
    re-animation -- they already happened, they're just... there),
  - the arc connecting to the CURRENT city drawing in live during the clip
    (mask-reveal dash trick, verbatim from build_hop.py/build_payoff.py --
    see either module's docstring for why a plain stroke-dashoffset tween
    can't grow a short dash pattern), and the current city's pin lighting
    up near the end of the draw,
  - cities AFTER the current one shown as dim/unlit ghost pins (visible,
    not invisible -- the point is "whole route, with progress", matching
    build_payoff.py's always-on ghost-route treatment) so every clip shows
    the complete shape of the journey, just at a different point of
    completion.

Because every clip renders the SAME full map (same positions, same fixed
1080x1920 canvas, same colours), cutting reveal(N) -> city block -> a
static "settled" frame -> reveal(N+1) reads as one persistent map drawing
itself over the course of the reel, rather than N disconnected mini-maps.

Public interface:

    build_route_map_reveal(reveal_index, output_path, fps=30,
                            quality="standard") -> str

reveal_index (1..5, 1-based, matches tour order / CITIES below):
  - cities 1..reveal_index-1 are already fully lit + connected (static,
    "already happened" -- rendered pre-solidified from frame 0, they do
    NOT re-animate),
  - the leg connecting city (reveal_index-1) -> city (reveal_index) draws
    in live during this clip ("happening now"), and city reveal_index's
    pin lights up as that arc completes,
  - cities reveal_index+1..5 stay dim/unlit ghost pins.
  - reveal_index=1 is a special case (the tour's opening "taxi-in" --
    there is no previous city to connect from): a short custom
    off-canvas-in approach path draws in and fades (flavour only, not a
    permanent route leg) while Perth's pin lights up; cities 2-5 are dim
    ghosts. No settled legs/pins exist yet.

Geometry/colours/tour order are lifted verbatim from build_payoff.py's
CITIES list -- see that module for why these positions ("abstract, not a
literal map", zigzag down the frame) and colours (matching each city's own
build_<city>.py stamp colour) were chosen. Kept as a second copy here
rather than importing from build_payoff (a rendering script, not a shared
lib) to avoid a fragile cross-import between two independent build_*.py
entry points; if these ever drift, this module's CITIES is the one to
correct to match (build_payoff.py is the original).

Timing (total {CLIP_DUR}s, matching the old build_hop.py clip length so it
drops into the same slot in build_final.py's segment list):
  0.00-0.30  scene fade-in: whole stage fades in as one unit. Settled
             pins/arcs, the current-leg's ghost dash, and the dim ghost
             pins for later cities are all just PRESENT in their resting
             state as the fade completes -- nothing settled re-animates.
  0.15-1.20  the live leg: dotted arc mask-reveals in the arriving city's
             colour (reveal_index=1: a short custom off-canvas approach
             path instead of a city-to-city leg). No plane glyph -- see
             the NOTE above CITIES/timing constants for why one was tried
             and dropped.
  1.10-1.60  arrival: radar-ping bloom at the arriving pin (reused from
             build_hop.py) overlapping the tail of the draw, then the pin
             itself lights (ring colour + core pop + label fade-in,
             reused from build_payoff.py's per-city light-up), then the
             solid arc overlay fades in on top of the dotted line (the
             "now fully drawn/settled" look, matching build_payoff.py's
             solidify beat) -- by clip end this leg/pin are in exactly the
             "already settled" state the NEXT reveal clip renders as static.
  1.60-1.70  short hold on the newly-settled frame.
"""
import base64
import json
import os
import shutil
import subprocess
import sys

_THIS = os.path.abspath(__file__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(_THIS))))  # reels/
from reel_paths import WORK, hyperframes_cli  # noqa: E402

FPS = 30
CLIP_DUR = 1.70  # matches build_hop.py's TOTAL_DUR -- same slot in build_final.py

INDIGO = "#100796"
YELLOW = "#FFC500"
RED = "#E84B37"
CYAN = "#00B3E3"
GREEN = "#31EB7C"

FF = shutil.which("ffmpeg") or "ffmpeg"

# --- the 5 stops, in tour order -- verbatim copy of build_payoff.py's
# CITIES (positions, colours, zigzag layout, labels). See that module's
# docstring for provenance/rationale. ---
CITIES = [
    {"name": "PERTH", "color": YELLOW, "pos": (360, 330), "lines": ["PERTH"]},
    {"name": "ADELAIDE", "color": RED, "pos": (760, 650), "lines": ["ADELAIDE"]},
    {"name": "BRISBANE", "color": YELLOW, "pos": (340, 970), "lines": ["BRISBANE"]},
    {"name": "MELBOURNE", "color": CYAN, "pos": (760, 1290), "lines": ["MELBOURNE"]},
    {"name": "HOBART & LAUNCESTON", "color": GREEN, "pos": (360, 1610), "lines": ["HOBART &", "LAUNCESTON"]},
]

# NOTE: an earlier version of this module rode a build_hop.py-style plane
# glyph along the drawing arc via GSAP MotionPathPlugin. Dropped after
# validation stills showed the plane freezing near the path's start instead
# of tracking the arc's progress across repeated non-sequential tl.seek()
# calls (the render pipeline's per-frame capture) -- a real MotionPathPlugin
# quirk, not a one-off. build_payoff.py (the reference this module
# generalises) has no plane either, so dropping it keeps this MORE
# consistent with the established look, not less. The arc-draw + pin-light
# beat alone reads as "one persistent map building up" on its own -- see
# this module's own validation stills. Revisit MotionPathPlugin only if a
# future need justifies re-debugging it.

# --- timing (seconds), see module docstring ---
FADE_DUR = 0.30
FLIGHT_START = 0.15
FLIGHT_DUR = 1.05          # flight window ends at 1.20
PING_START = 1.10
LIGHT_TIME = 1.15          # pin ring/core/label light-up start
SOLIDIFY_START = 1.30      # solid arc overlay fade-in


def _arc_d(p1, ctrl, p2):
    return f"M {p1[0]} {p1[1]} Q {ctrl[0]} {ctrl[1]} {p2[0]} {p2[1]}"


def _leg_geometry(i):
    """Leg i connects CITIES[i] -> CITIES[i+1]. Same gentle-upward-bow
    bezier control point as build_payoff.py (mid, mid.y-40)."""
    p1 = CITIES[i]["pos"]
    p2 = CITIES[i + 1]["pos"]
    mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    ctrl = (mid[0], mid[1] - 40)
    return p1, ctrl, p2, _arc_d(p1, ctrl, p2)


# All 4 legs' geometry, precomputed once -- used for the always-on ghost
# route (every reveal state shows the full shape) and for whichever
# subset is "settled"/"current" for a given reveal_index.
LEGS = [_leg_geometry(i) for i in range(len(CITIES) - 1)]

# --- reveal_index=1's special off-canvas "taxi-in" approach path (no
# previous city exists yet) -- a short bezier from off the lower-left edge
# of the canvas into Perth's pin position, flavour only (fades after
# arrival, not a permanent route leg). ---
TAXI_DEP = (-90, 720)
TAXI_CTRL = (90, 480)


def _pin_html(i, city, state):
    """state: 'settled' (already lit, static), 'current' (lights up
    during this clip), or 'dim' (unlit ghost, visible but de-emphasised)."""
    x, y = city["pos"]
    color = city["color"]
    label_html = "".join(f"<div>{ln}</div>" for ln in city["lines"])
    font_size = 26 if len(city["lines"]) > 1 else 30
    if state == "settled":
        ring_style = f"border-color:{color}"
        core_style = f"background-color:{color};box-shadow:0 0 30px {color};transform:translate(-50%,-50%) scale(1)"
        label_style = "opacity:1"
    elif state == "dim":
        ring_style = "border-color:rgba(255,255,255,.35)"
        core_style = "background-color:rgba(255,255,255,.18);transform:translate(-50%,-50%) scale(1)"
        label_style = "opacity:.45"
    else:  # current -- starts dim, JS animates it up during the clip
        ring_style = "border-color:rgba(255,255,255,.35)"
        core_style = "background-color:rgba(255,255,255,.18);transform:translate(-50%,-50%) scale(1)"
        label_style = "opacity:0"
    return (
        f'<div class="pin" id="pin{i}" style="left:{x}px;top:{y}px">'
        f'<div class="pinRing" style="{ring_style}"></div>'
        f'<div class="pinCore" style="{core_style}"></div>'
        f'<div class="pinLabel" style="font-size:{font_size}px;{label_style}">{label_html}</div>'
        f'</div>'
    )


def build_route_map_reveal(reveal_index, output_path=None, fps=FPS, quality="standard"):
    assert 1 <= reveal_index <= len(CITIES), "reveal_index must be 1..5"
    current = reveal_index - 1  # 0-based index into CITIES of the city lighting up now

    proj = os.path.join(WORK, "route_maps", f"reveal{reveal_index}_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)

    # --- pins ---
    pin_html = []
    for i, city in enumerate(CITIES):
        if i < current:
            state = "settled"
        elif i == current:
            state = "current"
        else:
            state = "dim"
        pin_html.append(_pin_html(i, city, state))

    # --- ghost route: full shape, always on, every leg (unchanged from
    # build_payoff.py's always-on ghost outline) ---
    ghost_svg = "".join(
        f'<path d="{d}" stroke="rgba(255,255,255,.22)" stroke-width="3" '
        f'stroke-dasharray="8 14" stroke-linecap="round" fill="none"/>'
        for (_, _, _, d) in LEGS)

    settled_arcs_svg = []
    live_arc_svg = ""
    mask_defs = ""
    mask_len_js = ""
    arc_draw_js = ""
    solidify_js = ""
    ping_svg = ""
    ping_js = ""

    if current > 0:
        # legs strictly before the live one: already fully settled/solid,
        # static from frame 0 (no re-animation).
        for i in range(current - 1):
            _, _, _, d = LEGS[i]
            color = CITIES[i + 1]["color"]
            settled_arcs_svg.append(
                f'<path d="{d}" stroke="{color}" stroke-width="6" stroke-dasharray="10 16" '
                f'stroke-linecap="round" fill="none" opacity="0.95" '
                f'style="filter:drop-shadow(0 0 6px {color}99)"/>'
                f'<path d="{d}" stroke="{color}" stroke-width="4" stroke-linecap="round" '
                f'fill="none" opacity="0.55"/>'
            )

        # the live leg: current-1 -> current, drawing in during this clip
        live_i = current - 1
        p1, ctrl, p2, d = LEGS[live_i]
        color = CITIES[current]["color"]
        live_arc_svg = (
            f'<path id="arcDotted" d="{d}" stroke="{color}" stroke-width="6" '
            f'stroke-dasharray="10 16" stroke-linecap="round" fill="none" mask="url(#drawMask)" '
            f'opacity="0.95" style="filter:drop-shadow(0 0 6px {color}99)"/>'
            f'<path id="arcSolid" d="{d}" stroke="{color}" stroke-width="4" stroke-linecap="round" '
            f'fill="none" opacity="0"/>'
        )
        mask_defs = (
            f'<mask id="drawMask"><path id="maskPath" d="{d}" stroke="#fff" stroke-width="70" '
            f'stroke-linecap="round" fill="none"/></mask>'
        )
        mask_len_js = (
            'var maskPath = document.getElementById("maskPath"); '
            'var len = maskPath.getTotalLength(); '
            'maskPath.style.strokeDasharray = len; maskPath.style.strokeDashoffset = len;\n'
        )
        arc_draw_js = (
            f'tl.to(maskPath, {{strokeDashoffset:0, duration:{FLIGHT_DUR:.3f}, ease:"none"}}, {FLIGHT_START:.3f});'
        )
        solidify_js = (
            f'tl.to("#arcSolid",{{opacity:0.55,duration:0.35,ease:"power2.out"}},{SOLIDIFY_START:.3f});'
        )
        arr_x, arr_y = p2
    else:
        # reveal_index == 1: opening taxi-in, no previous city -- a short
        # custom off-canvas approach path instead of a route leg.
        color = CITIES[0]["color"]
        d = _arc_d(TAXI_DEP, TAXI_CTRL, CITIES[0]["pos"])
        live_arc_svg = (
            f'<path id="arcDotted" d="{d}" stroke="{color}" stroke-width="6" '
            f'stroke-dasharray="10 16" stroke-linecap="round" fill="none" mask="url(#drawMask)" '
            f'opacity="0.95" style="filter:drop-shadow(0 0 6px {color}99)"/>'
        )
        mask_defs = (
            f'<mask id="drawMask"><path id="maskPath" d="{d}" stroke="#fff" stroke-width="70" '
            f'stroke-linecap="round" fill="none"/></mask>'
        )
        mask_len_js = (
            'var maskPath = document.getElementById("maskPath"); '
            'var len = maskPath.getTotalLength(); '
            'maskPath.style.strokeDasharray = len; maskPath.style.strokeDashoffset = len;\n'
        )
        arc_draw_js = (
            f'tl.to(maskPath, {{strokeDashoffset:0, duration:{FLIGHT_DUR:.3f}, ease:"none"}}, {FLIGHT_START:.3f});'
        )
        # taxi guide line is flavour only -- fade it out once Perth lands,
        # instead of solidifying into a permanent-looking route leg.
        solidify_js = (
            f'tl.to("#arcDotted",{{opacity:0,duration:0.4,ease:"power2.out"}},{SOLIDIFY_START:.3f});'
        )
        arr_x, arr_y = CITIES[0]["pos"]

    # arrival ping (reused from build_hop.py) at the arriving pin
    ping_color = CITIES[current]["color"]
    ping_svg = (
        f'<div id="pingWrap" style="position:absolute;left:{arr_x}px;top:{arr_y}px">'
        f'<div id="pingCore" style="position:absolute;left:0;top:0;width:24px;height:24px;'
        f'transform:translate(-50%,-50%) scale(.6);border-radius:50%;background:{ping_color};'
        f'opacity:0;box-shadow:0 0 24px {ping_color}"></div>'
        + "".join(
            f'<div class="ping" id="ping{n}" style="position:absolute;left:0;top:0;width:70px;height:70px;'
            f'transform:translate(-50%,-50%) scale(.2);border-radius:50%;border:4px solid {ping_color};'
            f'opacity:0;box-shadow:0 0 18px {ping_color}66"></div>'
            for n in range(3))
        + '</div>'
    )
    ping_js = (
        f'tl.fromTo("#pingCore",{{opacity:0,scale:0.6}},{{opacity:1,scale:1.15,duration:0.22,ease:"power2.out"}},{PING_START:.3f});'
        f'tl.to("#ping0",{{keyframes:[{{opacity:0,scale:0.2,duration:0}},'
        f'{{opacity:1,scale:0.45,duration:0.08,ease:"power2.out"}},'
        f'{{opacity:0,scale:2.3,duration:0.52,ease:"power1.out"}}]}},{PING_START:.3f});'
        f'tl.to("#ping1",{{keyframes:[{{opacity:0,scale:0.2,duration:0}},'
        f'{{opacity:0.9,scale:0.45,duration:0.08,ease:"power2.out"}},'
        f'{{opacity:0,scale:2.3,duration:0.52,ease:"power1.out"}}]}},{PING_START + 0.15:.3f});'
        f'tl.to("#ping2",{{keyframes:[{{opacity:0,scale:0.2,duration:0}},'
        f'{{opacity:0.8,scale:0.45,duration:0.08,ease:"power2.out"}},'
        f'{{opacity:0,scale:2.3,duration:0.52,ease:"power1.out"}}]}},{PING_START + 0.30:.3f});'
    )

    # current city's pin light-up (verbatim technique from build_payoff.py)
    cur_color = CITIES[current]["color"]
    light_js = (
        f'tl.to("#pin{current} .pinRing",{{borderColor:"{cur_color}",duration:0.28,ease:"power2.out"}},{LIGHT_TIME:.3f});'
        f'tl.to("#pin{current} .pinCore",{{keyframes:['
        f'{{backgroundColor:"rgba(255,255,255,.18)",boxShadow:"0 0 0px transparent",scale:1,duration:0}},'
        f'{{backgroundColor:"{cur_color}",boxShadow:"0 0 44px {cur_color}",scale:1.4,duration:0.16,ease:"back.out(2.4)"}},'
        f'{{scale:1.0,duration:0.18,ease:"power2.out"}}]}},{LIGHT_TIME:.3f});'
        f'tl.fromTo("#pin{current} .pinLabel",{{opacity:0,y:10}},'
        f'{{opacity:1,y:0,duration:0.3,ease:"power2.out"}},{LIGHT_TIME + 0.08:.3f});'
    )

    html = f"""<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:1080px;height:1920px;overflow:hidden;background:{INDIGO}}}
  .stage{{position:absolute;inset:0}}
  #root{{opacity:0}}
  #bg{{position:absolute;inset:0;
      background:
        radial-gradient(ellipse 900px 900px at 50% 22%, rgba(255,255,255,.08), transparent 60%),
        linear-gradient(160deg,#1A0FB8 0%,{INDIGO} 46%,#0A0730 100%);}}

  .pin{{position:absolute;transform:translate(-50%,-50%);text-align:center}}
  .pinRing{{width:52px;height:52px;border-radius:50%;border:3px solid rgba(255,255,255,.35);
      box-sizing:border-box;margin:0 auto}}
  .pinCore{{position:absolute;left:50%;top:50%;width:22px;height:22px;border-radius:50%;
      background:rgba(255,255,255,.18)}}
  .pinLabel{{margin-top:10px;font-family:"Poppins",sans-serif;font-weight:800;letter-spacing:.05em;
      color:#fff;white-space:nowrap;text-shadow:0 2px 6px rgba(0,0,0,.5)}}
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="{CLIP_DUR:.3f}" data-fps="{fps}" data-width="1080" data-height="1920">

  <div class="stage" id="bg"></div>

  <svg width="1080" height="1920" viewBox="0 0 1080 1920" style="position:absolute;inset:0">
    <defs>{mask_defs}</defs>
    {ghost_svg}
    {"".join(settled_arcs_svg)}
    {live_arc_svg}
  </svg>

  {"".join(pin_html)}

  {ping_svg}

</div>
<script>
(function(){{
  window.__timelines = window.__timelines || {{}};

  {mask_len_js}
  var tl = gsap.timeline({{paused:true}});

  // --- 0.00-0.30: whole stage fades in as one unit. Settled pins/arcs
  // and dim ghost pins are simply present in their resting state --
  // nothing already-settled re-animates. ---
  tl.to("#root", {{opacity:1, duration:{FADE_DUR:.3f}}}, 0);

  // --- live leg: dotted arc draws in ---
  {arc_draw_js}

  // --- arrival ping + current pin lights up ---
  {ping_js}
  {light_js}

  // --- settle: solid overlay fades in on top of the freshly-drawn arc
  // (or the taxi guide line fades out for reveal_index==1) ---
  {solidify_js}

  tl.seek(0);
  window.__timelines["main"] = tl;
}})();
</script></body></html>
"""

    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(proj, "meta.json"), "w") as f:
        json.dump({"id": f"route_map_reveal{reveal_index}",
                   "name": f"Migration 360 route map reveal {reveal_index}: {CITIES[current]['name']}"}, f)

    if output_path is None:
        output_path = os.path.join(WORK, f"route_map_reveal{reveal_index}.mp4")
    cli = hyperframes_cli()
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(output_path),
                     "-f", str(fps), "-q", quality, "--sdr", "--quiet"],
                    cwd=proj, check=True)
    print(f"[build_route_map] rendered {output_path} (reveal_index={reveal_index}, {CLIP_DUR:.2f}s)")
    return output_path


def grab_stills(video_path, out_prefix):
    stems = [("0.30", "still1"), ("0.90", "still2"), ("1.55", "still3")]
    for t, suffix in stems:
        out = f"{out_prefix}_{suffix}.png"
        subprocess.run([FF, "-y", "-ss", t, "-i", video_path, "-frames:v", "1", out],
                        check=True, capture_output=True, text=True)
        print(f"[build_route_map] still: {out}")


def main():
    out = build_route_map_reveal(2, output_path=os.path.join(WORK, "route_map_reveal2_TEST.mp4"))
    grab_stills(out, os.path.join(WORK, "route_map_reveal2_TEST"))
    print("Validation reveal:", out)


if __name__ == "__main__":
    main()
