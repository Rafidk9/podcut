"""Offline tests for caption grouping (no HyperFrames/API keys needed)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcut.models import Word                          # noqa: E402
from podcut.integrations import _compute_word_groups     # noqa: E402


def _w(text, start, speaker="A"):
    return Word(start=start, end=start + 0.3, text=text, speaker=speaker)


def test_groups_capped_at_four_words():
    words = [_w(t, i * 0.4) for i, t in
             enumerate(["one", "two", "three", "four", "five", "six"])]
    groups = _compute_word_groups(words)
    for g in groups:
        assert (g[1] - g[0] + 1) <= 4


def test_sentence_end_forces_a_break():
    # "Hi there." "Now what?" — each sentence must be its own group; the end of
    # sentence 1 and start of sentence 2 must never share a card.
    words = [_w("Hi", 0.0), _w("there.", 0.4), _w("Now", 1.0), _w("what?", 1.4)]
    groups = _compute_word_groups(words)
    assert groups == [[0, 1], [2, 3]]


def test_short_sentence_does_not_absorb_next_sentence():
    # A 1-word sentence is well under max_words=4, but must still end its own
    # group rather than merging with the words that follow.
    words = [_w("Okay.", 0.0), _w("So", 0.6), _w("then", 1.0), _w("what.", 1.4)]
    groups = _compute_word_groups(words)
    assert groups[0] == [0, 0]           # "Okay." alone
    assert groups[1] == [1, 3]           # "So then what." separate


def test_long_sentence_splits_but_still_ends_on_punctuation():
    words = [_w(t, i * 0.3) for i, t in enumerate(
        ["This", "sentence", "has", "many", "many", "words", "here."])]
    groups = _compute_word_groups(words)
    # last group of the sentence must end exactly at the punctuation word
    assert words[groups[-1][1]].text == "here."
    for g in groups:
        assert (g[1] - g[0] + 1) <= 4
