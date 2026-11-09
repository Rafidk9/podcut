"""Explainer-take pass for the Apurva employer-sponsorship reel (2026-11-05).
Same format as reels/2026-10-28_tushar-explainer: take/comp.html is one longtake
over the whole talking-head timeline, take/mask.html the same file in MASK mode,
both rendered with tools/longtake/render.py --no-sfx to work/take_comp.mp4 and
work/take_mask.mp4 at identical blur settings.

Unlike Tushar's single fixed 260 px drop, her head height changes per take (8
locations), so each take gets its own DROP keeping her head just inside the
window. Take 0 slides 240 -> its drop as the window goes FULL -> SPLIT.

    out = comp * (1 - mask) + apurva * mask

Writes work/captioned.mp4 with base.mp4's audio. Run after build_base.py, then
build_composite.py (skip insert_broll and build_captions).
"""
import json
import os
import sys

REEL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(REEL))
from ffmpeg_util import COLOR_TAGS, run  # noqa: E402

WORK = os.path.join(REEL, "work")
CUTS = [4.90, 7.02, 11.14, 17.54, 24.12, 25.50, 31.02]
DROPS = [333, 496, 325, 388, 281, 273, 186, 259]   # measured: head top lands ~930 (SPLIT) / ~950 (CARD)


def y_expr():
    e = str(DROPS[-1])
    for cut, d in reversed(list(zip(CUTS, DROPS))):
        e = f"if(lt(t,{cut}),{d},{e})"
    # take 0: FULL window needs only a 240 drop, eased to DROPS[0] with the split
    ramp = f"240+{DROPS[0] - 240}*(1-cos(PI*(t-1.3)/0.55))/2"
    return f"if(lt(t,1.3),240,if(lt(t,1.85),{ramp},{e}))"


def write_sync():
    """qa_reel.py's drift check reads work/caption_sync.json, which only
    build_captions.py writes. This format skips that script, so record what the
    comp really baked (take/words.js): a base rebuild without a new words.js
    and re-render still fails QA, as it should."""
    src = open(os.path.join(REEL, "take", "words.js"), encoding="utf-8").read()
    words = json.loads(src[src.index("["):src.rindex("]") + 1])
    cue = lambda w: {"text": w[0].strip(",.?").upper(), "start": w[1]}
    json.dump({"first_cue": cue(words[0]), "last_cue": cue(words[-1])},
              open(os.path.join(WORK, "caption_sync.json"), "w", encoding="utf-8"))


def main():
    write_sync()
    base, comp, mask = (os.path.join(WORK, n) for n in ("base.mp4", "take_comp.mp4", "take_mask.mp4"))
    for p in (base, comp, mask):
        if not os.path.exists(p):
            raise SystemExit(f"missing {p}")
    fc = (f"color=black:s=1080x1920:r=30[bk];"
          f"[0:v]setsar=1[b];[bk][b]overlay=0:'{y_expr()}':eval=frame:shortest=1,format=gbrp[ap];"
          f"[1:v]scale=1080:1920,setsar=1,format=gbrp[co];"
          f"[2:v]scale=1080:1920,setsar=1,format=gray,format=gbrp[ma];"
          f"[co][ap][ma]maskedmerge,format=yuv420p[v]")
    run(["-i", base, "-i", comp, "-i", mask, "-filter_complex", fc,
         "-map", "[v]", "-map", "0:a", "-shortest", "-r", "30", "-fps_mode", "cfr",
         "-c:v", "libx264", "-preset", "medium", "-crf", "17", *COLOR_TAGS,
         "-c:a", "aac", "-ar", "48000", "-ac", "2", os.path.join(WORK, "captioned.mp4")])
    print("wrote work/captioned.mp4")


if __name__ == "__main__":
    main()
