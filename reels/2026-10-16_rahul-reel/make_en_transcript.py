"""Hinglish speech -> ENGLISH caption transcript, on the original word timings.

Same approach as 2026-10-05_rahul-visa-changes-hindi/make_en_transcript.py
(user wants English captions on Rahul's Hinglish reels). ElevenLabs' output is
kept as work/raw.transcript.hi.json (source of truth); work/raw.transcript.json
is rewritten: English words pass through with exact timing, each Hindi phrase
in CHUNKS is replaced by its translation spread across that phrase's audio
window proportionally to word length.

Run AFTER `podcut transcribe`, BEFORE build_base.py. Idempotent.
"""
import json
import os
import shutil

REEL = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(REEL, "work")
CLIP = "raw"

# (first_index, last_index, english) over the .hi.json word list
CHUNKS = [
    (0, 8, "Your occupation is not on the NSW skills list?"),   # आपका occupation NSW की skill list में नहीं है
    (13, 16, "What does NSW do?"),                              # NSW क्या करता है?
    (17, 23, "They don't publish individual occupation codes."),  # वो individual occupation code publish नहीं करते।
]
# English ASR tidy-ups (index -> replacement text, None = drop the word)
FIXES = {}


def spread(words, a, b, text):
    t0, t1 = words[a]["start"], words[b]["end"]
    toks = text.split()
    total = sum(len(t) + 1 for t in toks)
    out, t = [], t0
    for tok in toks:
        d = (t1 - t0) * (len(tok) + 1) / total
        out.append({"text": tok, "start": round(t, 3), "end": round(t + d - 0.02, 3),
                    "speaker": "A"})
        t += d
    return out


def main():
    src = os.path.join(WORK, f"{CLIP}.transcript.json")
    hi = os.path.join(WORK, f"{CLIP}.transcript.hi.json")
    if not os.path.exists(hi):
        shutil.copy2(src, hi)
    d = json.load(open(hi, encoding="utf-8"))
    words = d["words"]
    # locate "a" in "like a coaches" and "including." by text, not hard index
    for i, w in enumerate(words):
        if w["text"] == "a" and i + 1 < len(words) and words[i + 1]["text"] == "coaches":
            FIXES[i] = None
        if w["text"].startswith("including"):
            FIXES[i] = None
    starts = {a: (b, txt) for a, b, txt in CHUNKS}
    out, i = [], 0
    while i < len(words):
        if i in starts:
            b, txt = starts[i]
            out += spread(words, i, b, txt)
            i = b + 1
            continue
        if i in FIXES:
            if FIXES[i] is not None:
                out.append({**words[i], "text": FIXES[i]})
        else:
            out.append(words[i])
        i += 1
    for w in out:
        if any("ऀ" <= ch <= "ॿ" for ch in w["text"]):
            raise SystemExit(f"untranslated Devanagari left: {w}")
    json.dump({"provider": d.get("provider", "elevenlabs") + "+en", "words": out},
              open(src, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"wrote {src}: {len(out)} words")


if __name__ == "__main__":
    main()
