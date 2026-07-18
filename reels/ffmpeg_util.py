"""Thin, shared wrappers around ffmpeg / ffprobe -- pulled out of build_base.py,
insert_broll.py, build_composite.py, build_captions.py, and build_opener.py,
which each used to carry their own (byte-identical) copy of these. Centralizing
means a future colour-tag or flag fix only has to happen once instead of being
kept in sync by hand across every file that touches an encode -- exactly the
kind of drift that let one file's HDR-tag fix not reach the others."""
import shutil
import subprocess

FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

# Explicit BT.709/SDR tags on every encode -- without these, libx264 just
# forwards whatever ambiguous/wrong tags rode in on the input. This is how
# HDR-tagged raw iPhone footage's colour metadata once ended up stamped onto
# an entire final file, including plain-SDR end cards concatenated in later.
COLOR_TAGS = ["-color_primaries", "bt709", "-color_trc", "bt709",
              "-colorspace", "bt709", "-color_range", "tv"]


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


def dur(path):
    return float(subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nokey=1", path],
        capture_output=True, text=True).stdout.strip())
