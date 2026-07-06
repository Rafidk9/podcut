"""Tests for the plan/review checkpoint — pure logic, no media or API keys."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcut import plan as plan_mod                       # noqa: E402
from podcut.models import EDL, Interval, Segment, Transcript, Word  # noqa: E402


def _t(words):
    return Transcript(words=[Word(s, e, txt, "A") for s, e, txt in words])


def test_cuts_from_keep_classifies_lead_filler_pause_tail():
    # timeline: [lead 0-1][keep 1-3][um cut 3-3.5][keep 3.5-5][silent 5-6][keep 6-8][tail 8-10]
    keep = [Interval(1.0, 3.0), Interval(3.5, 5.0), Interval(6.0, 8.0)]
    t = _t([(1.2, 1.5, "hello"), (3.1, 3.4, "um"), (6.2, 6.5, "world")])
    cuts = plan_mod._cuts_from_keep(keep, 10.0, t)
    kinds = [c["kind"] for c in cuts]
    assert kinds == ["lead", "filler", "pause", "tail"]
    assert cuts[1]["text"] == "um"
    assert cuts[2]["text"] == ""
    assert all(c["restore"] is False for c in cuts)


def test_merged_keep_restores_a_cut_and_reunites_intervals():
    plan = {
        "keep": [{"start": 1.0, "end": 3.0}, {"start": 3.5, "end": 5.0}],
        "cuts": [{"start": 3.0, "end": 3.5, "kind": "filler", "text": "um",
                  "restore": True}],
    }
    merged = plan_mod._merged_keep(plan)
    # restoring the 3.0-3.5 cut must fuse both keeps into one interval
    assert len(merged) == 1
    assert abs(merged[0].start - 1.0) < 1e-6 and abs(merged[0].end - 5.0) < 1e-6


def test_merged_keep_without_restores_is_identity():
    plan = {
        "keep": [{"start": 1.0, "end": 3.0}, {"start": 3.5, "end": 5.0}],
        "cuts": [{"start": 3.0, "end": 3.5, "kind": "filler", "text": "um",
                  "restore": False}],
    }
    merged = plan_mod._merged_keep(plan)
    assert [(iv.start, iv.end) for iv in merged] == [(1.0, 3.0), (3.5, 5.0)]


def test_camera_override_splits_segment_at_edges():
    edl = EDL(segments=[Segment(0.0, 10.0, "cam1", "follow")])
    out = plan_mod._apply_camera_overrides(edl, [{"start": 4.0, "end": 6.0,
                                                  "camera": "cam2"}])
    assert [(s.src_start, s.src_end, s.camera) for s in out.segments] == [
        (0.0, 4.0, "cam1"), (4.0, 6.0, "cam2"), (6.0, 10.0, "cam1")]
    assert out.segments[1].reason == "user_override"


def test_camera_override_coalesces_now_identical_neighbours():
    edl = EDL(segments=[Segment(0.0, 4.0, "cam1", "follow"),
                        Segment(4.0, 6.0, "cam2", "follow"),
                        Segment(6.0, 10.0, "cam1", "follow")])
    # overriding the middle segment to cam1 must collapse all three into one
    out = plan_mod._apply_camera_overrides(edl, [{"start": 4.0, "end": 6.0,
                                                  "camera": "cam1"}])
    assert len(out.segments) == 1
    assert (out.segments[0].src_start, out.segments[0].src_end,
            out.segments[0].camera) == (0.0, 10.0, "cam1")


def test_camera_override_never_bridges_a_removed_gap():
    # Regression: segments here already have keep cuts applied — 3.0-4.5 is
    # REMOVED material. Overriding seg1 to cam2 makes it same-camera as seg2,
    # but they must NOT merge across the gap (that would re-insert cut footage
    # and lengthen the output).
    edl = EDL(segments=[Segment(0.5, 3.0, "cam1", "follow"),
                        Segment(4.5, 6.5, "cam2", "follow")])
    out = plan_mod._apply_camera_overrides(edl, [{"start": 0.5, "end": 3.0,
                                                  "camera": "cam2"}])
    assert [(s.src_start, s.src_end, s.camera) for s in out.segments] == [
        (0.5, 3.0, "cam2"), (4.5, 6.5, "cam2")]
    total = sum(s.src_end - s.src_start for s in out.segments)
    assert abs(total - 4.5) < 1e-6


def test_segment_previews_pull_words_in_range():
    edl = EDL(segments=[Segment(0.0, 2.0, "cam1"), Segment(2.0, 4.0, "cam2")])
    t = _t([(0.5, 0.8, "first"), (1.0, 1.3, "shot"), (2.5, 2.8, "second")])
    segs = plan_mod._plan_segments(edl, t)
    assert segs[0]["preview"] == "first shot"
    assert segs[1]["preview"] == "second"
    assert segs[0]["camera"] == "cam1"
