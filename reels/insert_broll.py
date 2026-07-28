"""Insert 4 DISTINCT, topical B-roll cutaways into base.mp4 at the transition
boundaries, each masked by a quick on-brand grid-wipe transition (adapted from
HyperFrames' registry `grid-pixelate-wipe`) instead of a flat instant cut.
Original audio stays fully continuous throughout (B-roll replaces video only)."""
import os, json, shutil

from reel_paths import WORK, REEL, X264_PRESET  # noqa: E402 -- per-reel folders
from ffmpeg_util import COLOR_TAGS, run  # noqa: E402 -- shared ffmpeg wrappers
WIPE_DUR = 0.5


def load_plan():
    """Per-reel B-roll placement: <reel>/broll_plan.json = {"n_segments": N,
    "broll_dur": D, "plan": {"<seg idx>": "<stinger name>"},
    "boundaries": {"<seg idx>": <absolute time>},
    "extra_wipes": [{"at": <absolute time>, "style": "grid"|"speed"|"flash"}, ...]}.

    "extra_wipes" (optional, default []) masks a PLAIN hard cut (segment
    boundary with no B-roll splice -- "boundaries" only ever covers indices
    that appear in "plan") with a wipe transition of its own. "style" picks
    which of build_wipe.py's rendered variants to use (default "grid" if
    omitted) -- mix styles across a reel's cuts for visual variety rather
    than reusing one flavour everywhere.

    Required per reel -- deliberately NO cross-reel fallback. An earlier
    version silently reused a previous reel's fixed 4-stinger placement (at
    THAT reel's own boundary timestamps) whenever this file was missing --
    which is wrong content at wrong timestamps with no error, not a safe
    default (see build_broll.py's load_stingers() docstring for the same
    reasoning). If a reel genuinely has no B-roll, write broll_plan.json
    with "plan": {} and "boundaries": {} rather than omitting the file."""
    cfg = os.path.join(REEL, "broll_plan.json")
    if not os.path.isfile(cfg):
        raise SystemExit(
            f"{cfg} not found. Every reel needs its own broll_plan.json -- "
            "derive placement from THIS reel's transcript (see the docstrings "
            "in build_broll.py / insert_broll.py), or write one with "
            '"plan": {} and "boundaries": {} if this reel genuinely has no '
            "B-roll. There is no cross-reel default.")
    j = json.load(open(cfg, encoding="utf-8"))
    plan = {int(k): v for k, v in j["plan"].items()}
    boundaries = {int(k): float(v) for k, v in j["boundaries"].items()}
    extra_wipes = [(float(w["at"]), w.get("style", "grid")) for w in j.get("extra_wipes", [])]
    return plan, boundaries, int(j["n_segments"]), float(j.get("broll_dur", 1.3)), extra_wipes


PLAN, BOUNDARIES, N_SEGMENTS, BROLL_DUR, EXTRA_WIPES = load_plan()

VF = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"


def splice_broll_into_segment(seg_path, broll_path, out_path):
    """out video = broll[0:BROLL_DUR] + seg_video[BROLL_DUR:end]; out audio =
    seg's ORIGINAL audio, full duration, untouched."""
    run([
        "-i", broll_path, "-i", seg_path,
        "-filter_complex",
        f"[0:v]{VF},trim=0:{BROLL_DUR},setpts=PTS-STARTPTS[b];"
        f"[1:v]{VF},trim=start={BROLL_DUR},setpts=PTS-STARTPTS[rest];"
        f"[b][rest]concat=n=2:v=1:a=0[vout]",
        "-map", "[vout]", "-map", "1:a",
        "-c:v", "libx264", "-preset", X264_PRESET, "-crf", "18", "-pix_fmt", "yuv420p",
        *COLOR_TAGS,
        "-r", "30", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-video_track_timescale", "90000", out_path,
    ])


def overlay_wipes(video_in, video_out, wipe_specs):
    """Mask each hard cut with a wipe transition: peak coverage lands exactly
    on the cut time, so the swap happens invisibly under full coverage.
    wipe_specs: [(time, wipe_filename), ...] -- wipe_filename resolves under
    WORK (e.g. "wipe.webm", "wipe_speed.webm", "wipe_flash.webm" -- see
    build_wipe.py), so different cuts can use different transition styles."""
    half = WIPE_DUR / 2
    cmd = ["-i", video_in]
    for t, wipe_file in wipe_specs:
        start = max(0.0, t - half)
        cmd += ["-itsoffset", f"{start:.3f}", "-c:v", "libvpx-vp9",
                "-i", os.path.join(WORK, wipe_file)]

    filt = []
    prev = "0:v"
    for i, (t, wipe_file) in enumerate(wipe_specs):
        idx = i + 1
        start = max(0.0, t - half)
        end = start + WIPE_DUR
        filt.append(f"[{idx}:v]format=yuva420p[w{idx}]")
        nxt = f"v{idx}"
        filt.append(f"[{prev}][w{idx}]overlay=0:0:format=auto:"
                    f"enable='between(t,{start:.3f},{end:.3f})'[{nxt}]")
        prev = nxt

    args = cmd + ["-filter_complex", ";".join(filt), "-map", f"[{prev}]", "-map", "0:a",
                  "-c:v", "libx264", "-preset", X264_PRESET, "-crf", "18", "-pix_fmt", "yuv420p",
                  *COLOR_TAGS,
                  "-c:a", "copy", "-video_track_timescale", "90000", video_out]
    run(args)


def main():
    seg_dir = os.path.join(WORK, "segments")
    new_list = []
    for i in range(N_SEGMENTS):
        seg = os.path.join(seg_dir, f"seg_{i:02d}.mp4")
        if i in PLAN:
            broll = os.path.join(WORK, PLAN[i] + ".mp4")
            out = os.path.join(seg_dir, f"seg_{i:02d}_broll.mp4")
            splice_broll_into_segment(seg, broll, out)
            new_list.append(out)
            print(f"seg_{i:02d}: {PLAN[i]} spliced in, audio untouched")
        else:
            new_list.append(seg)

    lst = os.path.join(seg_dir, "concat_broll.txt")
    open(lst, "w").write("\n".join(f"file '{os.path.abspath(s)}'" for s in new_list) + "\n")
    raw = os.path.join(WORK, "base_broll_raw.mp4")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", raw])

    out = os.path.join(WORK, "base_broll.mp4")
    def _wipe_file(style):
        return "wipe.webm" if style == "grid" else f"wipe_{style}.webm"
    wipe_specs = sorted(
        [(t, "wipe.webm") for t in BOUNDARIES.values()] +
        [(t, _wipe_file(style)) for t, style in EXTRA_WIPES],
        key=lambda p: p[0])
    if wipe_specs:
        overlay_wipes(raw, out, wipe_specs)
        print("wrote", out, f"(with {len(wipe_specs)} wipe transition(s) masking each cut)")
    else:
        shutil.copy2(raw, out)
        print("wrote", out, "(no B-roll cuts or extra wipes for this reel -- straight concat)")


if __name__ == "__main__":
    main()
