---
name: feedback-say-codes-digit-by-digit
description: "Visa condition / subclass codes are spoken digit by digit in voiceovers (\"eight two zero two\"), never \"eighty-two oh two\""
metadata:
  node_type: memory
  type: feedback
  originSessionId: 86ebcf77-d2f4-48f1-b8db-f4346f3b2605
  modified: 2026-10-26T04:23:34.419Z
---

In TTS/voiceover scripts, say visa condition numbers digit by digit: 8202 → "eight two zero two", 8533 → "eight five three three". Captions still show the digits.

**Why:** user corrected "eighty-two oh two" on 2026-10-26: digit-by-digit is how these codes are usually pronounced in Australian migration.
**How to apply:** in `script.json` put the digit-by-digit form in `say` for every code (and probably subclass numbers too: ask if unsure); expect lines to get longer and re-check overlaps/beat timings. Related: [[visa-compass-au]].
