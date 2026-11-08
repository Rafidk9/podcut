---
name: feedback-no-overlap-onetake-transitions
description: "Visa Compass AU reels — no on-screen text may overlap other text/cards; every screen change is a onetake carry (morph/fold/camera), never a pop-swap"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 86ebcf77-d2f4-48f1-b8db-f4346f3b2605
  modified: 2026-10-26T10:31:30.841Z
---

On every reel, no text may overlap other text or cards (captions, chips, stamps, bubbles, name tags, timesheet), and
screens must switch with onetake-style motion (card morphs into the next card, fold, camera push/pull, iris), not
by popping one screen out and another in.

**Why:** the user asked for this on Decoder #3 (2026-10-26) after the storyboard showed captions over the timesheet,
a stamp over a row label and pop-swaps between the payslip and 8105.

**How to apply:** lay out fixed zones (top band 230–400, content 400–1215, captions from 1225) and cap camera zoom so
content never reaches captions; run `tools/overlap_check.py comp.html 0.05` (videos/reel-04) and get "no overlaps"
before showing the storyboard; include a transition strip. Related: [[feedback-storyboard-before-render]],
[[visa-compass-au]].
