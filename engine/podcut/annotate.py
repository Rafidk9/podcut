"""The semantic layer: label conversational structure.

Per our design: **the AI annotates, it never emits timecodes.** It labels spans
of the transcript (by word index) with a `kind` and the `subject_speaker` (who
the moment points to next — e.g. who a question is aimed at). We then snap those
labels to the real word timestamps here, so timing stays frame-accurate.

Providers:
  * Anthropic (claude) if ANTHROPIC_API_KEY is set.
  * Otherwise a deterministic heuristic fallback (questions, backchannels,
    monologues) so the pipeline still produces anticipation cuts.
"""
from __future__ import annotations

import json
from typing import List

from .config import Providers
from .models import (
    Word, Transcript, Annotation,
    KIND_QUESTION, KIND_ANSWER, KIND_STATEMENT, KIND_MONOLOGUE,
    KIND_BACKCHANNEL, KIND_INTERRUPTION, KIND_PUNCHLINE,
)

BACKCHANNELS = {"yeah", "yep", "yes", "mhm", "mm", "uh-huh", "right", "ok",
                "okay", "sure", "exactly", "totally", "wow", "nice", "cool",
                "hmm", "gotcha", "true"}
QUESTION_WORDS = {"what", "why", "how", "when", "where", "who", "which",
                  "do", "does", "did", "is", "are", "can", "could", "would",
                  "will", "have", "has", "should"}


def annotate(transcript: Transcript, providers: Providers) -> List[Annotation]:
    if not transcript.words:
        return []
    mode = getattr(providers, "annotator", "auto")
    if mode == "heuristic":
        return _heuristic(transcript)
    if mode in ("auto", "anthropic") and providers.anthropic_key:
        try:
            return _anthropic(transcript, providers)
        except Exception as e:                      # noqa: BLE001
            print(f"[annotate] Anthropic failed ({e}); using heuristic fallback.")
    elif mode == "anthropic":
        print("[annotate] annotator=anthropic but no ANTHROPIC_API_KEY; using heuristic.")
    return _heuristic(transcript)


# --------------------------------------------------------------------------- #
# Heuristic fallback (no key)                                                  #
# --------------------------------------------------------------------------- #
def _sentences(words: List[Word]):
    """Group words into utterances split on speaker change or sentence-ending
    punctuation. Yields (start_idx, end_idx_inclusive)."""
    if not words:
        return
    start = 0
    for i, w in enumerate(words):
        end_here = w.text.strip().endswith((".", "?", "!"))
        speaker_change = (i + 1 < len(words) and words[i + 1].speaker != w.speaker)
        gap = (i + 1 < len(words) and words[i + 1].start - w.end > 0.8)
        if end_here or speaker_change or gap or i == len(words) - 1:
            yield start, i
            start = i + 1


def _norm(t: str) -> str:
    return t.strip().strip(".,!?;:").lower()


def _heuristic(transcript: Transcript) -> List[Annotation]:
    words = transcript.words
    anns: List[Annotation] = []
    speakers = transcript.speakers() or ["A"]
    other = {s: (speakers[(speakers.index(s) + 1) % len(speakers)] if len(speakers) > 1 else s)
             for s in speakers}

    for s, e in _sentences(words):
        span = words[s:e + 1]
        if not span:
            continue
        spk = span[0].speaker or "A"
        text_words = [_norm(w.text) for w in span if _norm(w.text)]
        dur = span[-1].end - span[0].start
        joined = " ".join(text_words)

        is_backchannel = len(text_words) <= 2 and all(t in BACKCHANNELS for t in text_words)
        is_question = span[-1].text.strip().endswith("?") or (
            text_words and text_words[0] in QUESTION_WORDS)

        if is_backchannel:
            kind, subj = KIND_BACKCHANNEL, None
        elif is_question:
            kind, subj = KIND_QUESTION, other.get(spk, spk)
        elif dur >= 12.0:
            kind, subj = KIND_MONOLOGUE, None
        else:
            kind, subj = KIND_STATEMENT, None

        anns.append(Annotation(start=span[0].start, end=span[-1].end,
                               kind=kind, speaker=spk, subject_speaker=subj,
                               note=joined[:80]))
    return anns


# --------------------------------------------------------------------------- #
# Anthropic provider                                                           #
# --------------------------------------------------------------------------- #
_SYSTEM = """You are a video editor's assistant. You are given a podcast transcript as a
numbered list of words with speaker labels. Segment it into conversational spans
and label each. Return STRICT JSON only.

For each span return: {"start_word": int, "end_word": int, "kind": one of
["statement","question","answer","monologue","backchannel","interruption","punchline"],
"speaker": "<label>", "subject_speaker": "<label or null>"}.

Rules:
- "question": someone asking; set subject_speaker to who should answer next.
- "backchannel": brief "yeah/mhm/right" — the editor will NOT cut for these.
- "monologue": one speaker holding the floor a long time.
- "punchline": a landed joke or emotional beat; hold on the speaker.
- Never invent timecodes. Only reference word indices given.
Return {"spans": [ ... ]} and nothing else."""


_ALLOWED_KINDS = {
    KIND_STATEMENT, KIND_QUESTION, KIND_ANSWER, KIND_MONOLOGUE,
    KIND_BACKCHANNEL, KIND_INTERRUPTION, KIND_PUNCHLINE,
}


def parse_spans(raw_json: str, transcript: Transcript) -> List[Annotation]:
    """Turn the model's JSON (a {"spans":[...]} object, possibly fenced) into
    validated Annotations snapped to real word timestamps. Kept separate from the
    network call so it can be unit-tested offline."""
    words = transcript.words
    n = len(words)
    if not n:
        return []
    # tolerate code fences / prose around the JSON object
    s, e = raw_json.find("{"), raw_json.rfind("}")
    if s < 0 or e < 0:
        return []
    spans = json.loads(raw_json[s:e + 1]).get("spans", [])
    valid_speakers = set(transcript.speakers())

    anns: List[Annotation] = []
    for sp in spans:
        try:
            i = max(0, min(n - 1, int(sp["start_word"])))
            j = max(0, min(n - 1, int(sp["end_word"])))
        except (KeyError, TypeError, ValueError):
            continue
        if j < i:
            i, j = j, i
        kind = str(sp.get("kind", KIND_STATEMENT)).lower()
        if kind not in _ALLOWED_KINDS:
            kind = KIND_STATEMENT
        subj = sp.get("subject_speaker")
        if subj in (None, "null", "None", ""):
            subj = None
        elif valid_speakers and subj not in valid_speakers:
            subj = None  # model named a speaker we don't have
        anns.append(Annotation(
            start=words[i].start, end=words[j].end, kind=kind,
            speaker=sp.get("speaker") or (words[i].speaker or "A"),
            subject_speaker=subj,
            note=" ".join(w.text for w in words[i:j + 1])[:80],
        ))
    return anns


def _anthropic(transcript: Transcript, providers: Providers) -> List[Annotation]:
    import anthropic  # noqa: PLC0415

    words = transcript.words
    numbered = "\n".join(f"{i}\t[{w.speaker or '?'}]\t{w.text}" for i, w in enumerate(words))
    client = anthropic.Anthropic(api_key=providers.anthropic_key)
    msg = client.messages.create(
        model=providers.anthropic_model,
        max_tokens=8000,
        temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": numbered}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    anns = parse_spans(raw, transcript)
    if not anns:                      # empty/garbled response -> heuristic
        raise RuntimeError("Anthropic returned no usable spans")
    return anns
