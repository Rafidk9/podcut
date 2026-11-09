"""Normalize the user-supplied "AI search bar" motion graphic into
work/searchmg.mp4 so insert_broll.py can splice it like any other B-roll asset.

The clip (assets/searchmg/zlabz-search-justaskexpo.mp4, generated on zlabz.io)
is a 5.467s dark-UI mockup: a "What Are You Looking For?" heading above a search
field that types out a query character by character, then holds. It is spliced
over the opening of segment 1 (segment 2 until v3 dropped the P1 hook take),
where Salman says "Is the Just Ask Expo by PFEC Global" -- see broll_plan.json.

Source is already 1080x1920 / 30fps / yuv420p / bt709 / tv, i.e. the reel's own
spec, so unlike the 2026-08-11 Tushar reel's prep_matchcut.py there is no frame
rate or colour-primaries conversion to do here. What this script does instead:

  1. SPEED THE WHOLE CLIP INTO 1.6s. The full 5.467s is retimed by
     setpts*0.29268 (~3.42x) so the query finishes typing inside the cutaway --
     the point of the cutaway is the completed campaign name, so it has to
     land. An earlier version instead trimmed to 2.42s and sped up only that,
     to dodge the typo below; that kept the text honest but cut away at "PFEC
     Global Jus", i.e. it never delivered the line. Fixing the typo directly
     (step 2) is what makes the full-clip speed-up safe.

  2. FIX THE TYPO IN THE QUERY. The string typed into the tool reads "PFEC
     Global Jusk Ask EXPO" -- "Jusk" for "Just". This is the client's own
     campaign name, so it cannot go out. The fix is a single-glyph swap rather
     than redrawing the line, which keeps every other pixel of the original
     render untouched:

       cover   x=286 y=998 w=22 h=44, patched with a slice of empty field
               interior lifted from the SAME columns 44px lower (y=1042), so
               both the field's horizontal gradient and its grain carry over
       redraw  a Segoe UI 't' (work/t_glyph.png), ink box 13x26, placed so its
               STEM lands on the old 'k' stem at x=290 and its baseline on
               y=1032. The stem sits 4px inside the glyph's ink box (the
               crossbar overhangs left), so the ink box goes at x=286 -- an
               earlier version aligned the ink box itself to 290 and the
               4px error read as a visible space in "Jus t"

     The metrics come from measuring the render, not guessing: the query's
     glyph runs put "Jusk" at J(235-246) u(250-268) s(272-286) k(289-306),
     baseline y=1032, x-height 20px (1013-1032) and 'k' ascender 29px
     (1004-1032). Segoe UI at 39px gives x-height 20 and t-height 26, which is
     the correct typographic relationship ('t' ascends less than 'k'). Text
     colour is sampled off the 'k' itself. Segoe UI was picked over Calibri,
     Arial and Verdana by rendering all four against the reference 't' in the
     heading's "What" -- the source face is a modern UI sans with a
     double-storey 'a' (so NOT Poppins) and Segoe UI matches its stem/crossbar/
     bottom-hook shape closest.

     BOTH edits are gated to `gte(t,0.655)` because the 'k' does not exist for
     the first two thirds of the clip -- drawing a 't' into an empty field
     would be worse than the typo. Frame-by-frame scanning of the type-on (the
     text is left-aligned, so the right edge only grows) puts the 'k' first on
     screen at source frame 68, t=2.267s; retimed that is 0.663s, which is
     output frame 19.9, so the gate sits at 0.655 to land cleanly on output
     frame 20. Note this had to be measured by decoding from frame 0 -- input
     seeking (`-ss` before `-i`) lands on the wrong frames on this file and
     reported the 'k' as arriving a full 0.25s later than it does.

  3. COVER TWO MORE REGIONS, each by a different method, because they are
     different shapes of problem. The background is a smooth two-axis gradient
     -- it samples ~23 at the frame edges against ~40 mid-frame, and falls from
     ~31 at y=1300 to ~13 at y=1910 -- so a flat drawbox would show as a patch
     at any single colour.

       chips band  patched at x=0 y=1140 w=1080 h=96, using a clean strip
                   lifted from y=1300 of the SAME frame
           The row of fake "related search" chips under the field. They repeat
           the same typo ("PFEC Global Jusk Ask EXPO reddit" / "...meaning")
           and are wrong from frame 1. They are removed wholesale rather than
           glyph-patched like the main query: there are three of them, they are
           small enough that losing them costs nothing, and the row reads fine
           as empty space.

           delogo was tried here first and streaked: the band is 1064px wide,
           so delogo has to interpolate between borders that far apart and it
           smeared the vertical gradient into visible vertical banding. Copying
           a genuinely empty strip from lower in the same frame keeps the real
           horizontal gradient intact, because it comes from the same x
           positions. y=1300 is picked for the vertical match: sampled across
           the width it runs 12..37 against the target band's own 12..39 at
           y=1140 and 12..37 at y=1228, i.e. within ~2/255 at both seams.

       watermark   delogo x=895 y=1832 w=175 h=76
           The "zlabz.io" attribution pill, bottom-right. delogo is the right
           tool at this size -- the box is small enough that interpolating from
           its border reproduces the local gradient cleanly.

     The "Don't MISS OUT" line at y~1250 is left alone: it carries no typo and
     is on-message for the reel. The patch band stops at y=1236, clear of it.

Audio is dropped (-an) on purpose: the source has no audio stream at all, and
insert_broll maps the SEGMENT's audio (`-map 1:a`) and never the B-roll's, so
there is nothing to carry through either way.

Run after build_base.py and before insert_broll.py (order doesn't matter
relative to date_behind.py / cities_behind.py -- they touch different files):

    PODCUT_REEL=2026-08-13_salman-just-ask-expo \\
        python 2026-08-13_salman-just-ask-expo/prep_searchmg.py

Pass --check to also write check/searchmg_cover.jpg -- the fixed word and both
covered regions at full resolution, taken from the finished asset.
"""
import os
import shutil
import subprocess
import sys

FF = shutil.which("ffmpeg") or "ffmpeg"
REEL = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REEL, "assets", "searchmg", "zlabz-search-justaskexpo.mp4")
OUT = os.path.join(REEL, "work", "searchmg.mp4")
GLYPH = os.path.join(REEL, "work", "t_glyph.png")

SRC_DUR = 5.466667       # full clip
TARGET_DUR = 1.6         # requested cutaway length
SPEED = TARGET_DUR / SRC_DUR

# --- typo fix: "Jusk" -> "Just" -----------------------------------------
K_BOX = (286, 998, 22, 44)     # region to blank (the 'k'), x y w h
# Patch source: the SAME x, 44px lower -- empty field interior. Taking it from
# the same columns is the point: the field carries a horizontal gradient (mean
# 43 at x=286 against 46 at x=600), so an earlier version that lifted the strip
# from x=600 left a faintly brighter rectangle around the fixed word. Vertically
# the field is flat (43-44 from y=1038 through y=1092), so a same-x/lower-y
# source matches on both axes.
K_SRC_Y = 1042
T_LEFT, T_BASELINE = 286, 1032   # ink-box left; puts the t stem on the k stem (x=290)
T_FONT = "C:/Windows/Fonts/segoeui.ttf"
T_SIZE = 39
T_RGB = (178, 181, 178)        # pre-blur; lands ~170 after softening, matching the 'k'
T_BLUR = 0.5                   # source glyphs are soft; a crisp overlay would stand out
# output-timeline gate; see the module docstring for how this was derived
T_GATE = 0.655

# --- chips band: patch destination, and the clean strip lifted to fill it ---
PATCH_Y, PATCH_H = 1140, 96
STRIP_Y = 1300
# zlabz.io attribution pill (x, y, w, h) -- small enough for delogo
WATERMARK = (895, 1832, 175, 76)


def build_glyph():
    """Render the replacement 't', cropped to its ink box so the overlay
    coordinates below are exact pixel positions rather than font metrics."""
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    from PIL import ImageFilter

    font = ImageFont.truetype(T_FONT, T_SIZE)
    im = Image.new("RGBA", (90, 90), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((20, 20), "t", font=font, fill=T_RGB + (255,))
    a = np.array(im)[:, :, 3]
    ys, xs = np.where(a > 8)
    # crop to ink FIRST, then blur, so the recorded ink box is the sharp one the
    # overlay coordinates are derived from; pad by the blur radius so the soft
    # edge is not clipped
    pad = 3
    im = im.crop((xs.min() - pad, ys.min() - pad, xs.max() + 1 + pad,
                  ys.max() + 1 + pad))
    im = im.filter(ImageFilter.GaussianBlur(T_BLUR))
    os.makedirs(os.path.dirname(GLYPH), exist_ok=True)
    im.save(GLYPH)
    # report the SHARP ink size (pad stripped) -- callers position by that
    return im.size[0] - 2 * pad, im.size[1] - 2 * pad


def cover_graph(gw, gh):
    """filter_complex for the retime + all three repairs. The splits happen
    AFTER the retime so every patch strip comes from the same frame it is
    pasted back onto, and so the `enable` gates read the output clock."""
    wx, wy, ww, wh = WATERMARK
    kx, ky, kw, kh = K_BOX
    return (
        f"[0:v]setpts=(PTS-STARTPTS)*{SPEED:.6f},split=3[m][s1][s2];"
        f"[s1]crop=1080:{PATCH_H}:0:{STRIP_Y}[chips];"
        f"[s2]crop={kw}:{kh}:{kx}:{K_SRC_Y}[kpatch];"
        f"[m][chips]overlay=x=0:y={PATCH_Y}:eof_action=repeat[c1];"
        f"[c1][kpatch]overlay=x={kx}:y={ky}:eof_action=repeat:"
        f"enable='gte(t,{T_GATE})'[c2];"
        f"[c2][1:v]overlay=x={T_LEFT - 3}:y={T_BASELINE - gh - 3}:eof_action=repeat:"
        f"enable='gte(t,{T_GATE})'[c3];"
        f"[c3]delogo=x={wx}:y={wy}:w={ww}:h={wh},"
        "fps=30,format=yuv420p,setsar=1,"
        "setparams=range=tv:color_primaries=bt709:color_trc=bt709:"
        "colorspace=bt709[v]")


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args,
                   check=True)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    gw, gh = build_glyph()
    run(["-i", SRC, "-i", GLYPH, "-an",
         "-filter_complex", cover_graph(gw, gh), "-map", "[v]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-color_range", "tv",
         "-video_track_timescale", "90000", OUT])
    print(f"wrote {OUT} ({TARGET_DUR}s, {1/SPEED:.2f}x, 'Jusk' -> 'Just')")


def check():
    """Full-res look at the fixed word and both covered regions, from the
    finished asset so the check reflects exactly what gets spliced."""
    from PIL import Image
    tmp = os.path.join(REEL, "work", "searchmg_check")
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(os.path.join(REEL, "check"), exist_ok=True)
    raw = os.path.join(tmp, "raw.png")
    cov = os.path.join(tmp, "cov.png")
    # source frame 150 (t=5.0) and the matching late frame of the finished asset
    run(["-i", SRC, "-vf", "select=eq(n\\,150),format=yuv420p",
         "-frames:v", "1", raw])
    run(["-i", OUT, "-vf", "select=eq(n\\,44),format=yuv420p",
         "-frames:v", "1", cov])
    tiles = []
    for path in (raw, cov):
        im = Image.open(path).convert("RGB")
        tiles.append(im.crop((20, 985, 560, 1050)).resize((1080, 130)))
        tiles.append(im.crop((0, 1100, 1080, 1280)))
        tiles.append(im.crop((0, 1790, 1080, 1920)))
    sheet = Image.new("RGB", (1080, sum(t.height for t in tiles)))
    y = 0
    for t in tiles:
        sheet.paste(t, (0, y))
        y += t.height
    dest = os.path.join(REEL, "check", "searchmg_cover.jpg")
    sheet.save(dest, quality=93)
    shutil.rmtree(tmp, ignore_errors=True)
    print("wrote", dest,
          "(RAW: query, chips, watermark -- then FIXED: query, chips, watermark)")


if __name__ == "__main__":
    main()
    if "--check" in sys.argv:
        check()
