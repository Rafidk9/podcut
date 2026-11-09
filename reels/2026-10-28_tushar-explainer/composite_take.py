"""Explainer-take pass for the Tushar SA trade-courses reel (2026-10-28).

take/comp.html is one continuous longtake over the whole talking-head timeline;
take/mask.html is the same file in MASK mode (graphics black, the window white,
greying out as the window closes into a dot). Both are rendered with
tools/longtake/render.py --no-sfx into work/take_comp.mp4 / work/take_mask.mp4,
with identical blur settings so their edges match.

Tushar sits 260 px low (his headroom fills the panel area otherwise), and
shows wherever the matte is white:

    out = comp * (1 - mask) + tushar * mask

Writes work/captioned.mp4 directly (the comp carries the word-by-word
captions and the name/MARN tag, so build_captions.py is skipped), with
base.mp4's audio. Run after build_base.py, then build_composite.py.

    python composite_take.py
"""
import os
import sys

REEL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(REEL))
from ffmpeg_util import COLOR_TAGS, run  # noqa: E402

WORK = os.path.join(REEL, "work")
DROP = 260


def main():
    base = os.path.join(WORK, "base.mp4")
    comp = os.path.join(WORK, "take_comp.mp4")
    mask = os.path.join(WORK, "take_mask.mp4")
    for p in (base, comp, mask):
        if not os.path.exists(p):
            raise SystemExit(f"missing {p}")
    fc = (f"[0:v]crop=1080:{1920 - DROP}:0:0,pad=1080:1920:0:{DROP}:black,setsar=1,format=gbrp[tu];"
          f"[1:v]scale=1080:1920,setsar=1,format=gbrp[co];"
          f"[2:v]scale=1080:1920,setsar=1,format=gray,format=gbrp[ma];"
          f"[co][tu][ma]maskedmerge,format=yuv420p[v]")
    run(["-i", base, "-i", comp, "-i", mask, "-filter_complex", fc,
         "-map", "[v]", "-map", "0:a", "-shortest", "-r", "30", "-fps_mode", "cfr",
         "-c:v", "libx264", "-preset", "medium", "-crf", "17", *COLOR_TAGS,
         "-c:a", "copy", os.path.join(WORK, "captioned.mp4")])
    print("wrote work/captioned.mp4")


if __name__ == "__main__":
    main()
