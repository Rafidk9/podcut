"""Contact sheet of a longtake composition at chosen times -- look before you
render. Times default to every beat boundary plus the midpoint between them.

    python stills.py comp.html --out stills.png
    python stills.py comp.html --times 0.5,2.4,6 --out stills.png --cols 3
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lt_page  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("comp")
    ap.add_argument("--out", required=True)
    ap.add_argument("--times", help="comma-separated seconds")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--width", type=int, default=270, help="thumbnail width px")
    a = ap.parse_args(argv)

    from PIL import Image, ImageDraw
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br, pg, info = lt_page.open_comp(pw, a.comp)
        if a.times:
            times = [float(x) for x in a.times.split(",")]
        else:
            bt = sorted({0.0, info["dur"], *[b["t"] for b in info["beats"]]})
            times = sorted({round(t, 3) for x, y in zip(bt, bt[1:]) for t in (x + 0.05, (x + y) / 2)} | {round(info["dur"] - 0.05, 3)})
        shots = []
        for t in times:
            lt_page.seek(pg, t)
            shots.append((t, lt_page.grab(pg)))
        br.close()
    W, H = info["size"]
    tw, th = a.width, int(a.width * H / W)
    rows = (len(shots) + a.cols - 1) // a.cols
    sheet = Image.new("RGB", (a.cols * (tw + 4), rows * (th + 4)), "white")
    for j, (t, img) in enumerate(shots):
        x, y = (j % a.cols) * (tw + 4), (j // a.cols) * (th + 4)
        sheet.paste(img.resize((tw, th)), (x, y))
        ImageDraw.Draw(sheet).rectangle([x, y, x + 52, y + 18], fill="black")
        ImageDraw.Draw(sheet).text((x + 4, y + 3), f"{t:.2f}s", fill="white")
    sheet.save(a.out)
    print(f"wrote {a.out} ({len(shots)} frames: {', '.join(f'{t:g}' for t in times)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
