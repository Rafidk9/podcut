"""Thin, shared wrappers around ffmpeg / ffprobe -- pulled out of build_base.py,
insert_broll.py, build_composite.py, build_captions.py, and build_opener.py,
which each used to carry their own (byte-identical) copy of these. Centralizing
means a future colour-tag or flag fix only has to happen once instead of being
kept in sync by hand across every file that touches an encode -- exactly the
kind of drift that let one file's HDR-tag fix not reach the others."""
import os
import shutil
import subprocess
import sys

from render_progress import Progress

FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

# Explicit BT.709/SDR tags on every encode -- without these, libx264 just
# forwards whatever ambiguous/wrong tags rode in on the input. This is how
# HDR-tagged raw iPhone footage's colour metadata once ended up stamped onto
# an entire final file, including plain-SDR end cards concatenated in later.
#
# ffmpeg 8.1.2 (winget Gyan.FFmpeg build, confirmed 2026-08-07) regression:
# the top-level -color_primaries/-color_trc output options no longer reach
# libx264's actual bitstream -- only -colorspace does, so qa_reel.py's
# colour-tag check started failing with color_primaries=unknown /
# color_transfer=unknown even though every encode call here already passed
# COLOR_TAGS. -x264-params is what actually lands the primaries/transfer
# tags in the encoded stream on this ffmpeg version; keep both the top-level
# flags (harmless, and correct on older ffmpeg builds) and the x264-params
# belt-and-suspenders copy.
COLOR_TAGS = ["-color_primaries", "bt709", "-color_trc", "bt709",
              "-colorspace", "bt709", "-color_range", "tv",
              "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709:fullrange=off"]


def dur(path):
    return float(subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nokey=1", path],
        capture_output=True, text=True).stdout.strip())


def _find_total_duration(args):
    """Best-effort estimate of a render's output duration, used only to size
    the progress bar -- approximate is fine, this never affects correctness.
    Prefers an explicit -t/-to cap; otherwise the longest real file among the
    command's -i inputs (an overlay/audio layer's duration is always <= the
    main content's in this pipeline, so max() lands on the main content)."""
    for i, a in enumerate(args):
        if a in ("-t", "-to") and i + 1 < len(args):
            try:
                return float(args[i + 1])
            except ValueError:
                pass
    best = None
    for i, a in enumerate(args):
        if a == "-i" and i + 1 < len(args):
            path = args[i + 1]
            if not os.path.isfile(path):
                continue
            try:
                d = dur(path)
            except (ValueError, subprocess.SubprocessError):
                continue
            if best is None or d > best:
                best = d
    return best


def run(args, label=None):
    """Run ffmpeg. Shows a live progress bar (percent, elapsed, ETA) whenever
    the render's approximate total duration can be determined; falls back to
    the old silent behavior for quick metadata-only calls (single-frame
    grabs, audio extraction) where a bar isn't useful. label defaults to the
    output file's basename (by convention the last element of args), so
    every call site gets an identifying bar for free without having to pass
    one."""
    total = _find_total_duration(args)
    if not total or total <= 0:
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)
        return

    tag = label or (os.path.basename(args[-1]) if args else "ffmpeg")
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
           "-progress", "pipe:1"] + args
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, bufsize=1)
    bar = Progress(tag, total)
    for line in proc.stdout:
        line = line.strip()
        if not line.startswith("out_time_ms="):
            continue
        try:
            cur = int(line.split("=", 1)[1]) / 1_000_000
        except ValueError:
            continue
        bar.update(cur)

    ret = proc.wait()
    stderr = proc.stderr.read()
    bar.finish(ok=ret == 0)
    if ret != 0:
        if stderr:
            print(stderr, file=sys.stderr)
        raise subprocess.CalledProcessError(ret, cmd, stderr=stderr)
