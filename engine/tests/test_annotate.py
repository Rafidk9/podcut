"""Offline tests for the Anthropic annotation parser (no API key needed)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcut.models import Word, Transcript, KIND_QUESTION, KIND_STATEMENT  # noqa: E402
from podcut import annotate  # noqa: E402


def _transcript():
    words = [
        Word(0.0, 0.4, "What", "A"), Word(0.4, 0.7, "happens", "A"), Word(0.7, 1.0, "next?", "A"),
        Word(2.0, 2.4, "It", "B"), Word(2.4, 2.8, "improves.", "B"),
    ]
    return Transcript(words=words, provider="test")


def test_parse_basic_span_snaps_to_timestamps():
    raw = '{"spans":[{"start_word":0,"end_word":2,"kind":"question","speaker":"A","subject_speaker":"B"}]}'
    anns = annotate.parse_spans(raw, _transcript())
    assert len(anns) == 1
    a = anns[0]
    assert a.kind == KIND_QUESTION
    assert a.subject_speaker == "B"
    assert a.start == 0.0 and a.end == 1.0     # snapped to words 0..2


def test_parse_tolerates_code_fences_and_prose():
    raw = 'Here is the result:\n```json\n{"spans":[{"start_word":3,"end_word":4,"kind":"answer","speaker":"B"}]}\n```'
    anns = annotate.parse_spans(raw, _transcript())
    assert len(anns) == 1 and anns[0].speaker == "B"


def test_parse_validates_bad_kind_and_unknown_speaker():
    raw = '{"spans":[{"start_word":0,"end_word":1,"kind":"banana","speaker":"A","subject_speaker":"Z"}]}'
    anns = annotate.parse_spans(raw, _transcript())
    assert anns[0].kind == KIND_STATEMENT       # unknown kind -> statement
    assert anns[0].subject_speaker is None       # "Z" isn't a real speaker


def test_parse_clamps_out_of_range_indices():
    raw = '{"spans":[{"start_word":-5,"end_word":99,"kind":"monologue","speaker":"A"}]}'
    anns = annotate.parse_spans(raw, _transcript())
    assert anns[0].start == 0.0 and anns[0].end == 2.8   # clamped to 0..last


def test_parse_empty_or_garbage_returns_empty():
    assert annotate.parse_spans("no json here", _transcript()) == []
    assert annotate.parse_spans('{"spans":[]}', _transcript()) == []
