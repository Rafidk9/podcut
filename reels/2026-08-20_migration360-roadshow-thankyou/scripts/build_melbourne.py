"""Renders the real Melbourne city block via build_city_block.py. Thin
per-city driver -- see work/build_perth.py for the pattern this mirrors.

Melbourne content picks (see work/frame_scan_melb/*.jpg for the eyeballed
candidates -- richest source city: 14 landscape photos, 4 portrait videos
totaling 136.5s; 7 of the original 25 files are missing from Drive and were
excluded, working only with what's actually in input/melbourne/):

  - 20260812_124254.mp4, t=5.0-7.6s: presenter (Kapil Kumar, "189 Visa
    Insights" briefing) mid-gesture straight to camera, PFEC branded
    screen behind him, sharp/steady/well-lit continuous take (confirmed no
    internal cut across 5.0-7.6s -- this source file is itself a multi-cut
    compilation, so the window was checked frame-by-frame first). Fast-
    forwarded 2.0x into 1.3s on screen (mirrors Perth's IMG_7233.MOV "speed"
    treatment) -- source_span = 1.3*2.0 = 2.6s, i.e. exactly the
    frame-verified 5.0-7.6s window, no extra unverified footage pulled in.
    The 1.3s freed vs. the original 2.6s real-time cut goes to an extra
    photo (20260812_122726.jpg, below).
  - 20260812_124355.jpg: wide shot of the full session room, PFEC
    step-and-repeat backdrop, ~10 attendees seated and engaged -- the
    strongest single crowd shot in the set.
  - 20260812_124118.jpg: 1-on-1 consultation against the "OUR SERVICES"
    (Education/Migration/Health Insurance/Professional Year) branded wall,
    4 people engaged -- shows the "real answers" outcome, mirrors Perth's
    IMG_5894 pick.
  - 20260812_122726.jpg: waiting-room/lobby wide shot, 7 attendees seated,
    PFEC step-and-repeat + certificates wall and the "FREE consultation /
    550+ providers / award-winning / 20,000+ success stories" branded
    infographic all in frame -- distinct composition and colour palette
    (red/blue) from the other two photos, added to use the time freed by
    fast-forwarding the briefing video.

Two more Melbourne source videos surfaced later (attendee review footage,
see work/frame_scan_melb_reviews/*.jpg):

  - 20260812_122821.mp4 (27.1s) IS a genuine attendee testimonial: a man in
    a brown checked blazer speaking straight to camera, gesturing, PFEC
    office window backdrop -- glasses, in focus, steady framing throughout.
    Two clean speaking beats confirmed via frame scan (B_close1_*.jpg,
    B_close2_*.jpg), separated by a room/attendee cutaway mid-clip
    (B_122821_02.jpg): t=5.5-8.8s and t=24.0-27.0s. Both used here as
    separate media_items -- this is the richer city block, and both beats
    read clearly as "someone speaking to camera" rather than duplicating
    each other. Both carry a small "ATTENDEE FEEDBACK" badge (see the
    "badge" key in build_city_block.py's MEDIA ITEM SCHEMA) so they read
    unambiguously as testimonial content rather than generic footage --
    the badge sits low in the zone, well clear of the speaker's face (face
    lands roughly in the top half of the visible crop in both beats, per
    frame_scan_melb_reviews).
  - 20260812_124847.mp4 (6.9s) is NOT a testimonial (confirmed via
    A_124847_*.jpg: candid attendees on couches looking at phones in the
    waiting area, PFEC "20000+ Success Stories" wall graphic behind them,
    no one speaking to camera) -- excluded per review; kept as B-roll only
    if a future block needs plain waiting-room texture.

All Melbourne source videos are HEVC yuv420p10le, color_transfer
arib-std-b67 (HLG), color_primaries/space bt2020 -- confirmed via ffprobe.
build_city_block() always renders with --sdr (see its module docstring), so
this is handled automatically; verified against the rendered output
(h264/yuv420p/bt709) with no extra flag needed here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_city_block import build_city_block  # noqa: E402

STAMP_COLOR = "#00B3E3"  # brand cyan

TESTIMONIAL_BADGE = "ATTENDEE FEEDBACK"

MEDIA_ITEMS = [
    {"type": "video", "path": "input/melbourne/20260812_124254.mp4",
     "trim_start": 5.0, "duration": 1.3, "speed": 2.0},
    {"type": "photo", "path": "input/melbourne/20260812_124355.jpg", "duration": 2.6},
    {"type": "photo", "path": "input/melbourne/20260812_124118.jpg", "duration": 2.6},
    {"type": "photo", "path": "input/melbourne/20260812_122726.jpg", "duration": 1.3},
    {"type": "video", "path": "input/melbourne/20260812_122821.mp4",
     "trim_start": 5.5, "duration": 3.3, "orientation": "portrait"},
    {"type": "video", "path": "input/melbourne/20260812_122821.mp4",
     "trim_start": 24.0, "duration": 3.0, "orientation": "portrait"},
]


def main():
    out = build_city_block(
        city_name="MELBOURNE",
        stamp_color=STAMP_COLOR,
        media_items=MEDIA_ITEMS,
        stamp_index=4,
        total_stamps=5,
    )
    print("Melbourne block:", out)


if __name__ == "__main__":
    main()
