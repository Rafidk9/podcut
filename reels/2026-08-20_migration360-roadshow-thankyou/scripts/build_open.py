"""Renders the cold-open segment for the Migration 360 Roadshow thank-you
reel: a passport cover thudding open -> quick flash of crowd photos from all
4 cities -> title card. ~3.0s, 1080x1920, 30fps, same render pipeline as the
city-block segments (build_city_block.py / hyperframes_cli()), but a
one-off composition of its own (not a city block), so it's a standalone
script rather than a build_city_block() driver.

Beats:
  0.00-0.80s  passport cover (indigo, embossed PFEC/Migration 360 mark)
              thuds into place then swings open on a left-edge hinge
              (rotateY), fading out as it opens.
  0.80-1.60s  4 quick flash cuts (0.2s each) of vetted crowd photos, one
              per city -- reusing the same picks already confirmed good in
              build_perth.py / build_adelaide.py / build_melbourne.py /
              build_brisbane.py's MEDIA_ITEMS (their crowd-shot picks, not
              their video/consult picks):
                Perth:     input/perth/IMG_5890.jpg
                Adelaide:  input/adelaide/IMG_20260806_132638.jpg
                Melbourne: input/melbourne/20260812_124355.jpg
                Brisbane:  WhatsApp Image 2026-08-14 at 12.11.35 PM (5).jpeg
              A brief white flash overlay punches each cut boundary.
  1.60-3.00s  title card: the actual Migration 360 Roadshow campaign artwork
              (white lockup card: wordmark + "360" roundel + tagline ribbon,
              see MIGRATION360_LOCKUP) settles in on a white plaque over the
              indigo background, with a small "2026" year stamp below it
              (which was present under the photos the whole time -- no extra
              backdrop needed once the photos fade out), holding to the end.

All layers are flat, untitled DIRECT CHILDREN of the composition root (per
this project's established HyperFrames timing contract -- see
build_city_block.py's module docstring for why), driven by one paused GSAP
timeline seeked by the renderer.
"""
import base64
import os
import shutil
import subprocess
import sys

_THIS = os.path.abspath(__file__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(_THIS))))  # reels/
from reel_paths import WORK, REEL, ASSETS_ROOT, hyperframes_cli  # noqa: E402

LOGO_SVG = os.path.join(ASSETS_ROOT, "logo", "pfec-logo-white.svg")
FF = shutil.which("ffmpeg") or "ffmpeg"

# Real campaign artwork (see assets/migration360/README or the sibling
# reels' documents/ folders it was sourced from -- the actual Migration 360
# Roadshow poster/lockup used across PFEC's other reels and social posts).
# migration360_lockup_full.png is a build-time crop of migration360_logo.png
# (1536x1024) down to just the wordmark+roundel+tagline (drops the source
# poster's per-city date/venue footer, which is stale info that doesn't
# belong in a retrospective thank-you piece).
MIGRATION360_LOCKUP = os.path.join(REEL, "assets", "migration360", "migration360_lockup_full.png")

INDIGO = "#100796"
YELLOW = "#FFC500"
RED = "#E84B37"
CYAN = "#00B3E3"
GREEN = "#31EB7C"

FPS = 30
TOTAL_DUR = 3.0

CROWD_PHOTOS = [
    ("input/perth/IMG_5890.jpg", "PERTH"),
    ("input/adelaide/IMG_20260806_132638.jpg", "ADELAIDE"),
    ("input/melbourne/20260812_124355.jpg", "MELBOURNE"),
    ("input/brisbane/WhatsApp Image 2026-08-14 at 12.11.35 PM (5).jpeg", "BRISBANE"),
]


def _resolve_path(p):
    return p if os.path.isabs(p) else os.path.join(REEL, p)


def _data_uri(path, mime):
    with open(path, "rb") as f:
        b = f.read()
    return f"data:{mime};base64,{base64.b64encode(b).decode()}"


def _photo_mime(path):
    ext = os.path.splitext(path)[1].lower()
    return "image/png" if ext == ".png" else "image/jpeg"


def _inlined_logo_svg(style):
    # Inline the SVG (not a data-URI <img>, which can't be restyled) so the
    # sizing `style` attribute can be injected below. pfec-logo-white.svg
    # is a pre-recoloured all-white variant (.st0/.st1/.st2 all #FFFFFF) --
    # see assets/logo/README.md -- so no runtime colour patching is needed
    # here any more; it just reads cleanly on this composition's indigo
    # backgrounds as-is.
    with open(LOGO_SVG, "r", encoding="utf-8") as f:
        raw = f.read()
    start = raw.index("<svg")
    svg = raw[start:]
    svg = svg.replace("<svg ", f'<svg style="{style}" ', 1)
    return svg


def build_open(output_path=None, fps=FPS, quality="standard"):
    proj = os.path.join(WORK, "open_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)

    title_logo_svg = _inlined_logo_svg("display:block;height:38px;width:auto")
    crest_logo_svg = _inlined_logo_svg(
        "display:block;width:150px;height:auto;filter:drop-shadow(0 3px 8px rgba(0,0,0,.4))")
    lockup_uri = _data_uri(MIGRATION360_LOCKUP, "image/png")

    # --- flash-cut photo layers (4 x 0.2s, back to back from 0.8 to 1.6) ---
    photo_html = []
    photo_js = []
    flash_html = []
    flash_js = []
    cut_dur = 0.2
    n = len(CROWD_PHOTOS)
    for i, (rel_path, _city) in enumerate(CROWD_PHOTOS):
        start = 0.8 + i * cut_dur
        abs_path = _resolve_path(rel_path)
        uri = _data_uri(abs_path, _photo_mime(abs_path))
        cls = f"flashphoto{i}"
        photo_html.append(
            f'<div id="{cls}" class="clip {cls}" data-start="{start:.3f}" data-duration="{cut_dur:.3f}" '
            f'data-track-index="1" style="position:absolute;inset:0;overflow:hidden;opacity:0;">'
            f'<img class="kb-{cls}" src="{uri}" style="width:100%;height:100%;object-fit:cover;'
            f'filter:brightness(1.03) contrast(1.06) saturate(1.1)"/>'
            f'<div style="position:absolute;inset:0;background:linear-gradient(180deg,'
            f'rgba(16,7,150,.12),transparent 30%,transparent 70%,rgba(16,7,150,.28));"></div>'
            f'</div>'
        )
        # Fast hard cut with a very short anti-strobe fade; fast Ken Burns push for energy.
        photo_js.append(f'tl.set(".{cls}",{{opacity:1}},{start:.3f});')
        photo_js.append(f'tl.to(".{cls}",{{opacity:0,duration:0.03}},{start + cut_dur - 0.03:.3f});')
        photo_js.append(
            f'tl.fromTo(".kb-{cls}",{{scale:1.0}},{{scale:1.07,duration:{cut_dur:.3f},ease:"none"}},{start:.3f});')
        # White flash punch right at the cut boundary (skip the very first --
        # that boundary already has the passport-cover reveal doing the work).
        if i > 0:
            fcls = f"flashpunch{i}"
            flash_html.append(
                f'<div id="{fcls}" class="clip {fcls}" data-start="{start:.3f}" data-duration="0.06" '
                f'data-track-index="2" style="position:absolute;inset:0;background:#fff;opacity:0;"></div>')
            flash_js.append(
                f'tl.fromTo(".{fcls}",{{opacity:.55}},{{opacity:0,duration:0.06,ease:"power2.out"}},{start:.3f});')

    # --- title card (1.6 - 3.0, settles then holds) ---
    title_start = 1.6

    html = f"""<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:1080px;height:1920px;overflow:hidden;background:{INDIGO}}}
  .stage{{position:absolute;inset:0}}
  #bg{{position:absolute;inset:0;
      background:
        radial-gradient(ellipse 900px 900px at 50% 30%, rgba(255,255,255,.10), transparent 60%),
        linear-gradient(160deg,#1A0FB8 0%,{INDIGO} 46%,#0A0730 100%);}}

  #coverWrap{{position:absolute;inset:0;}}
  #cover{{position:absolute;inset:0;transform-origin:left center;background:
      linear-gradient(135deg,#160DAE 0%,{INDIGO} 55%,#0B0768 100%);
      box-shadow:0 0 140px rgba(0,0,0,.65) inset, 40px 0 90px rgba(0,0,0,.5);}}
  #cover .frame{{position:absolute;inset:56px;border:3px solid rgba(255,197,0,.55);border-radius:6px;}}
  #cover .frame-inner{{position:absolute;inset:80px;border:1px solid rgba(255,197,0,.3);border-radius:4px;}}
  #cover .crest{{position:absolute;left:50%;top:38%;transform:translate(-50%,-50%);width:280px;height:280px;
      border-radius:50%;border:5px solid {YELLOW};box-shadow:inset 0 0 0 3px rgba(255,197,0,.4),
      0 0 60px rgba(255,197,0,.18);display:flex;align-items:center;justify-content:center;}}
  #cover .crest svg{{display:block;}}
  #cover .mark{{position:absolute;left:50%;top:60%;transform:translateX(-50%);text-align:center;
      font-family:'Poppins',sans-serif;color:{YELLOW};white-space:nowrap;}}
  #cover .mark .m1{{font-weight:900;font-size:46px;letter-spacing:.16em;
      text-shadow:0 2px 0 rgba(0,0,0,.35), 0 0 30px rgba(255,197,0,.25);}}
  #cover .mark .m2{{margin-top:10px;font-weight:700;font-size:24px;letter-spacing:.32em;color:rgba(255,255,255,.82);}}

  #titleCard{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
      justify-content:center;}}
  #titleRule{{width:180px;height:6px;background:{YELLOW};border-radius:3px;transform:scaleX(0);
      margin-bottom:40px;}}
  #titleArt{{width:760px;background:#fff;border-radius:28px;padding:40px 46px 34px;
      box-shadow:0 26px 80px rgba(0,0,0,.55), 0 0 0 1px rgba(0,0,0,.03);
      opacity:0;transform:scale(.85);}}
  #titleArt img{{display:block;width:100%;height:auto;}}
  #titleYear{{margin-top:28px;font-family:'Poppins',sans-serif;font-weight:800;font-size:46px;
      color:{YELLOW};letter-spacing:.34em;text-align:center;
      text-shadow:0 4px 0 rgba(0,0,0,.28), 0 0 40px rgba(255,197,0,.20);opacity:0;transform:scale(.85);}}
  #titleLogo{{position:absolute;left:50%;bottom:150px;transform:translateX(-50%);opacity:0;}}
  #titleLogo svg{{display:block;}}
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="{TOTAL_DUR:.3f}" data-fps="{fps}" data-width="1080" data-height="1920">

  <div class="stage" id="bg"></div>

{"".join(photo_html)}

{"".join(flash_html)}

  <div id="titleCard">
    <div id="titleRule"></div>
    <div id="titleArt"><img src="{lockup_uri}" alt="Migration 360 Roadshow"/></div>
    <div id="titleYear">2026</div>
  </div>
  <div id="titleLogo">{title_logo_svg}</div>

  <div id="coverWrap">
    <div id="cover">
      <div class="frame"></div>
      <div class="frame-inner"></div>
      <div class="crest">{crest_logo_svg}</div>
      <div class="mark"><div class="m1">MIGRATION 360</div><div class="m2">ROADSHOW</div></div>
    </div>
  </div>

</div>
<script>
(function(){{
  window.__timelines=window.__timelines||{{}};
  var tl=gsap.timeline({{paused:true}});

  // --- passport cover: thud into place, hold, then collapse shut toward a
  // left hinge (2D scaleX, not 3D rotateY -- rotateY here produced an
  // asymmetric perspective warp: the frame border swung into an odd
  // diagonal quadrilateral while centered content barely moved, because
  // perspective-origin defaults to the wrap's own center rather than the
  // hinge line. scaleX toward transform-origin:left keeps the whole panel
  // -- border AND crest/text together -- shrinking uniformly toward the
  // hinge, reading cleanly as a cover swinging shut with zero risk of that
  // warp artifact.) ---
  tl.set("#cover",{{scale:0.94,transformOrigin:"left center"}},0.0);
  tl.to("#cover",{{scale:1.0,duration:0.10,ease:"back.out(3)"}},0.0);
  tl.to("#cover",{{scale:1.0,duration:0.10}},0.10); // hold beat after the thud
  tl.to("#cover",{{scaleX:0.02,duration:0.42,ease:"power2.in"}},0.20);
  tl.to("#cover",{{opacity:0,duration:0.18}},0.44);

{chr(10).join("  " + line for line in photo_js)}

{chr(10).join("  " + line for line in flash_js)}

  // --- title card: settle in and hold ---
  tl.to("#titleRule",{{scaleX:1,duration:0.28,ease:"power2.out"}},{title_start:.3f});
  tl.to("#titleArt",{{opacity:1,scale:1.0,duration:0.34,ease:"back.out(2.0)"}},{title_start+0.06:.3f});
  tl.to("#titleYear",{{opacity:1,scale:1.0,duration:0.30,ease:"back.out(2.0)"}},{title_start+0.20:.3f});
  tl.to("#titleLogo",{{opacity:1,duration:0.3}},{title_start+0.35:.3f});

  tl.seek(0);
  window.__timelines["main"]=tl;
}})();
</script></body></html>
"""

    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    import json as _json
    with open(os.path.join(proj, "meta.json"), "w") as f:
        _json.dump({"id": "segment_open", "name": "Migration 360 Roadshow cold-open"}, f)

    if output_path is None:
        output_path = os.path.join(WORK, "segment_open.mp4")
    cli = hyperframes_cli()
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(output_path),
                     "-f", str(fps), "-q", quality, "--sdr", "--quiet"],
                    cwd=proj, check=True)
    print(f"[build_open] rendered {output_path} ({TOTAL_DUR:.2f}s)")
    return output_path


def grab_stills(video_path):
    stems = [("0.5", "still1"), ("1.2", "still2"), ("2.5", "still3")]
    for t, suffix in stems:
        out = os.path.join(WORK, f"segment_open_{suffix}.png")
        subprocess.run([FF, "-y", "-ss", t, "-i", video_path, "-frames:v", "1", out],
                        check=True, capture_output=True, text=True)
        print(f"[build_open] still: {out}")


def main():
    out = build_open()
    grab_stills(out)
    print("Open segment:", out)


if __name__ == "__main__":
    main()
