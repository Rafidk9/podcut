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


def test_seed_file_loads_marn_correction():
    terms, corrections = load_dictionary()
    assert any(w == "marn number" and r == "MARN" for w, r in corrections)


def test_correct_words_merges_multiword_mishearing_and_keeps_timing():
    w = words(("Our", 0.0, 0.2), ("acme", 0.2, 0.5), ("co", 0.5, 0.7), ("platform.", 0.7, 1.0))
    corrected, log = correct_words(w, [("acme co", "AcmeCo")])
    assert [x["text"] for x in corrected] == ["Our", "AcmeCo", "platform."]
    assert corrected[1]["start"] == 0.2
    assert corrected[1]["end"] == 0.7
    assert log == [("acme co", "AcmeCo", 0.2, 0.7)]


def test_correct_words_preserves_trailing_punctuation():
    w = words(("acme", 0.0, 0.2), ("co,", 0.2, 0.4))
    corrected, _log = correct_words(w, [("acme co", "AcmeCo")])
    assert corrected[0]["text"] == "AcmeCo,"


def test_correct_words_case_insensitive():
    w = words(("Acme", 0.0, 0.2), ("CO", 0.2, 0.4))
    corrected, _log = correct_words(w, [("acme co", "AcmeCo")])
    assert corrected[0]["text"] == "AcmeCo"


def test_correct_words_no_corrections_is_a_no_op():
    w = words(("hello", 0.0, 0.2))
    corrected, log = correct_words(w, [])
    assert corrected == w
    assert log == []


def test_correct_words_leaves_non_matching_words_untouched():
    w = words(("completely", 0.0, 0.3), ("unrelated", 0.3, 0.6))
    corrected, log = correct_words(w, [("acme co", "AcmeCo")])
    assert corrected == w
    assert log == []


def test_normalize_text_string_level_whole_phrase():
    assert normalize_text("our acme co platform", [("acme co", "AcmeCo")]) == "our AcmeCo platform"


def test_normalize_text_case_insensitive_and_flexible_whitespace():
    assert normalize_text("Our ACME   CO Platform", [("acme co", "AcmeCo")]) == "Our AcmeCo Platform"


def test_normalize_text_does_not_match_partial_words():
    # "co" inside "coat" must not be treated as the token "co".
    assert normalize_text("check the coat", [("co", "XX")]) == "check the coat"
