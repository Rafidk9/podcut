# PodCut — standing editorial preferences

These apply by default to every reel produced with this pipeline — offer
them proactively when planning or finishing a reel, don't wait to be asked
each time. Full pipeline docs and mechanics: `reels/README.md`.

## Every reel gets a Tier-1 SFX pass

Whoosh+thud on any hero-word slam, a reused transition whoosh at wipe cuts,
a success chime on the CTA pop-in. The shared cues live in `assets/sfx/`
(see its README) — `build_composite.py`'s `sfx_cues()` resolves them
automatically via `content.json`'s `"sfx"` key, so there's no need to
resynthesize per reel; only add a reel-local override for a bespoke sound.

**Whoosh/impact sounds must be synthesized from filtered noise layers, never
a bare sine-frequency sweep** — a sine chirp reads as a sci-fi/game blip, not
real air movement, and clashes with professional brand content. (Learned the
hard way: the first pass used sine chirps and got flagged as sounding
"funny.")

## Offer "Text Behind Subject" for standout moments

A compositing z-order trick: real background → overlay layer → person
cutout on top (per-frame `rembg` matting), so the subject appears to
genuinely stand in front of a graphic or text. Works for images (a campaign
logo) AND plain rendered text (list items, keywords, stats) — the overlay
layer doesn't have to be an image asset.

Reserve it for 1-2 standout moments per reel (a hook payoff, a key list) —
the matting pass is expensive (roughly 1-2 minutes of processing per few
seconds of footage), so using it on every beat dilutes the effect and blows
up render time. There's no generalized reusable script yet — `bg_swap.py`
(built per-reel, see an existing reel for reference) is a one-off hardcoded
to one clip + one asset; worth generalizing if this becomes a recurring ask.

## Decorative orbs/sparkles/handle layer is available

For reels with a lot of dead wall space (subject framed small, plain
backdrop). Opt-in via `content.json`'s `"decor"` key:

```json
{ "decor": {"accents": true, "sparkles": true, "handle": "@PFECGlobal"} }
```

Already implemented in `build_captions.py` (soft low-opacity brand-colour
orbs + twinkle stars + a handle pill, sitting behind the captions), off by
default. Offer it when a reel's footage has a lot of empty margin.

## Reel folders are local-only — never on GitHub

`reels/<date>_<slug>/` is gitignored (client footage/PII). If a reel is
ever built inside a git worktree, copy its folder into the main checkout's
`reels/` **before** removing that worktree — otherwise the finished video
and all working files are gone for good. (This nearly happened once.)
