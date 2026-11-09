"""Renders the combined Hobart & Launceston city block via build_city_block.py.
Thin per-city driver, same pattern as build_perth.py -- see that file's
docstring for the overall convention. This is the DOUBLE-STAMP case
(is_double_stamp=True): both cities are covered by one shared roadshow stop
in the source footage (Tasmania), so they get one combined block sharing the
5th/last progress-dot slot instead of two separate blocks -- there is no
per-city split in the input media to justify two blocks.

Tasmania content picks (see work/frame_scan/tasmania/*.jpg for the eyeballed
candidates -- grid_landscape.jpg, grid_portrait.jpg, vrow1.jpg/vrow2.jpg):
  - IMG_7547.MOV, t=5.0-9.55s, sped up 3.5x into 1.3s on screen: presenter
    mid-gesture on stage, PFEC-branded slide ("Priority attribute tiers") on
    screen behind him, seated audience in the foreground -- direct parallel
    to Perth's IMG_7233.MOV pick; fast-forwarded (see "speed" key in
    build_city_block.py) so it reads as a fun time-lapse beat instead of a
    slow real-time pan. The 1.3s freed vs. the original 2.6s real-time cut
    goes to an extra photo.
  - IMG_7551.JPG: wide shot -- full seated crowd + presenter + branded
    slide on screen. Parallel to Perth's IMG_5890.jpg wide crowd shot.
  - IMG_7599.JPG: 1-on-1 consultation at a table, laptop + papers, with the
    "MIGRATION 360 ROADSHOW / FREE MIGRATION CONSULTATION" banner clearly
    visible in frame -- parallel to Perth's IMG_5894.jpg consultation shot,
    plus reinforces the roadshow branding directly.
  - IMG_7554.JPG: presenter mid-gesture addressing the seated front row,
    closer framing than IMG_7551's wide shot -- distinct composition, same
    stage/audience setting; added to use the time freed by fast-forwarding
    the video (parallel to Perth's IMG_5892.jpg addition).

Total on-screen media: 1.3 + 2.6 + 2.6 + 1.3 = 7.8s, in the 7-8s target window.

Tasmania's video source (IMG_7547.MOV) probed via ffprobe as h264/yuv420p/
bt709 -- ordinary 8-bit SDR, no HLG/BT.2020 side-data like some of the other
cities' phone footage. build_city_block()'s render call always forces
--sdr regardless (see its docstring), so this needed no special handling,
but the check was still run per the task brief before rendering.

Double-stamp layout: build_city_block.py's is_double_stamp branch was
already present (not a stub) when this driver was written, but had never
been exercised by a real render. It draws two independently-landed stamp
rings side by side (30%/70% of the 1080px width, 230px each -- vs 300px
for a single stamp), left ring "HOBART" landing first, right ring
"LAUNCESTON" 0.16s later, same ink colour, each with its own arc text +
plane glyph + "PFEC GLOBAL" footer. Left the per-ring footer as-is rather
than de-duping it into one shared "PFEC GLOBAL" between the two rings:
each ring reads as a fully self-contained stamp (matching how a real
passport carries one complete stamp per entry, even for two entries side
by side), and the rendered stills below show both footers sitting legibly
under their own ring with no crowding -- no correctness reason to add the
extra complexity of a shared/positioned-between element. Confirmed by
rendering and inspecting both stills (see reported stills below).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_city_block import build_city_block  # noqa: E402

STAMP_COLOR = "#31EB7C"  # brand green

MEDIA_ITEMS = [
    {"type": "video", "path": "input/tasmania/IMG_7547.MOV",
     "trim_start": 5.0, "duration": 1.3, "speed": 3.5},
    {"type": "photo", "path": "input/tasmania/IMG_7551.JPG", "duration": 2.6},
    {"type": "photo", "path": "input/tasmania/IMG_7599.JPG", "duration": 2.6},
    {"type": "photo", "path": "input/tasmania/IMG_7554.JPG", "duration": 1.3},
]


def main():
    out = build_city_block(
        city_name=["HOBART", "LAUNCESTON"],
        stamp_color=STAMP_COLOR,
        media_items=MEDIA_ITEMS,
        stamp_index=5,
        total_stamps=5,
        is_double_stamp=True,
        output_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "segment_tasmania.mp4"),
    )
    print("Hobart & Launceston block:", out)


if __name__ == "__main__":
    main()
