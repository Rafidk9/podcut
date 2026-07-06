"""Insert 4 DISTINCT, topical B-roll cutaways into base.mp4 at the transition
boundaries, each masked by a quick on-brand grid-wipe transition (adapted from
HyperFrames' registry `grid-pixelate-wipe`) instead of a flat instant cut.
Original audio stays fully continuous throughout (B-roll replaces video only)."""
import os, json, shutil, subprocess

from reel_paths import WORK, REEL  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"
WIPE_DUR = 0.5

# Legacy Lakemba defaults (kept so that reel builds unchanged with no config).
# segment index -> which topical broll stinger plays there; each ties to the
# moment it cuts away from/into (see build_broll.py for the content design).
_DEFAULT_PLAN = {1: "broll_1", 3: "broll_2", 4: "broll_3", 5: "broll_4"}
# absolute boundary time (on the base/base_broll timeline) for each -- these
# are exactly where each chosen segment starts, i.e. the cut point.
_DEFAULT_BOUNDARIES = {1: 8.19, 3: 19.13, 4: 25.88, 5: 28.71}
_DEFAULT_N_SEGMENTS = 9
_DEFAULT_BROLL_DUR = 1.3


def load_plan():
    """Per-reel B-roll placement: <reel>/broll_plan.json = {"n_segments": N,
    "broll_dur": D, "plan": {"<seg idx>": "<stinger name>"},
    "boundaries": {"<seg idx>": <absolute time>}}. Falls back to the legacy
    Lakemba constants if the reel has no override."""
    cfg = os.path.join(REEL, "broll_plan.json")
    if os.path.isfile(cfg):
        j = json.load(open(cfg, encoding="utf-8"))
        plan = {int(k): v for k, v in j["plan"].items()}
        boundaries = {int(k): float(v) for k, v in j["boundaries"].items()}
        return plan, boundaries, int(j["n_segments"]), float(j.get("broll_dur", 1.3))
    return _DEFAULT_PLAN, _DEFAULT_BOUNDARIES, _DEFAULT_N_SEGMENTS, _DEFAULT_BROLL_DUR


PLAN, BOUNDARIES, N_SEGMENTS, BROLL_DUR = load_plan()

VF = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
# Force correct SDR tags on every re-encode in this file too -- seg_XX.mp4
# inputs are already correctly BT.709-tagged (fixed in build_base.py), but any
# encode step needs these explicit or the muxed output can end up untagged/
# ambiguous again.
COLOR_TAGS = ["-color_primaries", "bt709", "-color_trc", "bt709",
             "-colorspace", "bt709", "-color_range", "tv"]


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


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
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        *COLOR_TAGS,
        "-r", "30", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-video_track_timescale", "90000", out_path,
    ])


def overlay_wipes(video_in, video_out, boundaries):
    """Mask each hard cut with the brand grid-wipe: peak coverage lands exactly
    on the boundary, so the swap happens invisibly under full-navy coverage."""
    wipe = os.path.join(WORK, "wipe.webm")
    half = WIPE_DUR / 2
    cmd = ["-i", video_in]
    for b in boundaries:
        start = max(0.0, b - half)
        cmd += ["-itsoffset", f"{start:.3f}", "-c:v", "libvpx-vp9", "-i", wipe]

    filt = []
    prev = "0:v"
    for i, b in enumerate(boundaries):
        idx = i + 1
        start = max(0.0, b - half)
        end = start + WIPE_DUR
        filt.append(f"[{idx}:v]format=yuva420p[w{idx}]")
        nxt = f"v{idx}"
        filt.append(f"[{prev}][w{idx}]overlay=0:0:format=auto:"
                    f"enable='between(t,{start:.3f},{end:.3f})'[{nxt}]")
        prev = nxt

    args = cmd + ["-filter_complex", ";".join(filt), "-map", f"[{prev}]", "-map", "0:a",
                  "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
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
    if BOUNDARIES:
        overlay_wipes(raw, out, sorted(BOUNDARIES.values()))
        print("wrote", out, "(with grid-wipe transitions masking each cut)")
    else:
        shutil.copy2(raw, out)
        print("wrote", out, "(no B-roll cuts for this reel -- straight concat)")


if __name__ == "__main__":
    main()
