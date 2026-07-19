"""Anchor-phrase -> time-window resolution (the PodCut principle, generalized
from B-roll placement): the AI names a PHRASE from what was actually said --
never a timecode. This resolves that phrase against word-level timestamps.
Exact match preferred; fuzzy match (>=0.8) as a fallback; otherwise the spot
is unresolved and MUST be flagged for human placement, never guessed."""
import difflib

from dictionary import load_dictionary, correct_words, normalize_text  # noqa: E402 -- per-reel folders

FUZZY_THRESHOLD = 0.8
_, _CORRECTIONS = load_dictionary()


def _norm(s):
    return s.strip().strip(".,!?;:\"'").lower()


def resolve_anchor(words, phrase, pad_before=0.15, pad_after=0.6):
    """words: [{"text","start","end"}, ...] on the OUTPUT timeline (e.g. from
    assembled.transcript.json). phrase: the words this B-roll/document/card
    ties to, as spoken (not necessarily verbatim-cased).

    Both `words` and `phrase` are run through the SAME domain-term dictionary
    (reels/dictionary.py) before matching -- a defense-in-depth pass
    independent of build_base.py's own correction step, so a domain term
    (e.g. "Agentcis" ASR-mishears as "agent cs") can't sink a fuzzy match
    below FUZZY_THRESHOLD just because it landed here uncorrected, or because
    an anchor_phrase was written using the correct spelling while an
    uncorrected transcript still has the split/mangled ASR version. Word-
    MERGING (not just text substitution) is used on `words` specifically so a
    2-token mishearing collapses to the same single token the phrase-side
    correction produces -- otherwise the two sides could still disagree on
    word COUNT even after their text matches.

    Returns (start, end, score). start/end are None if no candidate window
    clears FUZZY_THRESHOLD -- the caller must flag this for human placement
    rather than fall back to a guessed number."""
    words, _log = correct_words(words, _CORRECTIONS)
    phrase = normalize_text(phrase, _CORRECTIONS)

    target = [_norm(w) for w in phrase.split() if _norm(w)]
    n = len(target)
    if n == 0 or len(words) < n:
        return None, None, 0.0

    target_str = " ".join(target)
    best_score, best_start, best_end = 0.0, None, None
    for i in range(len(words) - n + 1):
        window_str = " ".join(_norm(w["text"]) for w in words[i:i + n])
        score = difflib.SequenceMatcher(None, target_str, window_str).ratio()
        if score > best_score:
            best_score = score
            best_start = words[i]["start"]
            best_end = words[i + n - 1]["end"]

    if best_score >= FUZZY_THRESHOLD:
        return round(best_start - pad_before, 3), round(best_end + pad_after, 3), best_score
    return None, None, best_score
