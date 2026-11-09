"""Hinglish speech -> ENGLISH caption transcripts, on the original word timings.

Same script as the 2026-10-05 Hindi reel, re-shot at a desk in two takes.
Captions are English (user's standing ask for this script, 2026-10-06).
ElevenLabs' originals are kept as work/<clip>.transcript.hi.json; each
work/<clip>.transcript.json is rewritten: English words pass through with exact
timing, each Hindi phrase in CHUNKS is replaced by its translation spread over
that phrase's audio window. A chunk with "" drops those words (crew cue /
filler, also outside the clips.json keep span). Also normalizes '1:00 p.m.' ->
'1 PM' and the Devanagari danda '।' -> '.'.

Run AFTER `podcut transcribe`, BEFORE build_base.py. Idempotent.
"""
import json
import os
import shutil

REEL = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(REEL, "work")

CHUNKS = {
    "IMG_3002": [
        (0, 1, ""),                                           # crew "Start?" + "अ,"
        (2, 4, "We know"),                                    # हमें पता है
        (5, 14, "you've been affected by the recent student visa changes"),
        (15, 18, "and stressed too."),                        # and परेशान भी हैं।
        (19, 22, "Especially in the scenario"),               # Specially उस scenario में
        (23, 26, "when your student visa"),                   # जब आपका student visa
        (27, 34, "is about to expire very soon."),            # बहुत ही जल्दी expire होने जा रहा है।
    ],
    "IMG_3007": [
        (0, 3, "Come and ask your questions,"),               # आइए अपने questions पूछिए
    ],
}
TIMES = {"1:00": "1", "2:00": "2", "p.m.": "PM"}


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


def convert(clip, chunks):
    src = os.path.join(WORK, f"{clip}.transcript.json")
    hi = os.path.join(WORK, f"{clip}.transcript.hi.json")
    if not os.path.exists(hi):
        shutil.copy2(src, hi)
    d = json.load(open(hi, encoding="utf-8"))
    w = d["words"]
    starts = {a: (b, en) for a, b, en in chunks}
    out, i = [], 0
    while i < len(w):
        if i in starts:
            b, en = starts[i]
            if en:
                out += spread(en, w[i]["start"], w[b]["end"], w[i].get("speaker", "A"))
            i = b + 1
            continue
        x = dict(w[i])
        x["text"] = x["text"].replace("।", ".")
        if any("ऀ" <= ch <= "ॿ" for ch in x["text"]):
            raise SystemExit(f"{clip}: untranslated Hindi word {i}: {x['text']}")
        core = x["text"].rstrip(",")
        if core in TIMES:
            x["text"] = TIMES[core] + x["text"][len(core):]
        out.append(x)
        i += 1
    d["words"] = out
    json.dump(d, open(src, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(clip, ":", " ".join(x["text"] for x in out))


if __name__ == "__main__":
    for clip, chunks in CHUNKS.items():
        convert(clip, chunks)
