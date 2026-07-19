"""Domain-term dictionary: corrects common ASR mishearings of PFEC's own
vocabulary (agency name, visa subclasses, registration terms) before they
ever reach the timeline transcript or anchor-phrase matching. One shared
file (reels/dictionary.txt) across all reels -- these are PFEC's fixed
domain terms, not something that varies per reel.

File format (one entry per line, '#' starts a comment, blank lines ignored):
    TERM             a domain term, kept as-is -- informational/reference
                     only, does not by itself change matching
    wrong=>right     case-insensitive correction. "wrong" can be more than
                     one word ("marn number=>MARN") -- matched as whole
                     tokens, never a partial-word substring.
"""
import os
import re

_DICT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dictionary.txt")
_warned = False


def load_dictionary(path=_DICT_PATH):
    """Returns (terms: list[str], corrections: [(wrong, right), ...]),
    corrections sorted longest-wrong-phrase-first (so a longer match is tried
    before a shorter one that could otherwise partially consume it).

    Missing file -> ONE warning, empty dictionary, never an error -- every
    reel still builds without it, same "opt-in with a loud warning" rule as
    the rest of this pipeline (e.g. content_check.py)."""
    global _warned
    if not os.path.isfile(path):
        if not _warned:
            print(f"  [dictionary] WARNING: {path} not found -- proceeding with no "
                  "domain-term corrections (transcript mishearings of PFEC/visa "
                  "subclass terms won't be auto-fixed).")
            _warned = True
        return [], []
    terms, corrections = [], []
    for line in open(path, encoding="utf-8"):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if "=>" in line:
            wrong, _, right = line.partition("=>")
            wrong, right = wrong.strip(), right.strip()
            if wrong and right:
                corrections.append((wrong, right))
        else:
            terms.append(line)
    corrections.sort(key=lambda pair: -len(pair[0].split()))
    return terms, corrections


def _norm_tok(t):
    return t.strip().strip(".,!?;:\"'").lower()


def correct_words(words, corrections):
    """words: [{"text","start","end", ...}, ...] in time order. Merges N
    consecutive words whose normalized text matches a (possibly multi-word)
    "wrong" phrase into ONE word carrying the "right" text and
    start=first/end=last of the consumed span -- so a 2-word mishearing like
    "agent cs" becomes exactly one corrected word, not two, keeping any
    downstream word-count-based logic (2-word caption chunking, anchor
    matching) consistent with what was actually said.

    Case-insensitive, whole-token match only (can't match inside a word).
    Preserves the trailing sentence punctuation of the last consumed word.

    Returns (new_words, correction_log) where correction_log is
    [(wrong_matched, right, start, end), ...] in the order corrections were
    applied, for the caller to log."""
    if not corrections:
        return words, []

    out, log = [], []
    i, n = 0, len(words)
    while i < n:
        matched = None
        for wrong, right in corrections:
            wrong_toks = wrong.lower().split()
            k = len(wrong_toks)
            if i + k > n:
                continue
            if [_norm_tok(words[i + j]["text"]) for j in range(k)] == wrong_toks:
                matched = (wrong, right, k)
                break
        if matched:
            wrong, right, k = matched
            last_text = words[i + k - 1]["text"]
            trail = last_text[len(last_text.rstrip(".,!?;:")):]
            new_word = {"text": right + trail, "start": words[i]["start"],
                        "end": words[i + k - 1]["end"]}
            if "speaker" in words[i]:
                new_word["speaker"] = words[i]["speaker"]
            out.append(new_word)
            log.append((wrong, right, new_word["start"], new_word["end"]))
            i += k
        else:
            out.append(words[i])
            i += 1
    return out, log


def normalize_text(text, corrections):
    """Plain string-level correction (regex, case-insensitive, whole-phrase
    via \\b boundaries, tolerant of any whitespace run between the wrong
    phrase's words) -- for comparison contexts (anchor_phrase.py) that need
    consistent text before a similarity score, not word-count-changing
    merges. Idempotent: safe to call on text that's already been through
    correct_words()."""
    for wrong, right in corrections:
        pattern = r"\b" + r"\s+".join(re.escape(w) for w in wrong.split()) + r"\b"
        text = re.sub(pattern, right, text, flags=re.IGNORECASE)
    return text
