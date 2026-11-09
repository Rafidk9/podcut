"""Split-format pass for the Rahul 'SA nomination program' reel (2026-10-23).

Top 1080x940: the longtake motion panel (top_take/comp.html -> work/top.mp4,
rendered with tools/longtake/render.py --no-sfx; it carries its own gold seam).
Bottom 1080x980: Rahul, cropped 1.15x so his head sits ~130px under the seam (clear of the seam captions).
The two takes are framed differently (IMG_0091 head-top y~560, IMG_0090
y~730 in base.mp4), so the crop offset switches at the take boundary.

Bakes into work/segments/seg_XX.mp4 (insert_broll.py rebuilds from those, not
base.mp4), AFTER build_base.py and BEFORE insert_broll.py, always starting
from the clean copies in work/segments_orig/, so it is safe to re-run.

    python split.py
"""
import os
import shutil
import subprocess
import sys

REEL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(REEL))
from ffmpeg_util import COLOR_TAGS, run  # noqa: E402

WORK = os.path.join(REEL, "work")
TOP_H, BOT_H = 940, 980
ZOOM = 1.15
CW, CH = round(1080 / ZOOM), round(BOT_H / ZOOM)
TAKE_CHANGE = 20.467   # end of seg_06 (last IMG_0091 segment) on the output timeline
CROP_A = (20, 440)     # IMG_0091: x, y in base.mp4
CROP_B = (0, 590)      # IMG_0090


def dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip())


def main():
    segdir = os.path.join(WORK, "segments")
    origdir = os.path.join(WORK, "segments_orig")
    top = os.path.join(WORK, "top.mp4")
    if not os.path.exists(top):
        raise SystemExit("work/top.mp4 missing -- render top_take/comp.html first")
    if not os.path.isdir(origdir):
        shutil.copytree(segdir, origdir)
    segs = sorted(f for f in os.listdir(origdir) if f.startswith("seg_") and f.endswith(".mp4"))
    t0 = 0.0
    for f in segs:
        src = os.path.join(origdir, f)
        d = dur(src)
        cx, cy = CROP_A if t0 + d / 2 < TAKE_CHANGE else CROP_B
        fc = (f"[0:v]crop={CW}:{CH}:{cx}:{cy},scale=1080:{BOT_H}:flags=lanczos,setsar=1[bot];"
              f"[1:v]scale=1080:{TOP_H},setsar=1,format=yuv420p[top];"
              f"[top][bot]vstack=inputs=2,format=yuv420p[v]")
        run(["-i", src, "-ss", f"{t0:.3f}", "-t", f"{d:.3f}", "-i", top, "-filter_complex", fc,
             "-map", "[v]", "-map", "0:a", "-t", f"{d:.3f}", "-r", "30",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", *COLOR_TAGS,
             "-c:a", "copy", "-video_track_timescale", "90000", os.path.join(segdir, f)])
        print(f"{f}: {t0:.2f}+{d:.2f}s crop {cx},{cy}")
        t0 += d


if __name__ == "__main__":
    main()
