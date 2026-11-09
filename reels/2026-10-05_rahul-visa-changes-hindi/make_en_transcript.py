"""Hinglish speech -> ENGLISH caption transcript, on the original word timings.

Rahul speaks Hinglish; the user wants English captions (2026-10-06, replacing
the first cut's romanized Hinglish -- make_roman_transcript.py, now unused).
Same approach as the Sinhala reel's make_en_transcript.py: ElevenLabs' original
is kept as work/<clip>.transcript.hi.json (source of truth for timing) and
work/<clip>.transcript.json is rewritten in English.

Words he already speaks in English pass through untouched (exact timing).
Each Hindi phrase in CHUNKS is replaced by its English translation, spread
across that phrase's real audio window [w[a].start, w[b].end] proportionally
to word length. '1:00'/'2:00' -> '1'/'2' (user wants '1 PM').

Run AFTER `podcut transcribe`, BEFORE build_base.py. Idempotent.
"""
import json
import os
import shutil

REEL = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(REEL, "work")
CLIP = "IMG_0293"

# (first_index, last_index, english) over the .hi.json word list
CHUNKS = [
    (0, 2, "We know"),                                   # हमें पता है
    (3, 12, "you've been affected by the recent student visa changes"),
    (13, 16, "and stressed too."),                       # और परेशान भी हैं
    (17, 21, "Especially in the scenario"),              # और specially उस scenario में
    (22, 25, "when your student visa"),                  # जब आपका student visa
    (26, 33, "is about to expire very soon."),           # बहुत ही जल्दी expire होने जा रहा है।
    (60, 63, "Come and ask your questions."),            # आइए अपने questions पूछिए।
]
TIMES = {"1:00": "1", "2:00": "2"}


def spread(text, start, end, speaker):
    words = text.split()
    weights = [len(w) + 2 for w in words]
    total, t, out = sum(weights), start, []
    for w, k in zip(words, weights):
        d = (end - start) * k / total
        out.append({"start": round(t, 3), "end": round(t + d, 3), "text": w,
                    "speaker": speaker})
        t += d
    return out


def main():
    src = os.path.join(WORK, f"{CLIP}.transcript.json")
    hi = os.path.join(WORK, f"{CLIP}.transcript.hi.json")
    if not os.path.exists(hi):
        shutil.copy2(src, hi)
    d = json.load(open(hi, encoding="utf-8"))
    w = d["words"]
    starts = {a: (b, en) for a, b, en in CHUNKS}
    out, i = [], 0
    while i < len(w):
        if i in starts:
            b, en = starts[i]
            out += spread(en, w[i]["start"], w[b]["end"], w[i].get("speaker", "A"))
            i = b + 1
            continue
        x = dict(w[i])
        if any("ऀ" <= ch <= "ॿ" for ch in x["text"]):
            raise SystemExit(f"untranslated Hindi word {i}: {x['text']}")
        core = x["text"].rstrip(",.")
        if core in TIMES:
            x["text"] = TIMES[core] + x["text"][len(core):]
        out.append(x)
        i += 1
    d["words"] = out
    json.dump(d, open(src, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", src)
    print(" ".join(x["text"] for x in out))


if __name__ == "__main__":
    main()
