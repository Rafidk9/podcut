"""Final assembly for the Migration 360 Roadshow thank-you reel: concat the
14 pre-built segments in work/ (cold open -> Gazi's message -> 5x
[hop + city block] -> payoff -> end card), lay a music bed with real
sidechain ducking under Gazi's dialogue, add a conservative Tier-1 SFX pass
(5 hop whooshes + 1 passport-stamp pop), and run the project's standard
two-pass loudnorm. Mirrors build_composite.py's concat/mix/loudnorm pattern
(same VENC/AENC, same -fps_mode cfr re-encode-once concat, same sidechain
mix) but with this reel's own segment list instead of
captioned.mp4+endcards, and its own explicit output filename.

All non-Gazi segments are silent -- they get a silent stereo track (at
Gazi's audio's own sample rate, 48000) stitched on via anullsrc before
concat, so the concat demuxer sees one consistent audio stream throughout.
Because that silent track has zero amplitude, the SAME sidechaincompress
trick build_composite.py uses (duck music against a "voice" bus) naturally
does the right thing here for free: it only ducks the bed while Gazi is
actually talking, and leaves the bed at full configured volume everywhere
else (hops/city blocks/payoff) with no separate manual volume-automation
pass needed.
"""
import json
import os
import subprocess
import sys

_THIS = os.path.abspath(__file__)
REELS_ROOT = os.path.dirname(os.path.dirname(_THIS))  # .../reels
sys.path.insert(0, REELS_ROOT)
from reel_paths import WORK, OUT, ASSETS_ROOT, X264_PRESET  # noqa: E402
from ffmpeg_util import FF, COLOR_TAGS, run, dur  # noqa: E402

# "Nonstop" (Driving/Grooving/Uplifting, 128bpm) read as calm/corporate in
# review -- swapped for "Upbeat Forever" (Bouncy/Bright, 164bpm, ska horns +
# guitar/bass/drums per incompetech's pieces.json metadata): noticeably
# brighter instrumentation and a faster tempo for a genuinely "fun and
# motivating" bed. Already in the local catalog (assets/music/CREDIT.txt
# has its CC BY 4.0 credit line) -- no new download needed.
MUSIC_TRACK = os.path.join(ASSETS_ROOT, "music", "upbeat-forever-kevin-macleod.mp3")
MUSIC_VOLUME = 0.065          # modest per project convention (~0.05-0.08)
DUCK_RATIO = 10               # project default -- aggressive, voice always wins
DUCK_THRESHOLD = 0.04

# Global colour-grade pass applied once at the final concat/re-encode step
# (not per-composition -- re-rendering all 14 HyperFrames segments would be
# expensive). Moderate saturation + contrast lift for a livelier, punchier
# look; brightness nudged up a touch to keep the lift from reading dark.
# Values kept conservative specifically so Gazi's talking-head skin tones
# don't shift orange/oversaturated -- verified against before/after stills
# (see build_final.py's run notes) before locking these in.
COLOR_GRADE = "eq=saturation=1.15:contrast=1.08:brightness=0.02"

SFX = os.path.join(ASSETS_ROOT, "sfx")
WHOOSH = os.path.join(SFX, "transition-whoosh.mp3")
POP = os.path.join(SFX, "pop.mp3")

FINAL_NAME = "migration360_roadshow_thankyou.mp4"

VENC = (["-c:v", "libx264", "-preset", X264_PRESET, "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30"]
        + COLOR_TAGS + ["-video_track_timescale", "90000"])
AENC = ["-c:a", "aac", "-ar", "48000", "-ac", "2"]

SEGMENTS = [
    ("segment_open.mp4", True),
    ("segment_gazi.mp4", False),
    ("hop_open_perth.mp4", True),
    ("segment_perth.mp4", True),
    ("hop_perth_adelaide.mp4", True),
    ("segment_adelaide.mp4", True),
    ("hop_adelaide_brisbane.mp4", True),
    ("segment_brisbane.mp4", True),
    ("hop_brisbane_melbourne.mp4", True),
    ("segment_melbourne.mp4", True),
    ("hop_melbourne_tasmania.mp4", True),
    ("segment_tasmania.mp4", True),
    ("segment_payoff.mp4", True),
    ("segment_end.mp4", True),
]


def norm_segment(src, dst, silent):
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
    if silent:
        run(["-i", src, "-f", "lavfi", "-t", f"{dur(src):.3f}", "-i",
             "anullsrc=r=48000:cl=stereo", "-vf", vf, "-map", "0:v", "-map", "1:a",
             "-shortest", *VENC, *AENC, dst])
    else:
        run(["-i", src, "-vf", vf, "-map", "0:v", "-map", "0:a?", *VENC, *AENC, dst])


def main():
    # 1) normalize every segment (silent-pad all but Gazi's) ------------------
    norm_paths = []
    for name, silent in SEGMENTS:
        src = os.path.join(WORK, name)
        if not os.path.isfile(src):
            raise SystemExit(f"missing segment: {src}")
        dst = os.path.join(WORK, "final_" + name)
        norm_segment(src, dst, silent)
        norm_paths.append((name, dst))
    print("normalized", len(norm_paths), "segments")

    # 2) build the assembled/CONTENT timeline (cumulative starts, in seconds) -
    starts = {}
    t = 0.0
    for name, dst in norm_paths:
        starts[name] = t
        t += dur(dst)
    total = t
    print("timeline starts:", json.dumps({k: round(v, 3) for k, v in starts.items()}, indent=2))

    # 3) concat with one re-encode (avoid -f concat -c copy: corrupts fps -----
    #    metadata at independently-encoded seams -- see build_composite.py)
    lst = os.path.join(WORK, "final_concat_list.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for _, dst in norm_paths:
            fh.write(f"file '{os.path.abspath(dst)}'\n")
    assembled = os.path.join(WORK, "final_assembled.mp4")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-fps_mode", "cfr", "-vf", COLOR_GRADE,
         *VENC, *AENC, assembled])
    total = dur(assembled)
    print("assembled:", assembled, f"({total:.3f}s)")

    # 4) SFX cue plan -----------------------------------------------------------
    # 5 hop whooshes, each 0.12s before the hop clip starts (whoosh peaks INTO
    # the cut rather than after it -- established convention, see
    # tushar-melbourne-expo/content.json's _sfx_note), + one passport-stamp pop
    # at the first city landing (Perth), where the stamp-landing animation
    # begins right as the hop clip cuts into segment_perth.mp4. 6 cues total --
    # comfortably under the ~8-cue true-peak budget documented for this project.
    cues = []
    for hop_name in ("hop_open_perth.mp4", "hop_perth_adelaide.mp4",
                      "hop_adelaide_brisbane.mp4", "hop_brisbane_melbourne.mp4",
                      "hop_melbourne_tasmania.mp4"):
        cues.append({"file": WHOOSH, "at": max(0.0, starts[hop_name] - 0.12), "volume": 0.20})
    cues.append({"file": POP, "at": starts["segment_perth.mp4"], "volume": 0.30})
    print("sfx cues:", json.dumps(
        [{"file": os.path.basename(c["file"]), "at": round(c["at"], 3), "volume": c["volume"]}
         for c in cues], indent=2))

    # 5) music + sfx mix with sidechain ducking ----------------------------------
    mixed = os.path.join(WORK, "final_mixed.mp4")
    fade_out_st = max(0.0, total - 2.4)

    sfx_in = []
    for c in cues:
        sfx_in += ["-i", c["file"]]
    sfx_filters = []
    for i, c in enumerate(cues):
        idx = 2 + i  # 0=assembled, 1=music, 2..=sfx
        delay_ms = round(c["at"] * 1000)
        sfx_filters.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume={c['volume']}[sfx{i}]")
    sfx_filters.append(
        "".join(f"[sfx{i}]" for i in range(len(cues)))
        + f"amix=inputs={len(cues)}:duration=longest:normalize=0[sfxbus]")
    final_mix = "[voice2][mduck][sfxbus]amix=inputs=3:duration=first:normalize=0[a]"

    filter_complex = (
        f"[1:a]atrim=0:{total:.3f},volume={MUSIC_VOLUME},afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={fade_out_st:.3f}:d=2.4[m];"
        f"[0:a]asplit=2[voice1][voice2];"
        f"[m][voice1]sidechaincompress=threshold={DUCK_THRESHOLD}:ratio={DUCK_RATIO}:"
        f"attack=40:release=450:makeup=1[mduck];"
        + "".join(f + ";" for f in sfx_filters) + final_mix)

    run(["-i", assembled, "-stream_loop", "-1", "-i", MUSIC_TRACK, *sfx_in,
         "-filter_complex", filter_complex,
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", *AENC, mixed])
    print("mixed:", mixed)

    # 6) two-pass loudnorm to -14 LUFS / -1 dBTP, with limiter safety net -------
    ln = "loudnorm=I=-14:TP=-1:LRA=11"
    os.makedirs(OUT, exist_ok=True)
    final = os.path.join(OUT, FINAL_NAME)
    p1 = subprocess.run([FF, "-hide_banner", "-i", mixed, "-af", ln + ":print_format=json",
                         "-f", "null", "-"], capture_output=True, text=True)
    txt = p1.stderr
    js = json.loads(txt[txt.rfind("{"): txt.rfind("}") + 1])
    run(["-i", mixed, "-af",
         f"{ln}:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
         f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:"
         f"offset={js['target_offset']}:linear=true,"
         "alimiter=limit=0.79:level=disabled",
         "-c:v", "copy", *AENC, final])
    print("FINAL REEL:", final, f"({total:.2f}s)")


if __name__ == "__main__":
    main()
