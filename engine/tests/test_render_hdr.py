"""HDR→SDR tone-mapping: real ffmpeg round-trip.

Generates a genuine HDR clip (10-bit, HLG transfer, BT.2020) like a modern
phone produces, renders it through render_single, and asserts the output is
correctly tagged SDR bt709. Per the colour-bug postmortem: verification MUST
check ffprobe colour tags — pixel diffing does not catch this class of bug.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcut import ffutil, render                        # noqa: E402
from podcut.models import EDL, Interval, Segment         # noqa: E402

pytestmark = pytest.mark.skipif(not ffutil.have_ffmpeg(),
                                reason="ffmpeg not on PATH")


def _make_hdr_clip(path: str) -> str:
    ffutil.run([
        "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        # setparams stamps the frames so the tags land in the bitstream VUI,
        # like real phone HDR footage (output -color_* flags alone are
        # container-only and don't survive remux).
        "-vf", "setparams=range=tv:color_primaries=bt2020:"
               "color_trc=arib-std-b67:colorspace=bt2020nc",
        "-c:v", "libx264", "-pix_fmt", "yuv420p10le",
        "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
        "-colorspace", "bt2020nc", "-color_range", "tv",
        "-c:a", "aac", "-shortest", path,
    ])
    return path


def _make_sdr_clip(path: str) -> str:
    ffutil.run([
        "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", path,
    ])
    return path


def test_is_hdr_detects_hlg_bt2020(tmp_path):
    hdr = _make_hdr_clip(str(tmp_path / "hdr.mp4"))
    sdr = _make_sdr_clip(str(tmp_path / "sdr.mp4"))
    assert ffutil.is_hdr(hdr) is True
    assert ffutil.is_hdr(sdr) is False


def test_render_single_tonemaps_hdr_to_tagged_bt709(tmp_path):
    src = _make_hdr_clip(str(tmp_path / "hdr.mp4"))
    out = str(tmp_path / "out.mp4")
    render.render_single([Interval(0.2, 1.0), Interval(1.2, 1.8)], src,
                         str(tmp_path / "work"), out)
    c = ffutil.probe_color(out)
    assert c["pix_fmt"] == "yuv420p"
    assert c["color_primaries"] == "bt709"
    assert c["color_transfer"] == "bt709"
    assert c["color_space"] == "bt709"
    assert c["color_range"] == "tv"


def test_render_multicam_mixed_sdr_hdr_cameras(tmp_path):
    # Realistic worst case: one phone shoots HDR, the other SDR. Only the HDR
    # camera's segments go through the tonemap chain; the final concat must
    # still be uniformly tagged bt709.
    cam1 = _make_sdr_clip(str(tmp_path / "cam1.mp4"))
    cam2 = _make_hdr_clip(str(tmp_path / "cam2.mp4"))
    edl = EDL(segments=[Segment(0.0, 0.8, "cam1"), Segment(0.8, 1.6, "cam2")],
              fps=25.0)
    out = str(tmp_path / "out.mp4")
    render.render(edl, {"cam1": cam1, "cam2": cam2}, str(tmp_path / "work"), out)
    c = ffutil.probe_color(out)
    assert c["pix_fmt"] == "yuv420p"
    assert c["color_primaries"] == "bt709"
    assert c["color_transfer"] == "bt709"
    assert c["color_space"] == "bt709"


def test_render_single_tags_sdr_output_explicitly(tmp_path):
    # SDR input skips the tonemap chain but the output must still carry
    # explicit bt709 tags so players never guess.
    src = _make_sdr_clip(str(tmp_path / "sdr.mp4"))
    out = str(tmp_path / "out.mp4")
    render.render_single([Interval(0.0, 1.5)], src, str(tmp_path / "work"), out)
    c = ffutil.probe_color(out)
    assert c["color_primaries"] == "bt709"
    assert c["color_transfer"] == "bt709"
    assert c["color_space"] == "bt709"
