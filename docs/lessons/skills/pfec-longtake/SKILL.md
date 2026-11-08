---
name: pfec-longtake
description: "PFEC's own continuous-take motion films (commercial-safe, built in-house): short 9:16 reels, openers, stings and teasers where every beat grows out of the last instead of cutting like slides. A dot becomes a pill becomes a card becomes the frame, words crush into a line that underlines the logo, the camera pushes and settles. Seekable HTML comps, real motion blur, shared SFX, and a continuity check that fails a slideshow. Use for PFEC promo/teaser/launch/event motion films, seamless or 'one-take' openers, or when a motion piece 'feels like PPT / slides'. Not for the non-profit-only onetake skill's jobs: this one is the commercial-safe route."
---

# PFEC longtake

The tool lives at `~/Downloads/podcut/podcut/tools/longtake/`. **Read its
`README.md` first.** It has the workflow, the `LT.comp` contract and the
library reference. Run scripts with the engine venv python:
`~/Downloads/podcut/podcut/engine/.venv/Scripts/python.exe`.

## Steps

1. **Write the beat chain as handoffs.** Before any code, write one line per
   boundary: what is on screen, what it *becomes*, and which element survives
   (`handoff`). A boundary with no survivor is a slideshow cut. Redesign it,
   or mark it `cut: true` only if the hard cut means something.
2. **Shape the rhythm.** Give beats uneven lengths (≈1 s punches against 2–3 s
   builds), leave rests of at least 0.3 s after big moves, and use
   `holdStill` on the camera inside rests.
3. `python new.py <folder>` (inside a reel folder when it feeds a reel), then
   edit `comp.html`. Keep `render(t)` a pure function of `t`.
4. `stills.py`, then look at the sheet as a viewer would: overflow,
   legibility, framing.
5. `check.py --sheet`. Zero FAIL before rendering, and read every WARN.
6. `render.py --draft` and watch it with sound. Final render without
   `--draft`. Add `--loudnorm` only for a standalone post.
7. In a reel, set `content.json` `"motion": [{"role": "opener", "take":
   "<folder>"}]` (or `sting`, or `broll` + `name`). `reels/build_motion.py`
   does the rest.

## PFEC rules

- Real copy only: replace every `SAMPLE COPY` and never invent figures.
- End lockups list all 7 offices: Melbourne, Sydney, Lakemba, Adelaide,
  Perth, Brisbane, Parramatta (last).
- Brand palette via `LT.BRAND` and Poppins. Keep text out of the top 8% /
  bottom 15% / right 10%.
- Whoosh/impact SFX must be filtered noise, never sine sweeps. Reuse
  `podcut/assets/sfx/` and keep about 8 cues or fewer.
- Do not copy code, text or assets from the onetake skill into this tool.
  longtake was written independently so PFEC can use it commercially.
