"""Renders the real Perth city block via build_city_block.py. Thin
per-city driver -- Adelaide/Brisbane/Melbourne/Hobart+Launceston should each
get their own equivalent driver (build_adelaide.py etc.) calling
build_city_block() with that city's own stamp colour + media_items.

Perth content picks (see work/frame_scan/*_grid.jpg for the eyeballed
candidates):
  - IMG_7233.MOV, t=1.0-5.55s, sped up 3.5x into 1.3s on screen: presenter
    mid-gesture, roadshow banner + small audience in frame, camera holding
    steady -- fast-forwarded (see "speed" key in build_city_block.py) so it
    reads as a fun time-lapse beat instead of a slow real-time pan; the
    1.3s freed vs. the original 2.6s real-time cut goes to an extra photo.
  - IMG_5890.jpg: wide shot, banner + crowd (already used in the approved
    style checkpoint).
  - IMG_5894.jpg: 1-on-1 consultation at a desk with laptop -- shows the
    "real answers" outcome, good variety against the wide crowd shot.
  - IMG_5892.jpg: widest crowd/banner shot (~10 attendees + full banner
    visible), distinct framing from IMG_5890 -- added to use the time
    freed by fast-forwarding the video.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_city_block import build_city_block  # noqa: E402

STAMP_COLOR = "#FFC500"  # brand yellow -- pops against the indigo/navy bg (was #100796, low-contrast)

MEDIA_ITEMS = [
    {"type": "video", "path": "input/perth/IMG_7233.MOV",
     "trim_start": 1.0, "duration": 1.3, "speed": 3.5},
    {"type": "photo", "path": "input/perth/IMG_5890.jpg", "duration": 2.6},
    {"type": "photo", "path": "input/perth/IMG_5894.jpg", "duration": 2.6},
    {"type": "photo", "path": "input/perth/IMG_5892.jpg", "duration": 1.3},
]


def main():
    out = build_city_block(
        city_name="PERTH",
        stamp_color=STAMP_COLOR,
        media_items=MEDIA_ITEMS,
        stamp_index=1,
        total_stamps=5,
    )
    print("Perth block:", out)


if __name__ == "__main__":
    main()
