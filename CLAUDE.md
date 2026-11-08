<!-- Mirrored in AGENTS.md for non-Claude AI coding tools that look for that
     filename instead. Keep both files in sync when either one changes. -->

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

## Motion-style library is available (opener / sting / B-roll)

20 PFEC-branded motion templates (split-flap, kinetic type, neon, particles,
isometric, glassmorphism, retro VHS, …) in `assets/motion-styles/`, rendered
by `build_motion.py` from `content.json`'s `"motion"` list into the
opener/sting/B-roll slots. Offer one when a reel wants a cold open, a closing
sting, or a cutaway that a HyperFrames stinger would otherwise be hand-built
for — but pick the style to fit the reel's tone (split-flap for travel/offices,
kinetic type for a hook, neon for live events; keep playful styles like
pixel-art/comic-book off compliance-toned reels). Text comes from this reel's
content; never ship a template's demo numbers. Docs: `reels/README.md`.

For a cold open or teaser that should flow as **one continuous take** (each
beat grows out of the last, camera push/settle, real motion blur), use
`tools/longtake/` (PFEC's own and commercial-safe; skill `pfec-longtake`) and
wire it in with `"take"`. Never use the onetake skill for commercial reels.
It is licensed for the non-profit wing only.

For a word-synced animated explainer over a whole talking-head reel, run one
full-frame longtake with the presenter in a window. At each take change the
window closes into a graphic, which hides the jump cut. The matte comes from a
mask-mode copy of the same comp. Reference:
`reels/2026-10-28_tushar-explainer/` (`take/comp.html`, `composite_take.py`).

## End-of-reel ritual: propose new learnings for confirmation

When a reel edit is finished, before considering the task done: review what
was learned this session — a taste correction (e.g. "these SFX sound
funny"), a technical fix, a generalizable technique — and propose a short
list to the user, asking which should be saved as standing preferences for
future reels (in memory, and/or folded back into this doc). Don't silently
decide on your own what's worth remembering — this is a review-and-confirm
step every time, not a one-off or a silent auto-save.

## Reel folders are local-only — never on GitHub

`reels/<date>_<slug>/` is gitignored (client footage/PII). If a reel is
ever built inside a git worktree, copy its folder into the main checkout's
`reels/` **before** removing that worktree — otherwise the finished video
and all working files are gone for good. (This nearly happened once.)
