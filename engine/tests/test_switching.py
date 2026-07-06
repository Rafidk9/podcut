"""Unit tests for the switching engine — pure logic, no media or API keys."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcut.config import SwitchConfig                       # noqa: E402
from podcut.models import (Turn, Annotation, Interval, Word, Transcript, EDL, Segment,  # noqa: E402
                           KIND_QUESTION, KIND_BACKCHANNEL)
from podcut import switching                                  # noqa: E402


def test_remap_transcript_to_edit_maps_and_drops():
    # seg1 orig 1.04-5.55 -> out 0.00; gap 5.98-7.28 removed; seg3 orig 7.28-13.38 -> out 4.94
    edl = EDL(segments=[Segment(1.04, 5.55, "cam1"), Segment(5.55, 5.98, "cam2"),
                        Segment(7.28, 13.38, "cam2")])
    t = Transcript(words=[
        Word(1.94, 2.04, "got", "A"),        # -> out 0.90
        Word(6.5, 6.8, "dropped", "A"),      # in removed gap -> dropped
        Word(7.36, 7.82, "honestly", "B"),   # -> out 5.02
    ])
    r = switching.remap_transcript_to_edit(t, edl)
    texts = [w.text for w in r.words]
    assert "dropped" not in texts
    assert abs(next(w for w in r.words if w.text == "got").start - 0.90) < 0.01
    assert abs(next(w for w in r.words if w.text == "honestly").start - 5.02) < 0.02


def full_keep(duration):
    return [Interval(0.0, duration)]


def camera_at(edl, t):
    for s in edl.segments:
        if s.src_start <= t < s.src_end:
            return s.camera
    return None


def test_follows_active_speaker():
    turns = [Turn(0, 6, "A"), Turn(6, 12, "B")]
    cfg = SwitchConfig(min_shot=1.0, anticipation_lead=0.0)
    edl = switching.build_edl(turns, [], full_keep(12), 12, cfg)
    assert camera_at(edl, 2) == "cam1"
    assert camera_at(edl, 9) == "cam2"


def test_anticipation_cut_fires_on_question():
    # A asks a question ending at 6.0; B answers starting 6.5.
    turns = [Turn(0, 6.0, "A"), Turn(6.5, 12, "B")]
    anns = [Annotation(start=3.0, end=6.0, kind=KIND_QUESTION, speaker="A",
                       subject_speaker="B")]
    cfg = SwitchConfig(min_shot=2.0, anticipation_lead=0.4, anticipation_timeout=1.5)
    edl = switching.build_edl(turns, anns, full_keep(12), 12, cfg)
    # Just before B actually speaks (during the tail of A's question), we should
    # already be on B's camera — the anticipation cut.
    assert camera_at(edl, 5.8) == "cam2"
    assert any(s.reason == "anticipation" for s in edl.segments)


def test_anticipation_fires_across_realistic_thinking_pause():
    # A real Scribe transcript showed a 1.46s gap between question end and answer.
    # With the default config this must still produce the anticipation cut.
    turns = [Turn(1.1, 5.9, "A"), Turn(7.36, 13.3, "B")]
    anns = [Annotation(start=3.6, end=5.9, kind=KIND_QUESTION, speaker="A",
                       subject_speaker="B")]
    cfg = SwitchConfig()  # defaults, incl. anticipation_timeout=2.5
    edl = switching.build_edl(turns, anns, full_keep(14), 14, cfg)
    assert any(s.reason == "anticipation" for s in edl.segments)
    assert camera_at(edl, 5.75) == "cam2"   # on B just before A finishes asking


def test_no_anticipation_when_answer_never_comes():
    # A asks but B never speaks -> we must NOT cut to a dead B shot.
    turns = [Turn(0, 6.0, "A"), Turn(6.2, 12, "A")]
    anns = [Annotation(start=3, end=6, kind=KIND_QUESTION, speaker="A",
                       subject_speaker="B")]
    cfg = SwitchConfig(min_shot=1.0, anticipation_timeout=1.0)
    edl = switching.build_edl(turns, anns, full_keep(12), 12, cfg)
    assert not any(s.reason == "anticipation" for s in edl.segments)
    assert camera_at(edl, 5.8) == "cam1"


def test_backchannel_does_not_switch():
    # B says a quick "yeah" (0.4s) in the middle of A's turn -> stay on A.
    turns = [Turn(0, 5, "A"), Turn(5.0, 5.4, "B"), Turn(5.4, 12, "A")]
    anns = [Annotation(start=5.0, end=5.4, kind=KIND_BACKCHANNEL, speaker="B")]
    cfg = SwitchConfig(min_shot=2.0, backchannel_max=1.0)
    edl = switching.build_edl(turns, anns, full_keep(12), 12, cfg)
    assert camera_at(edl, 5.2) == "cam1"


def test_min_shot_enforced():
    # Rapid alternation should be smoothed so no (non-anticipation) shot is tiny.
    turns = [Turn(0, 0.5, "A"), Turn(0.5, 1.0, "B"), Turn(1.0, 1.5, "A"),
             Turn(1.5, 8.0, "B")]
    cfg = SwitchConfig(min_shot=2.0, backchannel_max=0.0)
    edl = switching.build_edl(turns, [], full_keep(8), 8, cfg)
    for s in edl.segments:
        if s.reason != "anticipation":
            assert s.duration >= 2.0 - 1e-6 or s is edl.segments[-1]


def test_keep_intervals_confine_output():
    turns = [Turn(0, 10, "A")]
    keep = [Interval(2, 4), Interval(6, 8)]
    cfg = SwitchConfig(min_shot=1.0)
    edl = switching.build_edl(turns, [], keep, 10, cfg)
    covered = sum(s.duration for s in edl.segments)
    assert abs(covered - 4.0) < 0.2          # only the 2s + 2s kept windows
    assert camera_at(edl, 3) == "cam1"
    assert camera_at(edl, 5) is None         # removed region
