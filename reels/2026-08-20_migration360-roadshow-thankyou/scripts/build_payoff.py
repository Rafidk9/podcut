"""Payoff segment for the Migration 360 Roadshow thank-you reel -- the
emotional high point right before the end card. ~8s, 1080x1920, 30fps, same
render pipeline as every other segment (build_city_block.py / build_hop.py /
build_end_card.py / hyperframes_cli()).

Concept: every hop transition so far (build_hop.py) only ever showed two
cities at a time, zoomed into one leg of the journey. This is the FIRST beat
that pulls back to the whole route -- all 5 stops, connected, fully lit at
once -- before handing off into the closing stat card.

Beats (~8s total):
  0.00-0.40  scene fade-in: background, a faint "ghost" outline of the whole
             route (all 4 connecting arcs, low-opacity static dashes -- so
             the viewer sees the complete shape of the journey immediately,
             even before any city lights up), all 5 pins present but dim
             (unlit rings), header fades in -- a small white badge card with
             the real Migration 360 Roadshow lockup artwork (cropped to just
             the wordmark+roundel, see MIGRATION360_BADGE; no tagline ribbon,
             too small to read at this size) above the "THE WHOLE JOURNEY"
             headline.
  0.40-2.20  chain reaction: each pin lights up in tour order (Perth ->
             Adelaide -> Brisbane -> Melbourne -> Hobart & Launceston),
             staggered ~0.35s apart. Between each pair of pins, the
             connecting arc "draws" in the ARRIVING city's stamp colour
             (same mask-reveal technique as build_hop.py's dotted arc,
             reused verbatim -- see that module's docstring for why a
             plain stroke-dashoffset tween can't grow a short dash
             pattern) right as the next pin lights, reading as the colour
             physically travelling stop to stop.
  2.20-3.00  solidify: once all 5 are lit, a solid colour overlay fades in
             on top of each dotted arc (the "all lines now solid/fully
             drawn" feel from the brief) while all 5 pins pulse together
             once, in sync -- the single "look how far we went together"
             beat -- then holds to a clean, fully-resolved frame.
  3.00-3.70  the map recedes: fades + scales down as a single unit (pins,
             arcs, header all children of one #mapStage wrapper, so one
             tween handles the whole recede).
  3.30-4.65  stat card enters (overlapping the map's recede for a smooth
             handoff): PFEC logo, then the hero stat "300+ ATTENDEES"
             (large, brand yellow), then "6 CITIES" / "5 STATES" side by
             side (smaller), then a short pull-quote in Gazi's own words
             (see work/gazi_P2.transcript.json: "...roadshow across six
             cities was a huge success, welcoming more than 300
             attendees.") -- simple scale/fade entrance, no elaborate
             choreography, per the brief. Numbers: 6 CITIES / 5 STATES
             (not "5 cities" just because there are only 5 visual
             pins/blocks -- Hobart & Launceston is one combined block/stamp
             covering 2 physical cities, so the true count across 5
             states is 6 cities, matching Gazi's own phrasing).
  4.65-8.00  hold on the settled stat card.

Renders work/segment_payoff.mp4. No audio track (matches every other
segment_*.mp4 -- audio is added later in the composite stage).
"""
import base64
import json
import os
import shutil
import subprocess
import sys

_THIS = os.path.abspath(__file__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(_THIS))))  # reels/
from reel_paths import WORK, REEL, ASSETS_ROOT, hyperframes_cli  # noqa: E402

FPS = 30
TOTAL_DUR = 8.0

INDIGO = "#100796"
YELLOW = "#FFC500"
RED = "#E84B37"
CYAN = "#00B3E3"
GREEN = "#31EB7C"

LOGO_SVG = os.path.join(ASSETS_ROOT, "logo", "pfec-logo-white.svg")

# Real campaign artwork for the header badge (see build_open.py's module
# docstring for provenance): a build-time crop of the actual Migration 360
# Roadshow lockup down to just the wordmark+roundel (no tagline ribbon --
# too small to read as a compact header badge, so it's dropped here; the
# fuller crop with the ribbon is used in build_open.py's larger title card
# instead).
MIGRATION360_BADGE = os.path.join(REEL, "assets", "migration360", "migration360_lockup_compact.png")


def _data_uri(path, mime):
    with open(path, "rb") as f:
        b = f.read()
    return f"data:{mime};base64,{base64.b64encode(b).decode()}"
FF = shutil.which("ffmpeg") or "ffmpeg"

# --- the 5 stops, in tour order, each with its own stamp colour (same
# colours used by that city's own build_<city>.py block) and a fixed,
# deliberately-abstract zigzag position down the frame -- same "abstract,
# not a literal map" language as build_hop.py's fixed arc geometry. ---
CITIES = [
    {"name": "PERTH", "color": YELLOW, "pos": (360, 330), "lines": ["PERTH"]},
    {"name": "ADELAIDE", "color": RED, "pos": (760, 650), "lines": ["ADELAIDE"]},
    {"name": "BRISBANE", "color": YELLOW, "pos": (340, 970), "lines": ["BRISBANE"]},
    {"name": "MELBOURNE", "color": CYAN, "pos": (760, 1290), "lines": ["MELBOURNE"]},
    {"name": "HOBART & LAUNCESTON", "color": GREEN, "pos": (360, 1610), "lines": ["HOBART &", "LAUNCESTON"]},
]

# --- chain-reaction timing ---
LIGHT_START = 0.50
STAGGER = 0.35
LIGHT_TIMES = [LIGHT_START + i * STAGGER for i in range(len(CITIES))]  # 0.50 .. 1.90

SOLIDIFY_START = 2.20
RECEDE_START = 3.00
CARD_START = 3.30


def _inlined_logo_svg(style):
    # Inline the SVG (not a data-URI <img>, which can't be restyled) so the
    # sizing `style` attribute can be injected below. pfec-logo-white.svg
    # is a pre-recoloured all-white variant (.st0/.st1/.st2 all #FFFFFF) --
    # see assets/logo/README.md -- so no runtime colour patching is needed
    # here any more; it just reads cleanly on this composition's indigo
    # background as-is.
    with open(LOGO_SVG, "r", encoding="utf-8") as f:
        raw = f.read()
    start = raw.index("<svg")
    svg = raw[start:]
    svg = svg.replace("<svg ", f'<svg style="{style}" ', 1)
    return svg


def _arc_d(p1, ctrl, p2):
    return f"M {p1[0]} {p1[1]} Q {ctrl[0]} {ctrl[1]} {p2[0]} {p2[1]}"


def build_payoff(output_path=None, fps=FPS, quality="standard"):
    proj = os.path.join(WORK, "payoff_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)

    # --- pins ---
    pin_html = []
    pin_light_js = []
    for i, city in enumerate(CITIES):
        x, y = city["pos"]
        color = city["color"]
        t = LIGHT_TIMES[i]
        label_html = "".join(f'<div>{ln}</div>' for ln in city["lines"])
        font_size = 26 if len(city["lines"]) > 1 else 30
        pin_html.append(
            f'<div class="pin" id="pin{i}" style="left:{x}px;top:{y}px">'
            f'<div class="pinRing"></div>'
            f'<div class="pinCore"></div>'
            f'<div class="pinLabel" style="font-size:{font_size}px">{label_html}</div>'
            f'</div>'
        )
        pin_light_js.append(
            f'tl.to("#pin{i} .pinRing",{{borderColor:"{color}",duration:0.28,ease:"power2.out"}},{t:.3f});')
        pin_light_js.append(
            f'tl.to("#pin{i} .pinCore",{{keyframes:['
            f'{{backgroundColor:"rgba(255,255,255,.18)",boxShadow:"0 0 0px transparent",scale:1,duration:0}},'
            f'{{backgroundColor:"{color}",boxShadow:"0 0 44px {color}",scale:1.4,duration:0.16,ease:"back.out(2.4)"}},'
            f'{{scale:1.0,duration:0.18,ease:"power2.out"}}]}},{t:.3f});')
        pin_light_js.append(
            f'tl.fromTo("#pin{i} .pinLabel",{{opacity:0,y:10}},'
            f'{{opacity:1,y:0,duration:0.3,ease:"power2.out"}},{t + 0.08:.3f});')

    # --- connecting arcs: 4 legs, each in the ARRIVING city's colour,
    # drawn (mask-reveal, same trick as build_hop.py) across the window
    # between the two pins' own light times. A faint always-on "ghost"
    # outline (below) shows the full route shape from the very start. ---
    ghost_paths = []
    arc_defs = []  # (idx, arc_d, color, start, dur)
    for i in range(len(CITIES) - 1):
        p1 = CITIES[i]["pos"]
        p2 = CITIES[i + 1]["pos"]
        mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        ctrl = (mid[0], mid[1] - 40)  # gentle upward bow, matches hop's bezier bow
        d = _arc_d(p1, ctrl, p2)
        ghost_paths.append(d)
        color = CITIES[i + 1]["color"]
        start = LIGHT_TIMES[i]
        dur = LIGHT_TIMES[i + 1] - LIGHT_TIMES[i]
        arc_defs.append((i, d, color, start, dur))

    ghost_svg = "".join(
        f'<path d="{d}" stroke="rgba(255,255,255,.22)" stroke-width="3" '
        f'stroke-dasharray="8 14" stroke-linecap="round" fill="none"/>'
        for d in ghost_paths)

    arc_js = []
    arc_paths_svg = "".join(
        f'<path id="arcDotted{i}" d="{d}" stroke="{color}" stroke-width="6" '
        f'stroke-dasharray="10 16" stroke-linecap="round" fill="none" mask="url(#drawMask{i})" '
        f'opacity="0.95" style="filter:drop-shadow(0 0 6px {color}99)"/>'
        f'<path id="arcSolid{i}" d="{d}" stroke="{color}" stroke-width="4" stroke-linecap="round" '
        f'fill="none" opacity="0"/>'
        for i, d, color, start, dur in arc_defs)

    for i, d, color, start, dur in arc_defs:
        arc_js.append(
            f'tl.to(maskPath{i}, {{strokeDashoffset:0, duration:{dur:.3f}, ease:"none"}}, {start:.3f});')
    solidify_js = []
    for n, (i, d, color, start, dur) in enumerate(arc_defs):
        solidify_js.append(
            f'tl.to("#arcSolid{i}",{{opacity:0.55,duration:0.4,ease:"power2.out"}},{SOLIDIFY_START + n * 0.1:.3f});')

    mask_defs = "".join(
        f'<mask id="drawMask{i}"><path id="maskPath{i}" d="{d}" stroke="#fff" stroke-width="70" '
        f'stroke-linecap="round" fill="none"/></mask>'
        for i, d, color, start, dur in arc_defs)
    mask_len_js = "".join(
        f'var maskPath{i} = document.getElementById("maskPath{i}"); '
        f'var len{i} = maskPath{i}.getTotalLength(); '
        f'maskPath{i}.style.strokeDasharray = len{i}; maskPath{i}.style.strokeDashoffset = len{i};\n  '
        for i, d, color, start, dur in arc_defs)

    logo_svg_small = _inlined_logo_svg("display:block;width:100%;height:auto")
    badge_uri = _data_uri(MIGRATION360_BADGE, "image/png")

    html = f"""<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:1080px;height:1920px;overflow:hidden;background:{INDIGO}}}
  .stage{{position:absolute;inset:0}}
  #bg{{position:absolute;inset:0;opacity:0;
      background:
        radial-gradient(ellipse 900px 900px at 50% 22%, rgba(255,255,255,.08), transparent 60%),
        linear-gradient(160deg,#1A0FB8 0%,{INDIGO} 46%,#0A0730 100%);}}
  #glowBloom{{position:absolute;inset:0;opacity:0;pointer-events:none;
      background:radial-gradient(ellipse 700px 900px at 50% 50%, rgba(255,255,255,.16), transparent 65%);}}

  #mapStage{{position:absolute;inset:0}}

  #header{{position:absolute;left:0;top:96px;width:1080px;text-align:center;opacity:0}}
  #headerBadge{{display:inline-block;background:#fff;border-radius:16px;padding:12px 24px 10px;
      box-shadow:0 12px 34px rgba(0,0,0,.4);margin-bottom:18px}}
  #headerBadge img{{display:block;height:52px;width:auto}}
  #header .headline{{font-family:"Poppins",sans-serif;font-weight:900;font-size:56px;letter-spacing:.01em;
      color:#fff;text-shadow:0 4px 0 rgba(0,0,0,.25)}}

  .pin{{position:absolute;transform:translate(-50%,-50%);text-align:center}}
  .pinRing{{width:52px;height:52px;border-radius:50%;border:3px solid rgba(255,255,255,.35);
      box-sizing:border-box;margin:0 auto}}
  .pinCore{{position:absolute;left:50%;top:50%;width:22px;height:22px;border-radius:50%;
      background:rgba(255,255,255,.18);transform:translate(-50%,-50%) scale(1)}}
  .pinLabel{{margin-top:10px;font-family:"Poppins",sans-serif;font-weight:800;letter-spacing:.05em;
      color:#fff;white-space:nowrap;opacity:0;text-shadow:0 2px 6px rgba(0,0,0,.5)}}

  #cardBg{{position:absolute;inset:0;opacity:1}}
  #statCard{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
      justify-content:center;gap:26px;opacity:0;transform:scale(.85)}}
  #statLogo{{width:210px;opacity:0;transform:translateY(14px)}}
  #heroWrap{{text-align:center}}
  #heroNum{{font-family:"Poppins",sans-serif;font-weight:900;font-size:190px;line-height:1;color:{YELLOW};
      opacity:0;transform:translateY(24px);
      text-shadow:0 8px 0 rgba(0,0,0,.25), 0 0 70px rgba(255,197,0,.25)}}
  #heroLabel{{margin-top:2px;font-family:"Poppins",sans-serif;font-weight:800;font-size:46px;
      letter-spacing:.16em;color:#fff;opacity:0;transform:translateY(16px)}}
  #statRow{{display:flex;align-items:center;gap:46px}}
  .statBlock{{text-align:center;opacity:0;transform:translateY(16px)}}
  .statBlockNum{{font-family:"Poppins",sans-serif;font-weight:900;font-size:88px;line-height:1}}
  .statBlockLabel{{margin-top:2px;font-family:"Poppins",sans-serif;font-weight:700;font-size:28px;
      letter-spacing:.14em;color:rgba(255,255,255,.85)}}
  .statDivider{{width:2px;height:70px;background:rgba(255,255,255,.25)}}
  #quoteLine{{max-width:820px;padding:0 40px;text-align:center;font-family:"Poppins",sans-serif;
      font-style:italic;font-weight:500;font-size:27px;line-height:1.45;color:rgba(255,255,255,.75);
      opacity:0}}
  #quoteLine .attrib{{display:block;margin-top:10px;font-style:normal;font-weight:700;font-size:22px;
      letter-spacing:.1em;color:{YELLOW}}}
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="{TOTAL_DUR:.3f}" data-fps="{fps}" data-width="1080" data-height="1920">

  <div class="stage" id="bg"></div>
  <div class="stage" id="glowBloom"></div>

  <div id="mapStage">
    <div id="header">
      <div id="headerBadge"><img src="{badge_uri}" alt="Migration 360 Roadshow"/></div>
      <div class="headline">THE WHOLE JOURNEY</div>
    </div>

    <svg width="1080" height="1920" viewBox="0 0 1080 1920" style="position:absolute;inset:0">
      <defs>{mask_defs}</defs>
      {ghost_svg}
      {arc_paths_svg}
    </svg>

    {"".join(pin_html)}
  </div>

  <div id="statCard">
    <div id="statLogo">{logo_svg_small}</div>
    <div id="heroWrap">
      <div id="heroNum">300+</div>
      <div id="heroLabel">ATTENDEES</div>
    </div>
    <div id="statRow">
      <div class="statBlock">
        <div class="statBlockNum" style="color:{CYAN}">6</div>
        <div class="statBlockLabel">CITIES</div>
      </div>
      <div class="statDivider"></div>
      <div class="statBlock">
        <div class="statBlockNum" style="color:{GREEN}">5</div>
        <div class="statBlockLabel">STATES</div>
      </div>
    </div>
    <div id="quoteLine">&ldquo;...roadshow across six cities was a huge success, welcoming
      more than 300 attendees.&rdquo;<span class="attrib">&mdash; GAZI TANVIR HOSSAIN</span></div>
  </div>

</div>
<script>
(function(){{
  window.__timelines = window.__timelines || {{}};

  {mask_len_js}
  var tl = gsap.timeline({{paused:true}});

  // --- 0.00-0.40: scene fade-in (bg, ghost route, header, dim pins) ---
  tl.to("#bg", {{opacity:1, duration:0.32}}, 0);
  tl.fromTo(".pin", {{opacity:0}}, {{opacity:1, duration:0.3, stagger:0.02}}, 0.06);
  tl.fromTo("#header", {{opacity:0, y:-8}}, {{opacity:1, y:0, duration:0.35}}, 0.15);

  // --- 0.40-2.20: chain reaction -- pins light + arcs draw, tour order ---
  {chr(10).join("  " + line for line in arc_js)}
  {chr(10).join("  " + line for line in pin_light_js)}

  // --- 2.20-3.00: solidify -- solid overlay fades in over each dotted
  // arc, ALL 5 pins pulse together once (the single "look how far we
  // went" beat), soft bloom lifts behind the whole map ---
  {chr(10).join("  " + line for line in solidify_js)}
  tl.to("#glowBloom", {{opacity:1, duration:0.5, ease:"power2.out"}}, {SOLIDIFY_START:.3f});
  tl.to("#glowBloom", {{opacity:0, duration:0.6, ease:"power2.in"}}, {SOLIDIFY_START + 0.55:.3f});
  tl.to(".pinCore", {{scale:1.14, duration:0.22, ease:"power2.out", stagger:0.03}}, {SOLIDIFY_START + 0.15:.3f});
  tl.to(".pinCore", {{scale:1.0, duration:0.28, ease:"power2.out", stagger:0.03}}, {SOLIDIFY_START + 0.45:.3f});

  // --- 3.00-3.70: the whole map recedes as one unit ---
  tl.to("#mapStage", {{opacity:0, scale:0.9, duration:0.7, ease:"power2.inOut"}}, {RECEDE_START:.3f});

  // --- 3.30+: stat card enters -- simple scale/fade, then a calm
  // logo -> hero -> row -> quote stagger, settled well before the hold ---
  tl.to("#statCard", {{opacity:1, scale:1.0, duration:0.6, ease:"back.out(1.6)"}}, {CARD_START:.3f});
  tl.to("#statLogo", {{opacity:1, y:0, duration:0.4, ease:"power2.out"}}, {CARD_START + 0.05:.3f});
  tl.to("#heroNum", {{opacity:1, y:0, duration:0.5, ease:"power2.out"}}, {CARD_START + 0.25:.3f});
  tl.to("#heroLabel", {{opacity:1, y:0, duration:0.4, ease:"power2.out"}}, {CARD_START + 0.38:.3f});
  tl.to(".statBlock", {{opacity:1, y:0, duration:0.4, ease:"power2.out", stagger:0.12}}, {CARD_START + 0.58:.3f});
  tl.to("#quoteLine", {{opacity:1, duration:0.5, ease:"power2.out"}}, {CARD_START + 0.95:.3f});

  tl.seek(0);
  window.__timelines["main"] = tl;
}})();
</script></body></html>
"""

    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(proj, "meta.json"), "w") as f:
        json.dump({"id": "segment_payoff", "name": "Migration 360 Roadshow payoff: whole route + stats"}, f)

    if output_path is None:
        output_path = os.path.join(WORK, "segment_payoff.mp4")
    cli = hyperframes_cli()
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(output_path),
                     "-f", str(fps), "-q", quality, "--sdr", "--quiet"],
                    cwd=proj, check=True)
    print(f"[build_payoff] rendered {output_path} ({TOTAL_DUR:.2f}s)")
    return output_path


def grab_stills(video_path):
    stems = [("2.0", "still1"), ("2.9", "still2"), ("6.0", "still3")]
    for t, suffix in stems:
        out = os.path.join(WORK, f"segment_payoff_{suffix}.png")
        subprocess.run([FF, "-y", "-ss", t, "-i", video_path, "-frames:v", "1", out],
                        check=True, capture_output=True, text=True)
        print(f"[build_payoff] still: {out}")


def main():
    out = build_payoff()
    grab_stills(out)
    print("Payoff segment:", out)


if __name__ == "__main__":
    main()
