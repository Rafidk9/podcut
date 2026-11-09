"""Hindi/Hinglish speech -> ROMANIZED Hinglish caption transcript, same word timings.

Rahul speaks Hinglish: Hindi sentences with the English phrases (dates, times,
offices, 'student visa changes') spoken in English. ElevenLabs returns the Hindi
words in Devanagari and the English words in Latin script. Mixed-script caption
chunks look broken and Poppins has no Devanagari glyphs, so -- like the Sinhala
reel's make_en_transcript.py -- the original is kept as
work/<clip>.transcript.hi.json (source of truth) and work/<clip>.transcript.json
is rewritten with every Devanagari word romanized ONE-FOR-ONE. Because it is a
1:1 transliteration, not a translation, every word keeps its own exact timing.

Also normalizes ASR's '1:00'/'2:00' to '1'/'2' (user wants '1 PM', not '1:00 PM'
or 'one PM').

Run AFTER `podcut transcribe`, BEFORE build_base.py. Idempotent.
"""
import json
import os
import shutil

REEL = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(REEL, "work")
CLIP = "IMG_0293"

ROMAN = {
    "हमें": "Humein", "पता": "pata", "है": "hai", "है।": "hai.", "आप": "aap",
    "में": "mein", "हुए": "hue", "से": "se", "हैं": "hain", "और": "aur",
    "परेशान": "pareshaan", "भी": "bhi", "उस": "us", "जब": "jab",
    "आपका": "aapka", "बहुत": "bahut", "ही": "hi", "जल्दी": "jaldi",
    "होने": "hone", "जा": "ja", "रहा": "raha", "आइए": "Aaiye", "अपने": "apne",
    "पूछिए।": "poochhiye.",
}
TIMES = {"1:00": "1", "2:00": "2"}


def main():
    src = os.path.join(WORK, f"{CLIP}.transcript.json")
    hi = os.path.join(WORK, f"{CLIP}.transcript.hi.json")
    if not os.path.exists(hi):
        shutil.copy2(src, hi)
    d = json.load(open(hi, encoding="utf-8"))
    missing = []
    for w in d["words"]:
        t = w["text"]
        if any("ऀ" <= ch <= "ॿ" for ch in t):
            if t not in ROMAN:
                missing.append(t)
                continue
            w["text"] = ROMAN[t]
        elif t.rstrip(",.") in TIMES:
            core = t.rstrip(",.")
            w["text"] = TIMES[core] + t[len(core):]
    if missing:
        raise SystemExit(f"no romanization for: {missing}")
    json.dump(d, open(src, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", src)
    print(" ".join(w["text"] for w in d["words"]))


if __name__ == "__main__":
    main()
