"""No B-roll for this reel.

The "act portal" clip is a SINGLE continuous 24s take (one segment, not a
multi-take assembly), and its content is dense and load-bearing end to end --
a date (27 July go-live), a new fee, and a changed ranking rule. Per
reels/README.md, B-roll only ever goes over connecting/filler phrases, never
over key information, and the count scales with how many such spans genuinely
exist. This reel has none: there is no take boundary to cut on and no filler
span, so the correct, README-sanctioned choice is zero B-roll.

STINGERS is intentionally empty; broll_plan.json carries an empty plan +
boundaries so insert_broll.py does a straight concat (no cutaways, no wipes)."""

STINGERS = []
