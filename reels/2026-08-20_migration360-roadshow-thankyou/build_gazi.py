"""Opening "Gazi's message" segment for the Migration 360 Roadshow thank-you
reel: P1-P5.MOV are one continuous walk-and-talk through a single venue
(confirmed by eyeballing extracted frames -- same outfit/lav mic, natural
continuous gesturing across 5 spots in the same building), split across 5
files. Each of P2-P5 opens with an off-camera "three, two, one, go" verbal
slate cue (visible in the transcripts, diarized as speaker "A" there) before
Gazi (speaker "B") resumes speaking -- that's a sync cue for the file
restart, not a separate take; it's trimmed off each clip's head here so the
final cut reads as one clean, continuous message.

2026-08-23 retrim: the first pass (trim_in chosen a fixed ~1.9-3.8s per clip)
left 300-680ms of dead air + a splice "click" between the slate's last word
ending and Gazi's own first word starting, per clip -- audible on playback
as a residual "...go" bleeding right up to where he starts talking. Every
trim_in below is now pinned to each clip's transcript word-level timestamps
(work/gazi_P*.transcript.json, ElevenLabs scribe_v1, word-accurate): exactly
0.12s before the FIRST WORD TIME-WISE >= that clip's own diarized "Gazi"
speaker actually starts (found by inspecting each transcript by hand, not
assumed from the speaker label alone -- P1 has no second speaker at all, so
its one voice is diarized "A" there, unlike P2-P5 where "A" is the off-camera
slate caller and "B" is Gazi). P1 -- previously kept in full on the theory it
"carries no slate" -- turned out to still have ~2.2s of quiet pre-roll ahead
of his first word ("What"); a showspectrumpic look at its head shows a couple
of faint low-level transients in there too (most likely ambient/room noise,
not a second on-mic voice, but nothing that belongs in the final cut either),
so it now gets the same tight, transcript-pinned trim as every other clip.
Each _segment() encode also gets a 20ms in/out audio fade to kill the
sample-discontinuity "click" a hard concat cut otherwise leaves at every
join (confirmed present at all 4 internal cuts via showspectrumpic on the
prior render -- a vertical full-spectrum spike at each splice point).
P5's tail (~1.8s of silence after his last word) is also trimmed so the
message ends cleanly on "...migration journey." rather than holding on dead
air.

Source is 10-bit HEVC/HLG/BT.2020 (Dolby Vision profile 8) phone footage
with a -90 deg Display Matrix rotation (ffprobe's raw stream reads land-
scape 3840x2160; frames are actually portrait once the matrix is applied,
which ffmpeg does automatically) -- reuses engine/podcut/render.py's tested
hdr_to_sdr_vf() tonemap chain so colour doesn't come out flat/desaturated.

Architecture mirrors build_captions.py's LOOK (2-word UPPERCASE Poppins-800
caption chunks, gold-keyword pulse, back.out overshoot entrance, same
#cap/.card/.w CSS) but NOT its per-card sub-composition/caching machinery --
this is a one-off 25s segment, not the whole reel, so both the lower-third
name card and every caption chunk just live as siblings on ONE shared GSAP
timeline in ONE transparent HyperFrames render, composited onto the
concatenated/tonemapped footage in a single ffmpeg pass.

Renders WORK/segment_gazi.mp4 (1080x1920/30fps, h264 yuv420p bt709, aac
audio) and WORK/segment_gazi_still.png (frame grab at t=3s).
"""
import base64
import json
import os
import shutil
import subprocess
import sys

_THIS = os.path.abspath(__file__)
sys.path.insert(0, os.path.dirname(os.path.dirname(_THIS)))  # reels/

from reel_paths import WORK, PODCUT_ROOT, REEL, HF_QUALITY, HF_FPS, hyperframes_cli  # noqa: E402
from ffmpeg_util import FF, FFPROBE, COLOR_TAGS, run, dur  # noqa: E402

sys.path.insert(0, os.path.join(PODCUT_ROOT, "engine"))
from podcut.render import hdr_to_sdr_vf, SDR_TAG_VF, SDR_COLOR_ARGS  # noqa: E402
from podcut import ffutil  # noqa: E402

IN_GAZI = os.path.join(REEL, "input", "gazi")
W, H, FPS = 1080, 1920, 30
AFADE = 0.02  # 20ms in/out audio fade per segment -- kills the splice click at every concat join

# (filename, trim_in seconds, trim_out seconds or None = full clip duration)
# trim_in is pinned to 0.12s before each clip's first Gazi-spoken word (per
# its transcript's word-level timestamps -- see module docstring for the
# 2026-08-23 retrim rationale): P1 "What" @2.20 (transcript's only speaker,
# diarized "A"), P2 "Our" @2.20, P3 "These" @3.339, P4 "It's" @3.48,
# P5 "I" @4.179 (all speaker "B" there). P5's trim_out stops the message
# right after "...migration journey" instead of riding out ~1.8s of silent
# dead air to the clip's actual end.
CLIPS = [
    ("P1.MOV", 2.08, None),
    ("P2.MOV", 2.08, None),
    ("P3.MOV", 3.22, None),
    ("P4.MOV", 3.36, None),
    ("P5.MOV", 4.06, 9.0),
]

NAME = "Gazi Tanvir Hossain"
ROLE = "General Manager (Australia)"
INK = "#100796"
# lower-third on-screen window on the OUTPUT (post-trim) timeline: appears a
# couple seconds in, holds ~4.5s fully readable, then fades over ~0.4s. Sits
# in the bottom-left dock (top:1490px of a 1920px frame) -- well clear of the
# caption band anchored at cap_top (62% -> ~1190px center), so the two never
# collide; no suppression logic needed between them.
LT_START = 2.0
LT_FADE_START = 6.5
LT_END = 6.9
CAP_TOP = "62%"

# Caption look, lifted from build_captions.py's DEFAULT_CONTENT/asr_fix so
# this segment's captions read as the same house style (see that file's
# docstring: "2-word UPPERCASE Poppins Bold chunks with real kinetic motion
# (back-ease overshoot entrance, gold-keyword pulse)"). Trimmed to just the
# fixes/keywords this segment's own transcript actually needs rather than
# importing its whole content.json-driven machinery.
ASR_FIX = {"pfc": "PFEC"}
GOLD = {"MIGRATION", "PFEC", "360", "ROADSHOW"}
FILLERS = {"um", "uh", "erm", "er", "ah", "hmm", "mm", "mm-hmm", "mmhmm", "uh-huh"}
SENTENCE_END = (".", "?", "!")


def _norm(t):
    return t.strip().strip(".,!?;:'\"").lower()


def _segment(idx, fname, trim_in, trim_out):
    src = os.path.join(IN_GAZI, fname)
    color = ffutil.probe_color(src)
    is_hdr = ffutil.is_hdr(src)
    total = dur(src)
    t_out = trim_out if trim_out is not None else total
    seg_dur = t_out - trim_in
    assert seg_dur > 0, f"{fname}: bad trim ({trim_in} -> {t_out})"

    vf_parts = []
    if is_hdr:
        vf_parts.append(hdr_to_sdr_vf(color))
    vf_parts.append(f"scale={W}:{H}:force_original_aspect_ratio=decrease")
    vf_parts.append(f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2")
    vf_parts.append("setsar=1")
    vf_parts.append(f"fps={FPS}")
    vf_parts.append(SDR_TAG_VF)
    vf = ",".join(vf_parts)
    # 20ms in/out fade so the hard trim + concat join never leaves a raw
    # sample-value discontinuity (audible as a "click"/"pop" right at the cut).
    af = f"afade=t=in:st=0:d={AFADE},afade=t=out:st={max(0.0, seg_dur - AFADE):.3f}:d={AFADE}"

    seg_out = os.path.join(WORK, f"gazi_seg_{idx:02d}.mp4")
    run(["-ss", f"{trim_in:.3f}", "-i", src, "-t", f"{seg_dur:.3f}",
         "-map", "0:v:0", "-map", "0:a:0",
         "-vf", vf, "-af", af,
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         *COLOR_TAGS,
         "-c:a", "aac", "-ar", "48000", "-ac", "2",
         "-video_track_timescale", "90000", seg_out],
        label=f"gazi seg {idx} ({fname})")
    print(f"  seg {idx} {fname}: hdr={is_hdr} trim {trim_in:.2f}-{t_out:.2f} -> {seg_dur:.2f}s")
    return seg_out, seg_dur


# 2026-08-25 transition pass: replaced the 4 internal hard jump cuts (P1|P2,
# P2|P3, P3|P4, P4|P5) with a soft cross-dissolve -- Gazi is walking through
# different spots in ONE continuous venue/take, so a straight jump cut reads
# like a scene change; a brief dissolve reads as "he walked to another spot"
# instead. Picked over reels/build_wipe.py's brand grid-pixelate/speed-panel/
# flash overlays (this project's existing B-ROLL cut style) because those are
# opaque full-frame flourishes meant to hide a cut between DIFFERENT footage;
# here the same person keeps talking through the join, so a wipe that fully
# blanks the frame would read as a harder interruption than the plain jump
# cut it's replacing. Also skipped a simulated whip-pan (directional motion
# blur) -- these are static, unmoving shots, so faking camera-swish blur with
# no underlying pan motion would look like an artifact, not a natural beat.
#
# Verified safe against garbling speech before picking the duration: every
# one of P1-P4's transcripts (work/gazi_P*.transcript.json) has Gazi's last
# word ending well before that source clip's physical end -- 0.38s (P1),
# 0.44s (P2), 0.43s (P3), 0.84s (P4) of trailing room-tone/silence -- and
# each next clip's trim_in already starts 0.12s of pre-roll silence ahead of
# its own first word (see CLIPS comment above). TRANSITION_DUR=0.2s fits
# entirely inside every one of those tail buffers, so the crossfade blends
# outgoing silence into incoming silence/word-onset -- never two overlapping
# voices.
#
# ffmpeg's xfade (video) + acrossfade (audio) both work by OVERLAPPING the
# last TRANSITION_DUR seconds of clip i with the first TRANSITION_DUR seconds
# of clip i+1 into one shorter blended window rather than inserting extra
# frames -- so each transition shortens the running total by TRANSITION_DUR,
# and clip i+1's own local time 0 lands at (merged-duration-so-far -
# TRANSITION_DUR) on the OUTPUT timeline. build_base() computes each
# segment's output offset with that formula (instead of the old plain
# cumulative sum), and that same number IS the xfade "offset" parameter for
# the transition that creates it -- so build_captions_data()'s word timings
# and the lower third land in the right place on the new, slightly shorter
# timeline, from the same numbers that actually drove the encode.
TRANSITION_DUR = 0.2
XFADE_STYLE = "fade"  # plain alpha cross-dissolve ("dissolve" is a noisy pixel-stipple look instead)


def build_base():
    """Trim + tonemap + cross-dissolve P1-P5 into one 1080x1920/30fps clip
    with audio. Returns (base_path, total_duration, seg_info) where seg_info
    is a list of (fname, trim_in, trim_out_eff, seg_dur, output_offset) --
    reused by build_captions_data() so the caption timeline is derived from
    the exact same (transition-shortened) numbers that produced the encode,
    instead of recomputed by hand."""
    seg_files, seg_durs, seg_info = [], [], []
    for i, (fname, trim_in, trim_out) in enumerate(CLIPS):
        seg_out, seg_dur = _segment(i, fname, trim_in, trim_out)
        seg_files.append(seg_out)
        seg_durs.append(seg_dur)
        src = os.path.join(IN_GAZI, fname)
        trim_out_eff = trim_out if trim_out is not None else dur(src)
        seg_info.append([fname, trim_in, trim_out_eff, seg_dur, 0.0])  # offset filled in below

    n = len(seg_files)
    running = 0.0
    for i in range(n):
        seg_info[i][4] = round(running, 3)
        running += seg_durs[i]
        if i < n - 1:
            running -= TRANSITION_DUR
    seg_info = [tuple(s) for s in seg_info]

    # Chain xfade (video) and acrossfade (audio) across all 5 inputs so
    # picture and sound shorten by the exact same amount at every join and
    # stay in sync end to end. Each xfade's "offset" (the position within the
    # already-merged previous input where the transition starts) is exactly
    # seg_info[i][4] -- see the derivation in the comment above.
    v_filters, a_filters = [], []
    prev_v, prev_a = "0:v", "0:a"
    for i in range(1, n):
        v_out = f"v{i}" if i < n - 1 else "vout"
        a_out = f"a{i}" if i < n - 1 else "aout"
        offset = seg_info[i][4]
        v_filters.append(f"[{prev_v}][{i}:v]xfade=transition={XFADE_STYLE}:"
                          f"duration={TRANSITION_DUR}:offset={offset:.3f}[{v_out}]")
        a_filters.append(f"[{prev_a}][{i}:a]acrossfade=d={TRANSITION_DUR}:c1=tri:c2=tri[{a_out}]")
        prev_v, prev_a = v_out, a_out
    filter_complex = ";".join(v_filters + a_filters)

    base = os.path.join(WORK, "segment_gazi_base.mp4")
    input_args = []
    for s in seg_files:
        input_args += ["-i", s]
    run(input_args + ["-filter_complex", filter_complex,
                       "-map", "[vout]", "-map", "[aout]",
                       "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                       *COLOR_TAGS,
                       "-c:a", "aac", "-ar", "48000", "-ac", "2",
                       "-video_track_timescale", "90000", base],
        label="gazi crossfade concat")
    actual = dur(base)
    print(f"base: {actual:.2f}s ({n - 1} x {TRANSITION_DUR:.2f}s cross-dissolves, "
          f"segments summed to {sum(seg_durs):.2f}s), -> {base}")
    return base, actual, seg_info


# ------------------------------------------------------------- captions data

def build_captions_data(seg_info, total_dur):
    """Gazi's word-level speech timed onto the OUTPUT (post-trim, concatenated)
    timeline, chunked into 2-word caption cards the same way build_captions.py
    does (pair words unless the first ends a sentence), plus one extra rule
    specific to this multi-clip segment: never pair across a clip join --
    P3's last word and P4's first word are ~0.5s apart across a real splice,
    not a same-breath pair, so treating that boundary like a forced sentence
    end keeps a caption from showing a word before it's actually said."""
    words = []
    for si, (fname, trim_in, trim_out_eff, seg_dur, off) in enumerate(seg_info):
        stem = os.path.splitext(fname)[0]
        data = json.load(open(os.path.join(WORK, f"gazi_{stem}.transcript.json"),
                               encoding="utf-8"))
        for w in data["words"]:
            if w["start"] < trim_in - 1e-6 or w["start"] >= trim_out_eff + 1e-6:
                continue  # off-camera slate word (trimmed head) or past the kept tail
            n = _norm(w["text"])
            if n in FILLERS:
                continue
            text = w["text"]
            if n in ASR_FIX:
                trail = text[len(text.rstrip(".,!?;:")):]
                text = ASR_FIX[n] + trail
            words.append({"text": text,
                          "start": round(w["start"] - trim_in + off, 3),
                          "end": round(w["end"] - trim_in + off, 3),
                          "seg": si})

    chunks, i = [], 0
    while i < len(words):
        w = words[i]
        last_in_seg = (i + 1 >= len(words)) or (words[i + 1]["seg"] != w["seg"])
        if w["text"].strip().endswith(SENTENCE_END) or last_in_seg:
            chunks.append([w]); i += 1
        else:
            chunks.append([w, words[i + 1]]); i += 2

    cards = []
    for k, g in enumerate(chunks):
        start = g[0]["start"]
        end = chunks[k + 1][0]["start"] if k + 1 < len(chunks) else g[-1]["end"] + 0.4
        end = min(round(max(start + 0.2, end), 3), round(total_dur, 3))
        spans = [{"text": w["text"].strip().upper(), "gold": _norm(w["text"]).upper() in GOLD}
                 for w in g]
        cards.append({"start": round(start, 3), "end": end, "words": spans})
    print(f"captions: {len(cards)} 2-word chunks, {cards[0]['start']:.2f}s -> "
          f"{cards[-1]['end']:.2f}s")
    return cards


# -------------------------------------------------------- overlay (LT + captions)

_HTML = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1080px;height:1920px;overflow:hidden;background:transparent}
  #introCard{position:absolute;left:44px;top:1490px;opacity:0;visibility:hidden;
     display:inline-flex;align-items:flex-start;border-radius:16px;overflow:hidden;
     box-shadow:0 16px 40px rgba(0,0,0,.5)}
  #introCard .rule{flex:none;width:10px;align-self:stretch;background:#FFC500}
  #introCard .info-panel{display:flex;flex-direction:column;justify-content:center;
     background:linear-gradient(100deg,__INK__ 0%,#1A10C0 100%);
     padding:22px 40px 24px 30px}
  #introCard .nm{font-family:"Poppins",sans-serif;font-weight:800;font-size:44px;color:#fff;
     letter-spacing:.005em;line-height:1.14;white-space:nowrap}
  #introCard .role{font-family:"Poppins",sans-serif;font-weight:700;font-size:25px;color:#FFC500;
     letter-spacing:.03em;margin-top:6px;white-space:nowrap}

  /* Caption band -- same look as build_captions.py's #cap/.card/.w: 2-word
     UPPERCASE Poppins-800 chunks, white with brand-gold keyword highlight,
     drop-shadowed for legibility over live footage. Anchored at CAP_TOP
     (62%), well clear of the lower-third dock above. */
  #cap{position:absolute;left:0;right:0;top:__CAP_TOP__;transform:translateY(-50%);text-align:center}
  .card{position:absolute;left:0;right:0;top:0;padding:0 70px;opacity:0;visibility:hidden}
  .w{font-family:"Poppins",sans-serif;font-weight:800;font-size:96px;line-height:1.05;color:#fff;
     letter-spacing:.01em;text-shadow:0 6px 22px rgba(0,0,0,.75),0 2px 4px rgba(0,0,0,.95);
     display:inline-block;margin:0 26px}
  .w.gold{color:#FFC500}
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="__DUR__" data-fps="__FPS__" data-width="1080" data-height="1920">
  <div id="introCard">
    <div class="rule"></div>
    <div class="info-panel">
      <div class="nm">__NAME__</div>
      <div class="role">__ROLE__</div>
    </div>
  </div>
  <div id="cap">
__CAP_CARDS_DOM__
  </div>
</div>
<script>
(function(){
  window.__timelines=window.__timelines||{};
  var tl=gsap.timeline({paused:true});
  var ic=document.getElementById("introCard");
  var NS=__NS__, FS=__FS__, NE=__NE__;
  tl.set(ic,{visibility:"visible"}, NS);
  tl.fromTo(ic, {opacity:0, x:-56}, {opacity:1, x:0, duration:0.34, ease:"back.out(1.8)"}, NS);
  tl.to(ic, {opacity:0, x:-36, duration:0.4, ease:"power2.in"}, FS);
  tl.set(ic,{visibility:"hidden"}, NE);
__CAP_CARDS_JS__
  tl.seek(0);
  window.__timelines["main"]=tl;
})();
</script></body></html>
"""

_CARD_JS = """
  (function(){
    var el = document.getElementById("__ID__");
    var S = __S__, E = __E__;
    tl.set(el, {visibility:"visible"}, S);
    tl.fromTo(el,
      {opacity:0, y:34, scale:0.78, rotation:-3},
      {opacity:1, y:0, scale:1, rotation:0, duration:0.22, ease:"back.out(2.2)"},
      S);
    var goldEls = el.querySelectorAll(".gold");
    if (goldEls.length && (E - S) > 0.3) {
      tl.fromTo(goldEls, {scale:1}, {scale:1.08, duration:0.1, ease:"power2.out"}, S + 0.16);
      tl.to(goldEls, {scale:1, duration:0.16, ease:"power2.inOut"}, S + 0.26);
    }
    tl.to(el, {opacity:0, scale:0.92, duration:0.08, ease:"power1.in"}, Math.max(S + 0.12, E - 0.08));
    tl.set(el, {visibility:"hidden"}, E);
  })();
"""


def build_overlay(total_dur, cards):
    proj = os.path.join(WORK, "gazi_lt_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)

    cap_dom, cap_js = [], []
    for i, c in enumerate(cards):
        el_id = f"cap{i:03d}"
        words_html = " ".join(
            '<span class="w' + (' gold' if w["gold"] else '') + '">' + w["text"] + '</span>'
            for w in c["words"])
        cap_dom.append(f'    <div class="card" id="{el_id}">{words_html}</div>')
        cap_js.append(_CARD_JS.replace("__ID__", el_id)
                               .replace("__S__", f"{c['start']:.3f}")
                               .replace("__E__", f"{c['end']:.3f}"))

    html = (_HTML.replace("__DUR__", f"{total_dur:.3f}")
                 .replace("__FPS__", str(HF_FPS))
                 .replace("__INK__", INK)
                 .replace("__NAME__", NAME)
                 .replace("__ROLE__", ROLE)
                 .replace("__NS__", f"{LT_START:.3f}")
                 .replace("__FS__", f"{LT_FADE_START:.3f}")
                 .replace("__NE__", f"{LT_END:.3f}")
                 .replace("__CAP_TOP__", CAP_TOP)
                 .replace("__CAP_CARDS_DOM__", "\n".join(cap_dom))
                 .replace("__CAP_CARDS_JS__", "\n".join(cap_js)))
    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    json.dump({"id": "gazi-lower-third", "name": "Gazi Tanvir Hossain lower third + captions"},
              open(os.path.join(proj, "meta.json"), "w"))

    overlay = os.path.join(WORK, "gazi_lt.webm")
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(overlay),
                    "-f", str(HF_FPS), "--format", "webm", "-q", HF_QUALITY, "--quiet"],
                   cwd=proj, check=True, env=env)
    print("overlay (lower third + captions) rendered:", overlay)
    return overlay


def composite(base, overlay, total_dur):
    out = os.path.join(WORK, "segment_gazi.mp4")
    # force libvpx-vp9 decode -- ffmpeg's default vp9 decoder drops the alpha
    # plane and would paint opaque black over the footage (same note as
    # build_captions.py).
    run(["-i", base, "-c:v", "libvpx-vp9", "-i", overlay,
         "-filter_complex", "[1:v]format=yuva420p[ov];[0:v][ov]overlay=0:0:format=auto[vout]",
         "-map", "[vout]", "-map", "0:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", *COLOR_TAGS,
         "-c:a", "aac", "-ar", "48000", "-ac", "2",
         "-video_track_timescale", "90000", out], label="gazi composite")
    print("segment ready:", out)
    return out


def grab_still(video, t=3.0, out_name="segment_gazi_still.png"):
    still = os.path.join(WORK, out_name)
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                     "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", still], check=True)
    print("still:", still)
    return still


def transition_midpoints(seg_info):
    """Output-timeline time (seconds) at the middle of each of the 4 internal
    cross-dissolves, derived from seg_info's own offsets -- each segment i
    (i>=1)'s offset IS the point its transition starts (see build_base()'s
    derivation comment), so the midpoint is just offset + TRANSITION_DUR/2."""
    return [round(seg_info[i][4] + TRANSITION_DUR / 2, 3) for i in range(1, len(seg_info))]


def main():
    base, total, seg_info = build_base()
    cards = build_captions_data(seg_info, total)
    overlay = build_overlay(total, cards)
    out = composite(base, overlay, total)
    grab_still(out, t=3.0)
    for i, t in enumerate(transition_midpoints(seg_info), start=1):
        grab_still(out, t=t, out_name=f"segment_gazi_transition{i}.png")
    print(f"\nfinal duration: {dur(out):.2f}s")


if __name__ == "__main__":
    main()
