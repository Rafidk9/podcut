"""Scaffold a self-contained longtake project folder:

    <dir>/comp.html      the PFEC starter composition (edit this)
    <dir>/longtake.js    the motion library (copied, so the folder renders on its own)
    <dir>/fonts/         Poppins (OFL) -- the reels' house font
    <dir>/logo/          PFEC logo SVGs

    python new.py ../../reels/2026-11-02_seminar/opener_take
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PODCUT = os.path.dirname(os.path.dirname(HERE))
FONTS = os.path.join(PODCUT, "assets", "motion-styles", "fonts")
LOGO = os.path.join(PODCUT, "assets", "logo")
WEIGHTS = ["Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"]


def scaffold(dest, force=False):
    if os.path.exists(os.path.join(dest, "comp.html")) and not force:
        raise SystemExit(f"{dest} already has a comp.html (pass --force to overwrite)")
    os.makedirs(os.path.join(dest, "fonts"), exist_ok=True)
    os.makedirs(os.path.join(dest, "logo"), exist_ok=True)
    shutil.copy(os.path.join(HERE, "templates", "comp.html"), dest)
    shutil.copy(os.path.join(HERE, "lib", "longtake.js"), dest)
    for w in WEIGHTS:
        shutil.copy(os.path.join(FONTS, f"Poppins-{w}.ttf"), os.path.join(dest, "fonts"))
    shutil.copy(os.path.join(FONTS, "OFL.txt"), os.path.join(dest, "fonts"))
    for f in ("pfec-logo-white.svg", "pfec-logo-colour.svg"):
        shutil.copy(os.path.join(LOGO, f), os.path.join(dest, "logo"))
    return dest


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if x != "--force"]
    if len(args) != 1:
        raise SystemExit(__doc__)
    print("scaffolded", scaffold(args[0], "--force" in sys.argv))
