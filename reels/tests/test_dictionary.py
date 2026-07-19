"""Unit tests for dictionary.py -- the domain-term correction pass that fixes
known ASR mishearings of PFEC's vocabulary before it reaches the timeline
transcript or anchor-phrase matching."""
import os

from dictionary import load_dictionary, correct_words, normalize_text


def words(*specs):
    return [{"text": t, "start": s, "end": e} for t, s, e in specs]


def test_missing_file_warns_once_and_returns_empty(tmp_path):
    terms, corrections = load_dictionary(path=str(tmp_path / "nope.txt"))
    assert terms == []
    assert corrections == []


def test_seed_file_loads_agentcis_correction():
    terms, corrections = load_dictionary()
    assert any(w == "agent cs" and r == "Agentcis" for w, r in corrections)


def test_correct_words_merges_multiword_mishearing_and_keeps_timing():
    w = words(("Our", 0.0, 0.2), ("agent", 0.2, 0.5), ("cs", 0.5, 0.7), ("platform.", 0.7, 1.0))
    corrected, log = correct_words(w, [("agent cs", "Agentcis")])
    assert [x["text"] for x in corrected] == ["Our", "Agentcis", "platform."]
    assert corrected[1]["start"] == 0.2
    assert corrected[1]["end"] == 0.7
    assert log == [("agent cs", "Agentcis", 0.2, 0.7)]


def test_correct_words_preserves_trailing_punctuation():
    w = words(("agent", 0.0, 0.2), ("cs,", 0.2, 0.4))
    corrected, _log = correct_words(w, [("agent cs", "Agentcis")])
    assert corrected[0]["text"] == "Agentcis,"


def test_correct_words_case_insensitive():
    w = words(("Agent", 0.0, 0.2), ("CS", 0.2, 0.4))
    corrected, _log = correct_words(w, [("agent cs", "Agentcis")])
    assert corrected[0]["text"] == "Agentcis"


def test_correct_words_no_corrections_is_a_no_op():
    w = words(("hello", 0.0, 0.2))
    corrected, log = correct_words(w, [])
    assert corrected == w
    assert log == []


def test_correct_words_leaves_non_matching_words_untouched():
    w = words(("completely", 0.0, 0.3), ("unrelated", 0.3, 0.6))
    corrected, log = correct_words(w, [("agent cs", "Agentcis")])
    assert corrected == w
    assert log == []


def test_normalize_text_string_level_whole_phrase():
    assert normalize_text("our agent cs platform", [("agent cs", "Agentcis")]) == "our Agentcis platform"


def test_normalize_text_case_insensitive_and_flexible_whitespace():
    assert normalize_text("Our AGENT   CS Platform", [("agent cs", "Agentcis")]) == "Our Agentcis Platform"


def test_normalize_text_does_not_match_partial_words():
    # "cs" inside "docs" must not be treated as the token "cs".
    assert normalize_text("check the docs", [("cs", "XX")]) == "check the docs"
