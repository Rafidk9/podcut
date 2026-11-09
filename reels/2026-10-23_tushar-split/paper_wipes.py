"""Torn-paper wipes at the take changes of the Tushar '189 round' split reel.

A full-frame sheet of torn paper (generated here: crease shading, ragged left
and right edges, a strip of yellow tape, drop shadow) slides right -> left
across BOTH halves. It is wider than the frame and moves linearly, so it fully
covers 1080x1920 for ~3 frames around each cut (house rule: a wipe must cover
the frame at the cut). Cut times = take boundaries, read from clips.json.

Runs on work/base_broll.mp4 AFTER insert_broll.py and BEFORE build_captions.py.
The clean input is kept as work/base_broll_nowipe.mp4; pass --fresh after
re-running insert_broll.py so it re-copies.

    python paper_wipes.py [--fresh]
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REEL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(REEL))
from ffmpeg_util import COLOR_TAGS, run  # noqa: E402

WORK = os.path.join(REEL, "work")
W, H = 1080, 1920
PW, PH = 1500, 2100          # sheet incl. torn margins
DUR = 0.6                    # seconds the sheet takes to cross


def make_sheet(path):
    rng = np.random.default_rng(189)
    img = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    # ragged left/right edges
    ys = np.linspace(0, PH, 70)
    left = [(30 + rng.uniform(0, 34), y) for y in ys]
    right = [(PW - 30 - rng.uniform(0, 34), y) for y in ys[::-1]]
    poly = left + right
    shadow = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 14, y + 10) for x, y in poly], fill=(0, 0, 0, 110))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))
    # creases: soft grey diagonals, drawn on an RGB layer (RGBA drawing would
    # overwrite alpha and punch see-through stripes in the sheet)
    paper = Image.new("RGB", (PW, PH), (251, 251, 247))
    d = ImageDraw.Draw(paper)
    for _ in range(14):
        x0 = rng.uniform(-400, PW)
        d.line([(x0, 0), (x0 + rng.uniform(300, 900), PH)], fill=(236, 236, 231), width=int(rng.uniform(8, 30)))
    paper = paper.filter(ImageFilter.GaussianBlur(6)).convert("RGBA")
    grain = (rng.normal(0, 5, (PH, PW))).clip(-12, 12)
    arr = np.array(paper).astype(np.int16)
    arr[..., :3] = (arr[..., :3] + grain[..., None]).clip(0, 255)
    paper = Image.fromarray(arr.astype(np.uint8))
    mask = Image.new("L", (PW, PH), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    img.paste(paper, (0, 0), mask)
    # washi tape across the top
    tape = Image.new("RGBA", (420, 110), (236, 241, 103, 230))
    img.alpha_composite(tape.rotate(-8, expand=True, resample=Image.BICUBIC), (int(PW * 0.38), 120))
    img.save(path)


def cut_times():
    clips = json.load(open(os.path.join(REEL, "clips.json")))["clips"]
    t, prev, cuts = 0.0, None, []
    for c in clips:
        if prev is not None and c["name"] != prev:
            cuts.append(round(t, 3))
        prev = c["name"]
        t += c["keep"][1] - c["keep"][0]
    return cuts


def main():
    src = os.path.join(WORK, "base_broll.mp4")
    clean = os.path.join(WORK, "base_broll_nowipe.mp4")
    if "--fresh" in sys.argv or not os.path.exists(clean):
        shutil.copy2(src, clean)
    sheet = os.path.join(WORK, "paper_sheet.png")
    make_sheet(sheet)
    cuts = cut_times()
    print("wipes at", cuts)
    chain, last = [], "[0:v]"
    for i, c in enumerate(cuts):
        a = c - DUR / 2
        # left edge: 1080 at t=a -> -PW at t=a+DUR (linear, full cover around the cut)
        x = f"{W}-({W + PW})*(t-{a:.3f})/{DUR}"
        out = f"[v{i}]"
        chain.append(f"{last}[1:v]overlay=x='{x}':y={(H - PH) // 2}:enable='between(t,{a:.3f},{a + DUR:.3f})'{out}")
        last = out
    fc = ";".join(chain)
    run(["-i", clean, "-loop", "1", "-i", sheet, "-filter_complex", fc + f";{last}format=yuv420p[vo]",
         "-map", "[vo]", "-map", "0:a", "-shortest", "-r", "30",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", *COLOR_TAGS,
         "-c:a", "copy", src])
    print("wrote", src)


if __name__ == "__main__":
    main()
