---
name: feedback-say-acronyms-fluently
description: "Visa Compass AU voice — spell letter acronyms with hyphens (O-S-H-C, G-P, U-T-I, T-R-N) so Kokoro says them fluently; never \"O. S. H. C.\""
metadata:
  node_type: memory
  type: feedback
  originSessionId: 86ebcf77-d2f4-48f1-b8db-f4346f3b2605
  modified: 2026-10-26T14:20:05.250Z
---

Letter-by-letter acronyms in the VO must run together fluently ("OSHC"), not with a pause after each letter.
In script.json `say`, write them hyphenated: `O-S-H-C`, `G-P`, `U-T-I`, `T-R-N`.

**Why:** the user heard "O. S. H. C." as an odd, choppy "oHHSC" (2026-10-26). A test of 6 spellings with Kokoro
af_heart: raw "OSHC" is read "Oshk"; "O. S. H. C." pauses after each letter; "O-S-H-C" was tightest (0.60 s, no inner
pause, whisper hears "OSHC").

Same for words Kokoro drags out: "brochure" came out as "brochuuure" (2026-10-27) → `say` "brosher" (tightest of 6
tested spellings, still heard as brochure). Test odd-sounding words with whisper word lengths before voicing.

**How to apply:** use hyphens for any spelled-out acronym; keep a sentence's full stop after it ("a G-P. O-S-H-C pays…").
Codes are still said digit by digit ([[feedback-say-codes-digit-by-digit]]). Related: [[visa-compass-au]].
