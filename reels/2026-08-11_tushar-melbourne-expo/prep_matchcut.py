"""Normalize the user-supplied "text match cut" clip into work/matchcut.mp4 so
insert_broll.py can splice it like any other B-roll asset.

The clip (assets/matchcut/textmatchcut-justaskexpo.mp4) is a newspaper-column
text match cut: successive article pages with the phrase "JustAskEXPO"
highlighted in yellow, so the highlighted words land on screen exactly as
Tushar says "At the Just Ask Expo". It is spliced over the opening of segment 2
-- see broll_plan.json.

Why this script exists rather than just pointing insert_broll at the raw file:

  1. FRAME RATE. Source is 60fps; the reel is 30fps throughout. insert_broll's
     own VF does carry fps=30, so this is belt-and-braces, but doing the
     conversion once here keeps the spliced asset inspectable at the same spec
     as everything else in work/.

  2. COLOUR, which is the real reason. Source is tagged smpte170m on all three
     of primaries/transfer/matrix (SD/NTSC), NOT bt709. Every other asset in
     this pipeline is bt709/tv, and the encoders downstream apply COLOR_TAGS,
     which STAMPS bt709 on the output without converting the pixels -- exactly
     the "HDR tags riding on unconverted data" failure mode build_base.py warns
     about, just at SD scale instead. zscale below does the real primaries
     conversion first, so the bt709 tag the reel ends up carrying is honest.
     The visible difference on a near-monochrome newspaper graphic is small,
     but "small" is not a reason to ship mislabelled colour.

  3. The source is 5.22s and only the first 2.5s is used (broll_plan.json's
     "broll_durs"). The full converted clip is written here anyway -- trimming
     is insert_broll's job, so the splice length stays a one-line change in
     the plan rather than something baked into an asset.

Audio is dropped (-an) on purpose: insert_broll maps the SEGMENT's audio
(`-map 1:a`) and never the B-roll's, so the clip's own soundtrack would be
discarded regardless. Dropping it here makes that explicit instead of leaving
a stream that silently goes nowhere.

Run after build_base.py and before insert_broll.py (order doesn't matter
relative to bg_swap_melbourne.py -- they touch different files):

    PODCUT_REEL=2026-08-11_tushar-melbourne-expo \\
        python 2026-08-11_tushar-melbourne-expo/prep_matchcut.py
"""
import os
import shutil
import subprocess

FF = shutil.which("ffmpeg") or "ffmpeg"
REEL = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REEL, "assets", "matchcut", "textmatchcut-justaskexpo.mp4")
OUT = os.path.join(REEL, "work", "matchcut.mp4")


def main():
    if not os.path.isfile(SRC):
        raise SystemExit(f"source clip not found: {SRC}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    vf = (
        # Real SD->HD conversion (not a re-tag). NOTE the filter choice: the
        # zscale-through-linear-light chain that build_base.py uses for HDR
        # input FAILS here with "code 3074: no path between colorspaces",
        # because the source's transfer/primaries/matrix are all smpte170m and
        # zscale won't infer a route from them without every input field spelled
        # out. `colorspace` is the purpose-built SD<->HD converter and takes the
        # input spec in one argument, so it is both correct and readable.
        # (zscale with explicit matrixin/primariesin/transferin/rangein also
        # works and was verified, but reads far worse for the same result.)
        "colorspace=iall=smpte170m:all=bt709:irange=tv:range=tv,"
        "format=yuv420p,"
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "setsar=1,fps=30,"
        # Assert all four on the frames themselves so libx264 writes the full
        # VUI -- the -color_* flags alone leave transfer/primaries unspecified.
        "setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709"
    )

    subprocess.run(
        [FF, "-y", "-hide_banner", "-loglevel", "error", "-i", SRC,
         "-an", "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-color_range", "tv", "-r", "30",
         "-video_track_timescale", "90000", OUT],
        check=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
