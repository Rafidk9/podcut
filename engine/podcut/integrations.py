"""Hand-off steps: video-use (further editing) and HyperFrames (captions /
motion graphics).

Reality of each tool (from their docs):

* video-use (browser-use/video-use) is an *interactive* Claude Code workflow —
  you `cd` into a folder of footage and drive it conversationally; it "waits for
  your OK". It has no non-interactive CLI, so we cannot honestly run it inline.
  Instead we **stage** PodCut's output into a video-use-ready folder (with the
  ElevenLabs key and instructions) for you to drive in Claude Code.

* HyperFrames (heygen-com/hyperframes) is automatable: `npx hyperframes render`
  turns an HTML composition into an MP4 via headless Chrome + ffmpeg, and can
  overlay graphics/captions on existing footage. We generate the composition and
  invoke its CLI. Because that CLI download/run may be gated, we also provide a
  **reliable ffmpeg caption-burn fallback** so captioned output is produced even
  without HyperFrames installed.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
from typing import Optional

from .config import Providers
from . import ffutil


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# --------------------------------------------------------------------------- #
# Captions helpers                                                            #
# --------------------------------------------------------------------------- #
def write_srt(transcript, path: str, words_per_line: int = 7) -> str:
    """Emit an SRT from the transcript (word-timed → grouped caption lines)."""
    def ts(t: float) -> str:
        h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
        ms = int(round((t - int(t)) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    words = [w for w in transcript.words if w.text and not w.text.startswith("[")]
    lines, i, idx = [], 0, 1
    while i < len(words):
        chunk = words[i:i + words_per_line]
        lines.append(f"{idx}\n{ts(chunk[0].start)} --> {ts(chunk[-1].end)}\n"
                     f"{' '.join(w.text for w in chunk)}\n")
        idx += 1
        i += words_per_line
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


_SUB_STYLE = ("FontName=sans-serif,FontSize=16,PrimaryColour=&H00FFFFFF,"
              "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
              "Alignment=2,MarginV=28")


def burn_captions_ffmpeg(video: str, srt: str, out_path: str) -> str:
    """Reliable fallback: burn the SRT onto the video with libass. Runs ffmpeg
    with cwd set to the SRT's folder so we can pass a relative name (avoids the
    Windows drive-colon escaping problem in the subtitles filter)."""
    work = os.path.dirname(os.path.abspath(srt))
    rel = os.path.basename(srt)
    ff = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", os.path.abspath(video),
           "-vf", f"subtitles={rel}:force_style='{_SUB_STYLE}'",
           "-c:a", "copy", os.path.abspath(out_path)]
    subprocess.run(cmd, check=True, cwd=work, capture_output=True, text=True)
    return out_path


# --------------------------------------------------------------------------- #
# HyperFrames                                                                 #
# --------------------------------------------------------------------------- #
_SENTENCE_END = (".", "?", "!")


def _compute_word_groups(words, max_words: int = 4, max_gap: float = 0.6):
    """Group word indices into caption cards: 3-4 words at a time, ALWAYS
    breaking at sentence-ending punctuation so a card never straddles two
    sentences (the end of one sentence and the start of the next must not
    appear in the same card). Also breaks on line length, speaker change, or a
    pause. Returns list of [start_idx, end_idx] inclusive pairs."""
    groups, start = [], 0
    for i in range(len(words)):
        last = i == len(words) - 1
        sentence_end = words[i].text.strip().endswith(_SENTENCE_END)
        long_enough = (i - start + 1) >= max_words
        gap = (not last) and (words[i + 1].start - words[i].end > max_gap)
        spk_change = (not last) and (words[i + 1].speaker != words[i].speaker)
        if last or sentence_end or long_enough or gap or spk_change:
            groups.append([start, i])
            start = i + 1
    return groups


def generate_hyperframes_project(video: str, transcript, proj_dir: str,
                                 zoom_events=None, matte: Optional[str] = None,
                                 lower_thirds=None) -> str:
    """Create a HyperFrames project that plays the footage with the animated
    karaoke word-highlight caption block (from the HyperFrames registry) as a
    transparent sub-composition overlay.

    Layout follows HyperFrames conventions: the host `index.html` holds the muted
    <video> + <audio> on track 0 and references the caption block via
    `data-composition-src` on track 1. The block (compositions/components/
    caption-highlight.html) carries our real word-level transcript in its WORDS /
    RAW_GROUPS arrays and highlights each word as it is spoken. Rendered at 1080p
    so the block's tuned styling (font sizes, spacing) looks right.

    zoom_events: optional list of ZoomEvent (see zoom.py) — punch-in/out effects
    driven by the same conversational annotations that drive camera switching.
    Applied as a GSAP scale transform on a wrapper div so the main video (and the
    matte cutout, if present) zoom together while captions stay fixed size.

    matte: optional path to a subject-only alpha-channel webm/mov (from
    remove_background()). Layered ABOVE the captions at the same position/size as
    the main video, so it naturally re-covers the subject wherever they are —
    giving the illusion the captions sit BEHIND the person (matte occlusion).
    Requires an actual person in frame; see remove_background()'s docstring.

    lower_thirds: optional [{"time": t, "name": "Alice"}, ...] on the EDITED
    timeline — an animated name plate slides in bottom-left at t, holds ~3.5s,
    slides out. Plates don't zoom with the footage (like the captions).
    """
    import json
    os.makedirs(os.path.join(proj_dir, "media"), exist_ok=True)
    os.makedirs(os.path.join(proj_dir, "compositions", "components"), exist_ok=True)
    shutil.copy(video, os.path.join(proj_dir, "media", "input.mp4"))

    matte_rel = None
    if matte and os.path.exists(matte):
        matte_rel = "media/matte" + os.path.splitext(matte)[1]
        shutil.copy(matte, os.path.join(proj_dir, matte_rel))

    W, H = 1920, 1080
    dur = _probe_dur(video)

    words = [w for w in transcript.words if w.text and not w.text.startswith("[")]
    words_js = [{"text": w.text, "start": round(w.start, 3), "end": round(w.end, 3)}
                for w in words]
    groups = _compute_word_groups(words)

    block = (_CAPTION_BLOCK
             .replace("__DUR__", f"{dur:.3f}")
             .replace("__WORDS__", json.dumps(words_js))
             .replace("__GROUPS__", json.dumps(groups)))
    with open(os.path.join(proj_dir, "compositions", "components", "caption-highlight.html"),
              "w", encoding="utf-8") as f:
        f.write(block)

    # NOTE ON STACKING: the matte cutout must sit ABOVE the captions layer (DOM
    # order handles this — later elements paint on top — do NOT nest it inside a
    # z-indexed wrapper shared with the main video: a child's z-index is scoped
    # to its own parent's stacking context, so it can never escape above a
    # sibling of that parent no matter how high the child's z-index is set).
    # Zoom is applied by animating each video element's own CSS transform
    # directly (both main + matte get the identical tween so they stay pixel-
    # aligned), not via a wrapping div. html/body's overflow:hidden clips the
    # transform-scaled video without needing an extra clipping wrapper, since
    # `transform` doesn't affect layout/reflow.
    matte_html = ""
    if matte_rel:
        matte_html = (f'\n    <video id="matte-video" class="clip" data-start="0" '
                     f'data-duration="{dur:.3f}" data-track-index="2" muted src="{matte_rel}" '
                     f'style="position:absolute;inset:0;width:100%;height:100%;'
                     f'object-fit:cover;transform-origin:50% 50%;will-change:transform"></video>')

    zoom_js = json.dumps([
        {"start": round(z.start, 3), "peak": round(z.peak, 3),
         "release": round(z.release, 3), "end": round(z.end, 3), "scale": z.scale}
        for z in (zoom_events or [])
    ])

    # Lower-third name plates: plain host elements (not clips) animated on the
    # same paused timeline as the zoom, so they stay seek-safe/deterministic.
    # Sit between the video (track 0) and the captions overlay in DOM order.
    lts = lower_thirds or []
    lt_html = "".join(
        f'\n    <div class="lt" id="lt-{i}">'
        f'<div class="lt-bar"></div><div class="lt-name">{_esc(e["name"])}</div></div>'
        for i, e in enumerate(lts))
    lt_js = json.dumps([{"time": round(float(e["time"]), 3)} for e in lts])
    lt_css = """
  .lt { position:absolute; left:70px; bottom:330px; display:flex; align-items:stretch;
        background:rgba(10,10,14,0.62); border-radius:12px; overflow:hidden;
        visibility:hidden; will-change:transform,opacity; }
  .lt-bar { width:10px; background:linear-gradient(180deg,#ff4e45,#ff9068); }
  .lt-name { padding:18px 34px 18px 26px; color:#fff; font:800 44px/1.15 sans-serif;
             letter-spacing:0.02em; text-transform:uppercase; }""" if lts else ""

    host = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ width:{W}px; height:{H}px; overflow:hidden; background:#000; }}{lt_css}
</style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{dur:.3f}"
       data-width="{W}" data-height="{H}">
    <video id="main-video" class="clip" data-start="0" data-duration="{dur:.3f}" data-track-index="0"
           muted src="media/input.mp4"
           style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#000;
                  transform-origin:50% 50%;will-change:transform"></video>
    <audio class="clip" data-start="0" data-duration="{dur:.3f}" data-track-index="0"
           data-volume="1" src="media/input.mp4"></audio>
    <div class="clip" data-start="0" data-duration="{dur:.3f}" data-track-index="1"
         data-composition-src="compositions/components/caption-highlight.html"
         style="position:absolute;inset:0"></div>{matte_html}{lt_html}
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    var tl = gsap.timeline({{ paused: true }});
    var ZOOM = {zoom_js};
    var zoomTargets = [document.getElementById("main-video"),
                       document.getElementById("matte-video")].filter(Boolean);
    gsap.set(zoomTargets, {{ scale: 1 }});
    ZOOM.forEach(function (z) {{
      tl.fromTo(zoomTargets, {{ scale: 1 }}, {{ scale: z.scale, duration: Math.max(0.01, z.peak - z.start), ease: "power2.out" }}, z.start);
      tl.to(zoomTargets, {{ scale: z.scale, duration: Math.max(0.01, z.release - z.peak) }}, z.peak);
      tl.to(zoomTargets, {{ scale: 1, duration: Math.max(0.01, z.end - z.release), ease: "power2.inOut" }}, z.release);
    }});
    var LTS = {lt_js};
    var DUR = {dur:.3f};
    LTS.forEach(function (e, i) {{
      var el = "#lt-" + i;
      var t = Math.min(e.time, Math.max(0, DUR - 1.4));
      // a plate must be fully gone before the next one arrives (they share the
      // same screen position) and before the video ends
      var maxEnd = (i + 1 < LTS.length) ? LTS[i + 1].time - 0.15 : DUR - 0.05;
      var hold = Math.max(0.5, Math.min(3.5, maxEnd - t - 0.85));
      tl.fromTo(el, {{ x: -60, autoAlpha: 0 }},
                    {{ x: 0, autoAlpha: 1, duration: 0.45, ease: "power3.out" }}, t);
      tl.to(el, {{ x: -40, autoAlpha: 0, duration: 0.4, ease: "power2.in" }}, t + 0.45 + hold);
    }});
    window.__timelines["main"] = tl;
  </script>
</body>
</html>
"""
    with open(os.path.join(proj_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(host)
    with open(os.path.join(proj_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "podcut", "name": "PodCut captioned edit"}, f, indent=2)
    return proj_dir


def remove_background(video: str, out_path: str, providers: Providers,
                      quality: str = "balanced", timeout: int = 3600) -> str:
    """Extract a subject-only alpha-channel cutout via HyperFrames' real, verified
    `remove-background` command (local u2net_human_seg model; CPU/CUDA/CoreML).

    IMPORTANT (verified on this machine): the model is trained specifically on
    real people. Tested on a flat-color synthetic clip and it returned a fully
    OPAQUE frame (alpha == 255 everywhere) — i.e. it found nothing to remove. This
    only produces a meaningful cutout on footage with an actual visible person.
    CPU inference is slow (~400ms/frame measured here) — expect real runtime on a
    full clip.
    """
    out_path = os.path.abspath(out_path)
    if providers.hyperframes_path:
        cli = os.path.join(providers.hyperframes_path, "dist", "cli.js")
        cmd = ["node", cli, "remove-background", os.path.abspath(video),
               "-o", out_path, "--quality", quality, "--json"]
    else:
        cmd = ["npx", "hyperframes", "remove-background", os.path.abspath(video),
               "-o", out_path, "--quality", quality, "--json"]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    if not os.path.exists(out_path):
        raise RuntimeError("remove-background produced no output file")
    return out_path


def _probe_dims(path: str) -> tuple[int, int]:
    import json
    out = subprocess.run(
        [shutil.which("ffprobe") or "ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", path],
        check=True, capture_output=True, text=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


def _probe_dur(path: str) -> float:
    import json
    out = subprocess.run(
        [shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "json", path],
        check=True, capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])


def render_hyperframes(proj_dir: str, out_path: str, providers: Providers,
                       fps: int = 30) -> str:
    """Invoke the HyperFrames CLI to render the project to MP4. Raises if the CLI
    isn't available/fails (caller falls back to ffmpeg captions)."""
    out_path = os.path.abspath(out_path)
    if providers.hyperframes_path:
        cli = os.path.join(providers.hyperframes_path, "dist", "cli.js")
        cmd = ["node", cli, "render", ".", "-o", out_path, "-f", str(int(fps)),
               "-q", "standard", "--quiet"]
    else:
        # requires `hyperframes` installed / approved; may prompt on first use
        cmd = ["npx", "hyperframes", "render", ".", "-o", out_path, "-f", str(int(fps)),
               "-q", "standard", "--quiet"]

    # make sure ffmpeg is discoverable by the renderer
    env = dict(os.environ)
    ff = shutil.which("ffmpeg")
    if ff:
        env["PATH"] = os.path.dirname(ff) + os.pathsep + env.get("PATH", "")

    subprocess.run(cmd, check=True, cwd=proj_dir, capture_output=True, text=True, env=env)

    if os.path.exists(out_path):
        return out_path
    # fallback: locate the produced mp4
    candidates = [p for p in glob.glob(os.path.join(proj_dir, "**", "*.mp4"), recursive=True)
                  if os.path.basename(p) != "input.mp4"]
    if not candidates:
        raise RuntimeError("HyperFrames render produced no mp4")
    newest = max(candidates, key=os.path.getmtime)
    shutil.move(newest, out_path)
    return out_path


def add_captions(video: str, out_mp4: str, transcript, providers: Providers,
                 workdir: str, zoom_events=None, matte: Optional[str] = None,
                 lower_thirds=None) -> str:
    """Produce a captioned video. Uses HyperFrames if configured/available,
    otherwise the ffmpeg caption burn (which cannot do zoom, matte occlusion or
    lower-thirds — those are HyperFrames-only). Returns the path actually
    produced."""
    srt = write_srt(transcript, os.path.join(workdir, "captions.srt"))

    # Prefer HyperFrames when the user has pointed us at a checkout.
    if providers.hyperframes_path:
        try:
            proj = generate_hyperframes_project(video, transcript,
                                                os.path.join(workdir, "hyperframes_proj"),
                                                zoom_events=zoom_events, matte=matte,
                                                lower_thirds=lower_thirds)
            return render_hyperframes(proj, out_mp4, providers)
        except Exception as e:                      # noqa: BLE001
            print(f"[hyperframes] render failed ({e}); using ffmpeg caption burn "
                  f"(no zoom/matte/lower-thirds in this fallback).")

    # Always-available fallback (also generates the HF project for later use).
    try:
        generate_hyperframes_project(video, transcript,
                                     os.path.join(workdir, "hyperframes_proj"),
                                     zoom_events=zoom_events, matte=matte,
                                     lower_thirds=lower_thirds)
    except Exception:                               # noqa: BLE001
        pass
    try:
        return burn_captions_ffmpeg(video, srt, out_mp4)
    except Exception as e:                          # noqa: BLE001
        print(f"[captions] ffmpeg burn failed ({e}); returning uncaptioned clip.")
        return video


# --------------------------------------------------------------------------- #
# video-use (interactive) — stage a handoff                                   #
# --------------------------------------------------------------------------- #
def stage_for_video_use(video: str, providers: Providers, stage_dir: str) -> str:
    """video-use is interactive-only, so we can't run it inline. Stage the edited
    clip into a ready-to-drive folder and print instructions."""
    videos_dir = os.path.join(stage_dir, "videos")
    os.makedirs(videos_dir, exist_ok=True)
    shutil.copy(video, os.path.join(videos_dir, "podcut_edit.mp4"))

    if providers.elevenlabs_key:
        with open(os.path.join(videos_dir, ".env"), "w", encoding="utf-8") as f:
            f.write(f"ELEVENLABS_API_KEY={providers.elevenlabs_key}\n")

    instr = (
        "This folder is staged for video-use (browser-use/video-use).\n\n"
        "video-use is an interactive Claude Code workflow, so PodCut cannot run it\n"
        "automatically. To continue editing this clip:\n\n"
        f"  1) cd \"{videos_dir}\"\n"
        "  2) ensure video-use is installed (see its README), ELEVENLABS_API_KEY is set (.env here)\n"
        "  3) run:  claude\n"
        "  4) tell it e.g.: \"tighten this edit and add b-roll\"\n"
        "  Output will appear in ./edit/final.mp4\n"
    )
    with open(os.path.join(videos_dir, "READ_ME_FIRST.txt"), "w", encoding="utf-8") as f:
        f.write(instr)
    print("[video-use] staged edit for interactive editing:")
    print("           " + videos_dir)
    return videos_dir


# Ported from the HyperFrames registry block `caption-highlight` (hyperframes add
# caption-highlight). WORDS / RAW_GROUPS / duration are substituted with the real
# transcript by generate_hyperframes_project(). Transparent background so it
# overlays the footage as a sub-composition.
_CAPTION_BLOCK = r"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <title>Highlight</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@800&display=swap" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      *, *::before, *::after { box-sizing: border-box; }
      html, body { width: 1920px; height: 1080px; margin: 0; overflow: hidden; background: transparent; }
      #highlight { pointer-events: none; position: relative; width: 1920px; height: 1080px; overflow: hidden; background: transparent; }
      .hl-overlay { position: absolute; inset: 0; background: transparent; z-index: 1; pointer-events: none; }
      #hl-container { position: absolute; inset: 0; z-index: 10; pointer-events: none; }
      .hl-group { position: absolute; bottom: 140px; left: 0; width: 100%; display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: center; gap: 8px; padding: 0 100px; opacity: 0; visibility: hidden; }
      .hl-word { font-family: "Montserrat", sans-serif; font-weight: 800; font-size: 80px; text-transform: uppercase; color: #ffffff; display: inline-block; letter-spacing: 0.02em; line-height: 1; position: relative; padding: 6px 12px 8px; text-shadow: 0 6px 18px rgba(0,0,0,0.45); transform-origin: 50% 58%; will-change: transform, filter; }
      .hl-word-bg { position: absolute; inset: 0; background: linear-gradient(135deg, #ff1745 0%, #df1238 100%); border-radius: 10px; box-shadow: 0 12px 30px rgba(229,20,58,0.32); opacity: 0; transform: scaleX(0); transform-origin: 0% 50%; z-index: -1; }
      .hl-word-text { position: relative; z-index: 1; }
    </style>
  </head>
  <body>
    <div id="highlight" data-composition-id="caption-highlight" data-timeline-locked
         data-start="0" data-duration="__DUR__" data-fps="30" data-width="1920" data-height="1080">
      <div class="hl-overlay"></div>
      <div id="hl-container"></div>
    </div>
    <script>
      (function () {
        window.__timelines = window.__timelines || {};
        var COMP_DUR = __DUR__;
        var _fitCanvas = document.createElement("canvas");
        var _fitCtx = _fitCanvas.getContext("2d");
        function fitFontSize(text, baseFontSize, fontWeight, fontFamily, maxWidth) {
          var size = baseFontSize;
          var minSize = Math.floor(baseFontSize * 0.45);
          while (size > minSize) {
            _fitCtx.font = fontWeight + " " + size + "px " + fontFamily;
            if (_fitCtx.measureText(text).width <= maxWidth) return size;
            size -= 2;
          }
          return minSize;
        }
        var WORDS = __WORDS__;
        var RAW_GROUPS = __GROUPS__;
        var GROUPS = RAW_GROUPS.map(function (pair, gi) {
          var ws = pair[0], we = pair[1];
          var nextStart = gi + 1 < RAW_GROUPS.length ? WORDS[RAW_GROUPS[gi + 1][0]].start : COMP_DUR;
          var gEnd = Math.min(WORDS[we].end + 0.5, nextStart - 0.05);
          return { wordStart: ws, wordEnd: we, start: WORDS[ws].start, end: gEnd };
        });
        var container = document.getElementById("hl-container");
        var tl = gsap.timeline({ paused: true });
        GROUPS.forEach(function (g, gi) {
          var groupWords = WORDS.slice(g.wordStart, g.wordEnd + 1);
          var grp = document.createElement("div");
          grp.className = "hl-group";
          grp.id = "hl-grp-" + gi;
          var groupText = groupWords.map(function (w) { return w.text.toUpperCase(); }).join(" ");
          var computedSize = fitFontSize(groupText, 80, "800", "Montserrat", 1620);
          groupWords.forEach(function (w, i) {
            var wi = g.wordStart + i;
            var wordEl = document.createElement("span");
            wordEl.className = "hl-word"; wordEl.id = "hl-w-" + wi;
            wordEl.style.fontSize = computedSize + "px";
            var bgEl = document.createElement("span");
            bgEl.className = "hl-word-bg"; bgEl.id = "hl-bg-" + wi;
            var textEl = document.createElement("span");
            textEl.className = "hl-word-text";
            textEl.textContent = w.text.toUpperCase();
            wordEl.appendChild(bgEl); wordEl.appendChild(textEl); grp.appendChild(wordEl);
          });
          container.appendChild(grp);
          tl.set(grp, { visibility: "visible" }, g.start);
          tl.fromTo(grp, { opacity: 0 }, { opacity: 1, duration: 0.12, ease: "power2.out" }, g.start);
          groupWords.forEach(function (w, i) {
            var wi = g.wordStart + i;
            var bgEl = document.getElementById("hl-bg-" + wi);
            var wordEl = document.getElementById("hl-w-" + wi);
            tl.to(bgEl, { opacity: 1, scaleX: 1, duration: 0.15, ease: "power2.out" }, w.start);
            tl.to(wordEl, { filter: "brightness(1.05)", duration: 0.08, ease: "power2.out" }, w.start);
            tl.to(wordEl, { filter: "brightness(1)", duration: 0.16, ease: "power2.out" }, w.start + 0.08);
            tl.to(bgEl, { opacity: 0, scaleX: 1.02, duration: 0.1, ease: "power2.in" }, w.end);
            tl.set(bgEl, { scaleX: 0 }, w.end + 0.1);
          });
          tl.to(grp, { opacity: 0, duration: 0.1, ease: "power2.in" }, g.end - 0.1);
          tl.set(grp, { opacity: 0, visibility: "hidden" }, g.end);
        });
        tl.seek(0);
        window.__timelines["caption-highlight"] = tl;
      })();
    </script>
  </body>
</html>
"""
