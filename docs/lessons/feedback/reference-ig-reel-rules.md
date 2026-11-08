---
name: reference-ig-reel-rules
description: Instagram Reel/caption rules learned from github.com/Jakeschincariol/instagram-agent-skill (MIT) and applied to Visa Compass AU on 2026-10-26
metadata:
  node_type: memory
  type: reference
  originSessionId: 86ebcf77-d2f4-48f1-b8db-f4346f3b2605
  modified: 2026-10-26T06:50:02.488Z
---

Source: github.com/Jakeschincariol/instagram-agent-skill (MIT; skills ig-reel, ig-caption, ig-human, ig-viral…). Its scripts are stdlib-only: `hookscore.py hooks.txt`, `beats.py script.txt --target N`, `caption.py caption.txt --keywords "a,b"` (run with `python -I -X utf8` on Windows).

Rules applied to the Visa Code Decoder reels:
- Write 3 hooks on different formulas (hooks.json, 26 formulas), score them, use the top; under 50 = no hook yet. "Nobody tells you…" scored 82–84 for both episodes; the originals scored 55 and 42.
- On-screen hook card ≤ 6 words, up at frame 0; spoken and on-screen hook written separately.
- One ask only (comment a keyword, save, or follow); last line echoes a hook word (loop).
- Safe zone 1080×1920: nothing important above y 230 / below y 1440, keep the right 230 px (x > 850) clear.
- Captions: Job A for Reels (line 1 = the ask, first 125 chars), ≤ 5 hashtags (Instagram cap since 18 Dec 2025), search phrases in plain words, links aren't clickable (we keep source URLs on purpose, see [[visa-compass-au]]).
- Skill says 15–45 s; the user chose depth ([[feedback-go-deep-not-surface]]), so longer is accepted.
