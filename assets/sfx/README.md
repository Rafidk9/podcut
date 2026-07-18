# Shared SFX library

Reusable one-shot sound effects for the Tier-1 SFX pass every reel should get
(see `reels/build_composite.py`'s `sfx_cues()`): a hero-word slam whoosh+thud,
a transition whoosh for wipe cuts, and a CTA success chime.

All three are originals, synthesized locally with ffmpeg's audio filters
(`anoisesrc`, `sine`, `afade`, `amix`) — no third-party licence to track,
unlike `assets/music/`.

| File | Use | Design |
|------|-----|--------|
| `whoosh-impact.mp3` | Full-screen hero-word slam (kinetic word punching onto screen) | Layered noise (air + body) into a low sine+noise thud, timed so the thud lands ~165ms into the clip — offset the cue start by `word_start - 0.165` |
| `transition-whoosh.mp3` | Grid-pixelate wipe cut | Two crossfaded noise bands (high→low), no sine sweep |
| `success-chime.mp3` | CTA pop-in / confetti burst | Ascending sine triad (C5-E5-G5), bell-like |

**Note on timbre:** the first pass at the two whoosh sounds used pure
sine-frequency chirps (a swept sine wave) instead of filtered noise — those
read as a sci-fi/game blip, not a real air whoosh, and clashed with
professional brand content. Always synthesize whoosh/impact sounds from
filtered noise layers, never a bare sine sweep.

Regenerate/tweak by re-running the ffmpeg commands in this project's
conversation history for the 2026-07-17 Tushar Chopra Migration360 Roadshow
reel, or design new variants the same way for a different mood.
