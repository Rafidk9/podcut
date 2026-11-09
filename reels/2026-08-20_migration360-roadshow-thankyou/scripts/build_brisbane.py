"""Renders the real Brisbane city block via build_city_block.py. Thin
per-city driver, same pattern as build_perth.py.

Brisbane is the ONE city block that deliberately does NOT use the default
blur-extend photo treatment. Its 13 source photos are all WhatsApp-
compressed (~150-290KB each, 1600x1200 JPEGs -- visibly softer than the
other cities' 2-5MB originals; see work/media_inventory.json). All 4 items
below are photos with treatment="polaroid" (see build_city_block.py's MEDIA
ITEM SCHEMA / _emit_polaroid_item) -- a white-card, drop-shadowed, ~78%-width
snapshot with a warm-tint + grain grade, so the compression softness reads
as an intentional "polaroid snapshot" aesthetic instead of looking like a
mistake.

Re-checked after Perth's "speed" key landed (fast-forward a video into a
short beat, see build_city_block.py): re-eyeballed all 3 Brisbane source
videos (WhatsApp Video ...mp4, portrait 576x1024 effective after the
Display Matrix rotation) at both real-time and a 3.5x fast-forward test
(work/frame_scan/brisbane_speedtest/, incl. v0_speedtest_3.5x.mp4 and
contact sheets) before deciding photos-only still stands. Verdict: still
NO video, and by a wider margin than the original call --

  - Source quality gap is categorical, not marginal: Perth's IMG_7233.MOV is
    native 4K (3840x2160) at ~53 Mbps off an iPhone; Brisbane's WhatsApp
    videos are already-recompressed 1024x576 (portrait 576x1024 effective)
    at roughly 1/190th the bitrate density. Perth had real detail to
    downsample from when speeding up; Brisbane does not -- there is no
    hidden sharpness for a fast cut to reveal.
  - The candidate segment (steady presenter-at-screen, matching the "camera
    holding steady" shape that worked for Perth) only lasts ~1.5-1.8s
    before the camera whip-pans to the crowd -- too short to fill on its
    own, and any window wide enough to reach a usable ~1.3s on-screen beat
    at a legible 3+x speed necessarily swallows part of that pan. The 3.5x
    test clip confirms it: the held opening frame is fine, but the in-pan
    frames (see v0_3.5x_sheet.jpg, frames 2-3) show real smear that reads as
    blurry video, not an intentional time-lapse -- fast playback flashes it
    past the viewer but doesn't hide it, because at 1080 width the clip
    IS the frame, unlike Perth's clip which had 4K detail under the motion
    blur.
  - Head-to-head against the current polaroid photos (also WhatsApp-
    compressed, e.g. "12.11.34 PM (4).jpeg"), the stills are still
    meaningfully sharper than any frame pulled from the sped-up video --
    the photos are compressed once by WhatsApp, the videos are compressed
    *and* already low-res *and* motion-blurred *and* upscaled ~1.9x.

So: kept photos-only, and used the freed-up "what if we added the video"
time budget the way build_perth.py used its freed time from shrinking the
video -- by adding one more polaroid photo for variety instead.

Picks (see work/frame_scan/brisbane_photos_grid.jpg for the eyeballed
candidates, 0-indexed left-to-right/top-to-bottom; confirmed against the
sorted file listing -- grid idx N = the Nth file in `ls input/brisbane/*.jpeg`
sorted, i.e. all "12.11.34 PM" variants then all "12.11.35 PM" variants):
  - (4).jpeg [grid idx 3]: presenter mid-gesture, PFEC screen behind --
    close, energetic opener.
  - (5).jpeg [grid idx 4] -- NEW: presenter full-body, "MIGRATION 360
    ROADSHOW / FREE MIGRATION CONSULTATION" banner fully legible alongside
    the PFEC screen -- a clean establishing/context beat (banner text is
    sharp and readable) that reads differently from the close gesture shot,
    added for variety in place of the video.
  - 12.11.35 PM (5).jpeg [grid idx 10]: wide crowd shot, "TURN REFERRALS"
    banner -- ~20 attendees, the "full room" beat.
  - 12.11.35 PM (2).jpeg [grid idx 7]: wide crowd shot, "TURN REFERRALS"
    banner, most people in frame of any candidate -- closing beat.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_city_block import build_city_block  # noqa: E402

STAMP_COLOR = "#FFC500"  # brand yellow -- reused from Perth; not adjacent in
                          # the sequence (Perth=1, Brisbane=5), so no clash.

MEDIA_ITEMS = [
    {"type": "photo", "treatment": "polaroid", "duration": 2.3,
     "path": "input/brisbane/WhatsApp Image 2026-08-14 at 12.11.34 PM (4).jpeg"},
    {"type": "photo", "treatment": "polaroid", "duration": 1.3,
     "path": "input/brisbane/WhatsApp Image 2026-08-14 at 12.11.34 PM (5).jpeg"},
    {"type": "photo", "treatment": "polaroid", "duration": 2.1,
     "path": "input/brisbane/WhatsApp Image 2026-08-14 at 12.11.35 PM (5).jpeg"},
    {"type": "photo", "treatment": "polaroid", "duration": 2.1,
     "path": "input/brisbane/WhatsApp Image 2026-08-14 at 12.11.35 PM (2).jpeg"},
]


def main():
    out = build_city_block(
        city_name="BRISBANE",
        stamp_color=STAMP_COLOR,
        media_items=MEDIA_ITEMS,
        stamp_index=3,
        total_stamps=5,
        is_double_stamp=False,
    )
    print("Brisbane block:", out)


if __name__ == "__main__":
    main()
