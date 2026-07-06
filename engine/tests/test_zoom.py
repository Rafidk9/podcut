"""Offline tests for annotation-driven zoom (no rendering/keys needed)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcut.config import ZoomConfig                                    # noqa: E402
from podcut.models import (Annotation, EDL, Segment,                    # noqa: E402
                           KIND_PUNCHLINE, KIND_MONOLOGUE, KIND_QUESTION)
from podcut import zoom                                                 # noqa: E402


def _identity_edl(duration=30.0):
    return EDL(segments=[Segment(0.0, duration, "cam1")])


def test_remap_time_snaps_forward_through_cut_region():
    edl = EDL(segments=[Segment(0.0, 2.0, "cam1"), Segment(5.0, 8.0, "cam1")])
    assert abs(zoom.remap_time_to_edit(1.0, edl) - 1.0) < 0.01     # inside seg1
    assert abs(zoom.remap_time_to_edit(3.5, edl) - 2.0) < 0.01     # in the cut -> snaps to seg2 start (out=2.0)
    assert abs(zoom.remap_time_to_edit(6.0, edl) - 3.0) < 0.01     # inside seg2 (out = 2.0 + (6-5))


def test_punchline_produces_quick_punch_in():
    ann = [Annotation(start=4.0, end=5.0, kind=KIND_PUNCHLINE, speaker="A")]
    cfg = ZoomConfig()
    events = zoom.compute_zoom_events(ann, _identity_edl(), cfg)
    assert len(events) == 1
    e = events[0]
    assert e.reason == "punchline"
    assert e.scale == cfg.punchline_scale
    assert e.start < e.peak < e.release < e.end


def test_question_with_subject_produces_anticipation_zoom_peaking_at_answer():
    ann = [Annotation(start=1.0, end=6.0, kind=KIND_QUESTION, speaker="A", subject_speaker="B")]
    cfg = ZoomConfig()
    events = zoom.compute_zoom_events(ann, _identity_edl(), cfg)
    assert len(events) == 1
    e = events[0]
    assert e.reason == "anticipation"
    assert abs(e.peak - 6.0) < 0.01     # zoom peaks right at the question's end (the cut point)


def test_question_without_subject_speaker_produces_no_zoom():
    ann = [Annotation(start=1.0, end=6.0, kind=KIND_QUESTION, speaker="A", subject_speaker=None)]
    events = zoom.compute_zoom_events(ann, _identity_edl(), ZoomConfig())
    assert events == []


def test_monologue_produces_slow_zoom_across_the_whole_span():
    ann = [Annotation(start=0.0, end=20.0, kind=KIND_MONOLOGUE, speaker="A")]
    cfg = ZoomConfig()
    events = zoom.compute_zoom_events(ann, _identity_edl(30.0), cfg)
    assert len(events) == 1
    e = events[0]
    assert e.reason == "monologue"
    assert abs(e.start - 0.0) < 0.01 and abs(e.peak - 20.0) < 0.01


def test_overlapping_events_resolved_by_priority_punchline_wins():
    # A punchline lands right in the middle of a monologue span -> punchline wins.
    ann = [
        Annotation(start=0.0, end=20.0, kind=KIND_MONOLOGUE, speaker="A"),
        Annotation(start=9.0, end=9.5, kind=KIND_PUNCHLINE, speaker="A"),
    ]
    events = zoom.compute_zoom_events(ann, _identity_edl(30.0), ZoomConfig())
    reasons = [e.reason for e in events]
    assert "punchline" in reasons
    # the monologue event must not overlap the accepted punchline event
    punch = next(e for e in events if e.reason == "punchline")
    for e in events:
        if e.reason != "punchline":
            assert e.end <= punch.start or e.start >= punch.end


def test_disabled_config_produces_no_events():
    ann = [Annotation(start=0.0, end=1.0, kind=KIND_PUNCHLINE, speaker="A")]
    cfg = ZoomConfig(enabled=False)
    assert zoom.compute_zoom_events(ann, _identity_edl(), cfg) == []
