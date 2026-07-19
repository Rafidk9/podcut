"""Unit tests for anchor_phrase.resolve_anchor() -- the "AI names a phrase,
code resolves it to a timestamp, or refuses" pattern every reel-editing
feature (badges, lists, hero words, documents, SFX timing) depends on.
No fixtures beyond plain word lists -- no ffmpeg/HyperFrames/media needed."""
from anchor_phrase import resolve_anchor, FUZZY_THRESHOLD


def words(*specs):
    """specs: [(text, start, end), ...] -> [{"text","start","end"}, ...]."""
    return [{"text": t, "start": s, "end": e} for t, s, e in specs]


TRANSCRIPT = words(
    ("If", 0.0, 0.2), ("you're", 0.2, 0.4), ("an", 0.4, 0.5),
    ("international", 0.5, 1.0), ("student,", 1.0, 1.3),
    ("stop", 1.4, 1.6), ("scrolling.", 1.65, 2.1),
    ("Every", 2.2, 2.4), ("year,", 2.4, 2.6), ("hundreds", 2.7, 3.1),
    ("of", 3.1, 3.2), ("students", 3.2, 3.6),
    ("stop", 4.0, 4.2), ("scrolling.", 4.25, 4.7),  # a second, later occurrence
)


def test_exact_match_resolves_with_full_confidence():
    start, end, score = resolve_anchor(TRANSCRIPT, "stop scrolling",
                                        pad_before=0.15, pad_after=0.6)
    assert score == 1.0
    # first occurrence: "stop" starts at 1.4, "scrolling." ends at 2.1
    assert start == round(1.4 - 0.15, 3)
    assert end == round(2.1 + 0.6, 3)


def test_case_and_punctuation_are_ignored():
    start, end, score = resolve_anchor(TRANSCRIPT, "Stop, Scrolling!!")
    assert score == 1.0
    assert start is not None


def test_first_occurrence_wins_when_tied():
    """Two identical spoken phrases -- resolve_anchor has no surrounding-
    context awareness, so ties resolve to whichever window it scans first."""
    start, _end, score = resolve_anchor(TRANSCRIPT, "stop scrolling", pad_before=0)
    assert score == 1.0
    assert start == 1.4  # the FIRST "stop scrolling", not the one at 4.0


def test_fuzzy_match_above_threshold_still_resolves():
    # "student" (singular) vs the transcript's "student," -- normalization
    # strips punctuation but not the trailing content difference here, so
    # this exercises the fuzzy (not exact-ratio-1.0) path.
    start, end, score = resolve_anchor(TRANSCRIPT, "international students")
    assert score >= FUZZY_THRESHOLD
    assert start is not None and end is not None


def test_below_threshold_returns_none_never_a_guess():
    start, end, score = resolve_anchor(TRANSCRIPT, "completely unrelated phrase")
    assert start is None
    assert end is None
    assert score < FUZZY_THRESHOLD


def test_empty_phrase_returns_none():
    start, end, score = resolve_anchor(TRANSCRIPT, "")
    assert (start, end, score) == (None, None, 0.0)


def test_phrase_longer_than_transcript_returns_none():
    start, end, score = resolve_anchor(words(("hi", 0, 1)), "way more words than exist here")
    assert (start, end, score) == (None, None, 0.0)


def test_padding_defaults_applied():
    start, end, score = resolve_anchor(TRANSCRIPT, "stop scrolling")
    assert score == 1.0
    assert start == round(1.4 - 0.15, 3)   # default pad_before=0.15
    assert end == round(2.1 + 0.6, 3)      # default pad_after=0.6


def test_custom_padding_overrides_defaults():
    start, end, _score = resolve_anchor(TRANSCRIPT, "stop scrolling",
                                         pad_before=0.05, pad_after=0.2)
    assert start == round(1.4 - 0.05, 3)
    assert end == round(2.1 + 0.2, 3)


def test_dictionary_correction_resolves_a_match_that_would_otherwise_skip():
    """"Agentcis" ASR-mishears as two words ("agent cs") -- without the
    dictionary pass (reels/dictionary.py, dictionary.txt) this scores 0.786
    against a 1-word phrase, just under FUZZY_THRESHOLD (0.8). resolve_anchor
    normalizes both sides through the SAME dictionary before scoring, so this
    must resolve instead of skip. See dictionary.txt for the seeded pair."""
    mishearing = words(("Our", 0.0, 0.2), ("agent", 0.2, 0.5), ("cs", 0.5, 0.7),
                        ("platform.", 0.7, 1.0))
    start, end, score = resolve_anchor(mishearing, "Agentcis platform")
    assert score >= FUZZY_THRESHOLD
    assert start is not None and end is not None
