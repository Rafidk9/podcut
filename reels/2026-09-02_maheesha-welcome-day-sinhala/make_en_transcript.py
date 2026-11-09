"""Sinhala speech -> ENGLISH subtitle transcript, on the Sinhala word timings.

The reel is spoken entirely in Sinhala but ships English subtitles (user's
request). Every downstream stage of this pipeline -- the 2-word caption band,
anchor_phrase.py's badge/highlight/hero matching, build_caption_txt -- reads
work/<clip>.transcript.json, so the cleanest place to switch language is right
there: keep ElevenLabs' Sinhala output as <clip>.transcript.si.json (the source
of truth for timing) and REPLACE <clip>.transcript.json with an English one
whose word timings are derived from it.

How the mapping works: CHUNKS below pairs a span of Sinhala word indices with
the English that renders over it. Each chunk's English words are spread across
that span's real audio window [si[a].start, si[b].end], proportionally to word
length so long words get more screen time than short ones. Chunk boundaries are
chosen at points where Sinhala and English phrase order actually agree -- most
importantly the five city names and the date/time, which each get their own
chunk so the caption (and the background city swap keyed off it) lands exactly
on the spoken word. Where the two languages reorder against each other (Sinhala
is verb-final), the chunk is widened to a whole clause and the English simply
reads naturally across it rather than word-for-word.

Run AFTER `podcut transcribe` and BEFORE build_base.py. Idempotent: the Sinhala
originals are only copied to .si.json once, and every later run re-derives the
English from those, so re-running never compounds.
"""
import json
import os
import shutil

REEL = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(REEL, "work")

# (first_si_index, last_si_index, "english text")
CHUNKS = {
    # P1's six-months qualifier is CUT (clips.json keeps only 3.89s onward), so
    # indices 0-4 never survive build_base's keep filter. Their English is left
    # here, accurate to the Sinhala, purely so the mapping still reads correctly
    # if that trim is ever reverted -- the line that actually renders is the
    # 5-7 chunk, which now carries the whole question on its own.
    "P1": [
        (0, 4, "You, in the last six months,"),
        (5, 7, "Did you come to Australia?"),
    ],
    "P2": [
        (0, 1, "At PFEC Global"),
        (2, 9, "we've planned something special to welcome you."),
        (10, 16, "It's the PFEC Global Welcome Day."),
    ],
    "P3": [
        (0, 1, "On the river,"),
        (2, 8, "a three hour private cruise"),
        (9, 14, "to enjoy with your friends."),
        (15, 18, "Food and drinks free!"),
    ],
    "P4": [
        (0, 2, "On September 19,"),
        (3, 9, "from 12 noon to 3 PM,"),
        (10, 10, "at our"),
        (11, 11, "Brisbane,"),
        (12, 12, "Melbourne,"),
        (13, 13, "Perth,"),
        (14, 14, "Adelaide"),
        (15, 16, "and Sydney"),
        (17, 18, "branches."),
        (19, 24, "Join us for the event."),
        (25, 34, "Meet our team and make new friends."),
    ],
    "P5": [
        (0, 1, "So don't wait,"),
        (2, 5, "use the link below"),
        (6, 7, "and register."),
        (8, 11, "PFEC Global Welcome Day."),
    ],
}


def spread(words, t0, t1):
    """Lay english `words` across [t0, t1], each word's share of the window
    proportional to its length (a 9-letter word holds the band longer than
    'to'). Returns [(text, start, end), ...] with no gaps."""
    weights = [max(2, len(w.strip(".,!?—"))) for w in words]
    total = float(sum(weights))
    span = t1 - t0
    out, t = [], t0
    for w, wt in zip(words, weights):
        d = span * wt / total
        out.append((w, round(t, 3), round(t + d, 3)))
        t += d
    return out


def main():
    for clip, chunks in CHUNKS.items():
        si_path = os.path.join(WORK, clip + ".transcript.si.json")
        en_path = os.path.join(WORK, clip + ".transcript.json")
        if not os.path.exists(si_path):
            shutil.copyfile(en_path, si_path)      # first run: preserve original
        si = json.load(open(si_path, encoding="utf-8"))["words"]

        out = []
        for a, b, text in chunks:
            t0, t1 = float(si[a]["start"]), float(si[b]["end"])
            for w, s, e in spread(text.split(), t0, t1):
                out.append({"text": w, "speaker": si[a].get("speaker", "A"),
                            "start": s, "end": e, "confidence": 1.0})
        json.dump({"provider": "elevenlabs:scribe_v1+en-subtitle", "words": out},
                  open(en_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        covered = f"{out[0]['start']:.2f}-{out[-1]['end']:.2f}s"
        print(f"{clip}: {len(si)} si words -> {len(out)} en words  ({covered})")


if __name__ == "__main__":
    main()
