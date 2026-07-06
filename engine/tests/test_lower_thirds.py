"""Lower-third computation — pure logic, no media or API keys."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcut.plan import compute_lower_thirds               # noqa: E402
from podcut.models import EDL, Segment, Turn               # noqa: E402


def _turns():
    return [Turn(0.0, 5.0, "A"), Turn(5.0, 9.0, "B"), Turn(9.0, 12.0, "A")]


def test_one_plate_per_speaker_at_first_appearance_on_edited_timeline():
    # source: A-cam 1-3 (out 0.0), B-cam 4.5-6.5 (out 2.0), A-cam 8-10 (out 4.0)
    edl = EDL(segments=[Segment(1.0, 3.0, "cam1"), Segment(4.5, 6.5, "cam2"),
                        Segment(8.0, 10.0, "cam1")])
    events = compute_lower_thirds(edl, _turns(), {"A": "Alice", "B": "Bob"}, "podcast")
    assert [(e["name"], e["time"]) for e in events] == [("Alice", 0.2), ("Bob", 2.2)]


def test_unnamed_speaker_gets_no_plate():
    edl = EDL(segments=[Segment(1.0, 3.0, "cam1"), Segment(4.5, 6.5, "cam2")])
    events = compute_lower_thirds(edl, _turns(), {"B": "Bob"}, "podcast")
    assert [e["name"] for e in events] == ["Bob"]


def test_no_names_no_events():
    edl = EDL(segments=[Segment(1.0, 3.0, "cam1")])
    assert compute_lower_thirds(edl, _turns(), {}, "podcast") == []
    assert compute_lower_thirds(edl, _turns(), {"A": "  "}, "podcast") == []


def test_single_mode_shows_the_one_name_near_start():
    edl = EDL(segments=[Segment(0.5, 4.0, "v")])
    events = compute_lower_thirds(edl, [], {"A": "Alice"}, "single")
    assert len(events) == 1
    assert events[0]["name"] == "Alice"
    assert events[0]["time"] < 1.0


def test_speaker_camera_map_follows_turn_order_not_label_order():
    # B speaks first → B is cam1, A is cam2 (mirrors switching._default_map)
    turns = [Turn(0.0, 4.0, "B"), Turn(4.0, 8.0, "A")]
    edl = EDL(segments=[Segment(0.0, 4.0, "cam1"), Segment(4.0, 8.0, "cam2")])
    events = compute_lower_thirds(edl, turns, {"A": "Alice", "B": "Bob"}, "podcast")
    assert [(e["name"], e["time"]) for e in events] == [("Bob", 0.2), ("Alice", 4.2)]
