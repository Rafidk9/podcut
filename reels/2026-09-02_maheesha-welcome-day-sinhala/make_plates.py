"""Build the five 1080x1920 plates that snap behind Maheesha while she names the
five branches. Run once; bg_swap.py consumes assets/cities/*_plate.jpg.

SOURCE: each office's own Welcome Day leaflet design (the marketing team's A4
artwork, square social crop, one per branch). These are PFEC's own creatives, so
there is no external licence to carry -- and unlike the event photography they
exist for all five branches, including Brisbane and Perth.

LAYOUT. The designs are square (1200x1200) and the frame is 9:16, so a plain
cover-crop would throw away a third of the artwork. Instead each plate is the
whole design, scaled to DESIGN_W and placed at DESIGN_TOP, over a blurred,
darkened cover-crop of itself so the frame is filled edge to edge with no bars.

DESIGN_TOP/DESIGN_W are not arbitrary. Maheesha is matted on top of this plate,
and in segment 4 her hair starts at roughly 25% of frame height (~480px) and her
body spans about x 450-990 -- so the middle-lower band of the plate is going to
be hidden no matter what. The design's own hierarchy runs "Welcome DAY" headline
then the city badge then the boat photo then a bottom bar with the date and the
per-city time, and the one thing that MUST survive is the city badge, since the
whole point of the sequence is that the branch on screen matches the branch she
just said. So the design is sized and pushed up until its badge lands above her
hairline; the bottom date bar is knowingly sacrificed behind her torso (the date
is carried by the SAT 19 SEPT marker highlight and by the subtitles instead).

Worth knowing for the copy: these designs are the source of truth that the event
runs to DIFFERENT hours per city -- Brisbane 11:30-2:30, Melbourne and Adelaide
12-3, Perth and Sydney 12-4 -- and that entry is free. She says "12 to 3" on
camera, which is only true for two of the five, so nothing in this reel states a
single time for all branches. See content.json's _times_note.
"""
import os

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

REEL = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(REEL, "assets", "cities")
DL = r"C:/Users/AU-0011-PFEC-G/Downloads"
W, H = 1080, 1920
DESIGN_W = 960          # sized so the city badge clears her hairline (see above)
DESIGN_TOP = 46

PLATES = [
    ("brisbane", f"{DL}/Brisbane Welcome Day Design.jpg"),
    ("melbourne", f"{DL}/Melbourne Welcome Day Design.jpg"),
    ("perth", f"{DL}/Perth Welcome Day Design.jpg"),
    ("adelaide", f"{DL}/Adelaide Welcome Day Design.jpg"),
    ("sydney", f"{DL}/Sydney Welcome Day Design.png"),
]


def backdrop(im):
    """Fill the 9:16 frame with a heavily blurred, darkened cover-crop of the
    design itself, so the plate reads as one designed object rather than
    artwork floating on a flat colour -- and so nothing competes with the sharp
    copy sitting on top of it."""
    sw, sh = im.size
    scale = max(W / sw, H / sh) * 1.15
    nw, nh = round(sw * scale), round(sh * scale)
    bg = im.resize((nw, nh), Image.LANCZOS).crop(
        ((nw - W) // 2, (nh - H) // 2, (nw - W) // 2 + W, (nh - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(38))
    return ImageEnhance.Brightness(bg).enhance(0.52)


def main():
    for name, src in PLATES:
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        plate = backdrop(im)
        dw = DESIGN_W
        dh = round(im.size[1] * dw / im.size[0])
        plate.paste(im.resize((dw, dh), Image.LANCZOS), ((W - dw) // 2, DESIGN_TOP))
        out = os.path.join(OUT, f"{name}_plate.jpg")
        plate.save(out, quality=93)
        print(f"{name:10s} {im.size[0]}x{im.size[1]} -> design {dw}x{dh} @ y{DESIGN_TOP}")


if __name__ == "__main__":
    main()
