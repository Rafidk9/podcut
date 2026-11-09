"""Renders the real Adelaide city block via build_city_block.py. Thin
per-city driver, mirrors build_perth.py.

Adelaide content picks (see work/frame_scan/adelaide_vid_grid.jpg and
work/frame_scan/adel_photo_grid*.jpg for the eyeballed candidates):
  - VID_20260806_140033.mp4, t=1.0-5.55s, sped up 3.5x into 1.3s on screen:
    attendee walking through the waiting area toward reception, multiple
    other attendees seated in the background, camera holding steady --
    fast-forwarded (see "speed" key in build_city_block.py) so it reads as
    a fun time-lapse beat instead of a slow real-time pan; the 1.3s freed
    vs. the original 2.6s real-time cut goes to an extra photo (same
    treatment as Perth's IMG_7233.MOV).
  - IMG_20260806_132638.jpg: wide shot of the packed waiting room, ~6-7
    attendees seated + one standing -- the crowd shot for spotting yourself.
  - IMG_20260806_140100010_HDR.jpg: 1-on-1 consultation at a desk with the
    "Our Services" branded backdrop -- shows the "real answers" outcome,
    good variety against the wide crowd shot (same pairing logic as Perth's
    IMG_5894 desk-consult pick).
  - IMG_20260806_140103.jpg: handshake + certificate moment at a desk under
    the "Our Accreditations" banner -- a distinct positive-outcome beat
    against the other two (check-in/reception vs. seminar-audience), added
    to use the time freed by fast-forwarding the video.

HDR check: VID_20260806_140033.mp4 probed as h264/yuvj420p, color_transfer
bt709, color_primaries bt470bg, color_space smpte170m -- no HLG/BT.2020/
10-bit side data, so this source is not the HDR case Perth hit. Render still
goes through build_city_block()'s standard --sdr flag + yuv420p re-encode
for consistency with the rest of the pipeline.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_city_block import build_city_block  # noqa: E402

STAMP_COLOR = "#E84B37"  # brand red-orange

MEDIA_ITEMS = [
    {"type": "video", "path": "input/adelaide/VID_20260806_140033.mp4",
     "trim_start": 1.0, "duration": 1.3, "speed": 3.5},
    {"type": "photo", "path": "input/adelaide/IMG_20260806_132638.jpg", "duration": 2.6},
    {"type": "photo", "path": "input/adelaide/IMG_20260806_140100010_HDR.jpg", "duration": 2.6},
    {"type": "photo", "path": "input/adelaide/IMG_20260806_140103.jpg", "duration": 1.3},
]


def main():
    out = build_city_block(
        city_name="ADELAIDE",
        stamp_color=STAMP_COLOR,
        media_items=MEDIA_ITEMS,
        stamp_index=2,
        total_stamps=5,
    )
    print("Adelaide block:", out)


if __name__ == "__main__":
    main()
