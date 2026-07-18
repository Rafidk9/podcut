# PFEC reels

One folder per reel, named `<YYYY-MM-DD>_<slug>` (event/publication date first so
folders sort chronologically):

```
reels/
  README.md            this file
  reel_paths.py        picks the active reel (env var or newest folder)
  new_reel.py          scaffolds a new reel folder
  build_*.py …         shared pipeline scripts (operate on ONE reel at a time)
  2026-07-13_lakemba-seminar/
    input/             raw clips (phone footage fine — pipeline tone-maps HDR)
    work/              intermediates (base, B-roll, cap_proj, captioned…)
    output/            reel_final.mp4 + caption.txt   ← the deliverables
```

Shared brand assets (logo chip, end cards, music) are NOT per-reel — they live
in `podcut/assets/`.

## Starting a new reel

```
python new_reel.py 2026-08-02_parramatta-expo
# drop raw clips into 2026-08-02_parramatta-expo/input/
```

## Which reel do the scripts act on?

- Default: the **newest** reel folder (lexicographically last, i.e. latest date).
- Override: `set PODCUT_REEL=2026-07-13_lakemba-seminar` (or an absolute path).

Every script prints `[reel] <name>` when auto-picking, so you always know.

## Pipeline (run from `reels/`, in order)

```
python build_base.py        # trim/normalize/tone-map + assembled transcript
python build_broll.py       # topical B-roll stingers (HyperFrames)
python build_wipe.py        # brand grid-wipe transition
python insert_broll.py      # splice B-roll (video only; audio continuous)
python build_captions.py    # captions + overlay cards → captioned.mp4 (SLOW)
python build_composite.py   # logo, end cards, music, loudnorm → output/reel_final.mp4
python build_caption_txt.py # social caption → output/caption.txt
python build_thumbnail.py   # branded still → output/thumbnail.jpg
python qa_reel.py           # pre-post QA gate (spec/colour/loudness/true-peak/
                            # black-frames/caption sanity/safe-zone) — run last,
                            # exits non-zero on any FAIL
```

`qa_reel.py` is the automated half of the pre-post checklist; it does NOT replace
an eyes/ears pass (reverb/noise, mishears, on-screen PII, MARN correctness,
factual accuracy, and real in-app safe-zones still need a human).

`build_thumbnail.py` grabs a frame from `work/base_broll.mp4` (default: 3.0s
in — pre-caption, so no kinetic caption word can freeze into the still),
composites the logo fresh, then stamps a kicker pill + bold headline on top,
gold-accenting any `**word**` you wrap. Every field is optional via
`<reel>/content.json`:

```json
{ "thumbnail": { "at": 4.2, "kicker": "FREE MIGRATION SEMINAR",
                 "headline": "GET YOUR **189 VISA** FASTER" } }
```

With no override you still get a branded still (frame + logo + legibility
shade) — kicker/headline just add the hook on top.

## Caption band position

The 2-word caption band defaults to `top: 62%` (suits a normally-framed
talking head). If the subject sits lower or higher in frame, raise/lower it
per reel via `content.json`:

```json
{ "cap_top": "56%" }
```

Lower the percentage to move the band up (toward headroom) — check the
subject's face position in `work/base_broll.mp4` before picking a value so
captions never land on their face.

## Background music

`build_composite.py` defaults to the Lakemba reel's track (`funky-chunk-kevin-macleod.mp3`
at volume 0.05) so old reels keep rebuilding unchanged. Override per reel via
`<reel>/content.json`:

```json
{ "music": { "track": "adding-the-sun-kevin-macleod.mp3", "volume": 0.02 } }
```

- `track` — a filename under `assets/music/`. Drop the file there and add its
  licence entry to `assets/music/CREDIT.txt` (same CC-BY-4.0/incompetech
  convention as the existing track) *before* referencing it, and mirror that
  exact credit line into this reel's `content.json` under
  `caption_txt.music_credit` so `build_caption_txt.py` picks it up instead of
  the hardcoded default.
- `volume` — linear gain on the music bed before sidechain ducking under her
  voice (not final loudness — the two-pass loudnorm at the end still targets
  -14 LUFS overall). 0.05 was tuned for "Funky Chunk"; quieter/busier tracks
  may need a different level entirely — always listen back to the mixed
  result under her lowest-energy line, not just a peak moment.

Fast iteration (avoid full 4–9 min caption renders):
- live preview: launch config `reels-preview` (update its `cwd` if the newest
  reel changes — it points at `<reel>/work/cap_proj`). Stop this server before
  running `build_captions.py` (it locks `cap_proj`).
- `python preview_window.py START END` — draft-render just a time window.

After any rebuild of reel_final.mp4, verify colour tags read bt709/tv:
`ffprobe -select_streams v:0 -show_entries stream=color_range,color_space,color_transfer,color_primaries output/reel_final.mp4`

## Must do — SFX (Tier 1) on every reel

Every reel should get a Tier-1 SFX pass by default, not just on request:
whoosh+thud on a hero-word slam, a reused transition whoosh at wipe cuts, and
a success chime under the CTA pop-in. Wire cues via `<reel>/content.json`:

```json
{ "sfx": { "cues": [
    { "file": "whoosh-impact.mp3", "at": 3.48, "volume": 0.8 },
    { "file": "transition-whoosh.mp3", "at": 4.26, "volume": 0.45 },
    { "file": "success-chime.mp3", "at": 31.80, "volume": 0.7 }
] } }
```

- `at` — seconds on the same timeline as everything else in `content.json`
  (the assembled/content timeline, i.e. before the disclaimer/consultation
  end cards get appended). For a hero-word slam, sync it to the word's
  resolved start minus the cue's own internal attack offset (see
  `assets/sfx/README.md` for each stock cue's timing). For a wipe cut, use
  `broll_plan.json`'s `boundaries` values directly — those are exact
  final-timeline seconds; b-roll *replaces* footage rather than inserting it,
  so there's no time-shift math needed.
- `file` resolves against `<reel>/assets/sfx/` first, falling back to the
  shared `assets/sfx/` library (`sfx_path()` in `build_composite.py`) — the
  three stock Tier-1 cues need no per-reel copy; only add a reel-local file
  to override one with a bespoke sound.
- Always run `qa_reel.py` after adding/adjusting SFX — short percussive
  transients can push loudnorm's true-peak measurement over target; there's
  an `alimiter` safety net after the loudnorm pass for this.
- **Whoosh/impact sounds must be synthesized from filtered noise layers,
  never a bare sine-frequency sweep** — a sine chirp reads as a sci-fi/game
  blip, not real air movement, and clashes with professional brand content.

## Decorative layer (orbs / sparkles / handle)

For reels with a lot of dead wall space (subject framed small, plain
backdrop). Opt-in via `<reel>/content.json`:

```json
{ "decor": {"accents": true, "sparkles": true, "handle": "@PFECGlobal"} }
```

`accents` = soft, low-opacity brand-colour orbs drifting gently in the empty
margins; `sparkles` = small twinkle stars + outline rings; `handle` = a small
social-handle pill low-centre. All three sit behind the captions/cards and
animate on the same seek-safe timeline (`build_captions.py`). Off by default
— offer it when a reel's footage has a lot of empty margin around the
subject.

## Text Behind Subject (opt-in, expensive — use sparingly)

A compositing z-order trick: real background → overlay layer → person
cutout on top, using per-frame `rembg` (u2net_human_seg) matting, so the
subject appears to genuinely stand in front of a graphic or block of text.
Composite order matters: original footage (keeps the real room/background
visible) → the overlay layer (animated: fade/slide entrance, optional
shimmer sweep) → the person cutout, so they're in front of both.

The overlay layer doesn't have to be a logo/image asset — it works exactly
the same with rendered text (a list card, a keyword, a stat). There's no
generalized reusable script for this yet; `bg_swap.py` (see an existing
reel that used it) is a one-off hardcoded to one clip index + one asset —
worth generalizing into a shared pipeline step (clip index + timing + either
an image path or a text/HTML spec) if this becomes a recurring ask rather
than copy-pasted per reel.

**Cost tradeoff:** the matting pass is expensive — roughly 1-2 minutes of
processing per few seconds of footage. Reserve this for the strongest 1-2
moments per reel (a hook payoff, a key list/stat), not every caption beat —
using it everywhere dilutes the effect and blows up render time.

## Must do — B-roll placement is script-judged, not a fixed count

B-roll only ever goes over **connecting/filler phrases** in the transcript —
never over a moment carrying key information. The AI judges the script (the
assembled transcript from `build_base.py`) to find those connecting/filler
spans and picks an anchor phrase for each one; the **number of B-roll spots
is however many such spans genuinely exist, scaled to the video's length** —
it is not a fixed count. A short reel with few connecting phrases gets fewer
(or zero) B-roll cuts; a longer one can get more.

Each B-roll's design must be specific to what the speaker is actually saying
at that spot in that reel — never generic, and never reused wholesale from
another reel.

- Write a `<reel>/broll.py` (`STINGERS = [(name, duration, body_html), ...]`)
  and a `<reel>/broll_plan.json` (`n_segments`, `plan: {segment: stinger}`,
  `boundaries: {segment: time}`) — one stinger + placement per genuine
  connecting-phrase moment found in *this* reel's transcript. See the
  docstrings in `build_broll.py` / `insert_broll.py`.
- **Gotcha:** if a reel has no `broll.py` / `broll_plan.json` override,
  `build_broll.py` and `insert_broll.py` silently fall back to the *previous*
  reel's hard-coded defaults — currently 4 fixed Lakemba stingers at 4 fixed
  boundaries. That fallback only exists so the old Lakemba reel keeps
  rebuilding unchanged; it is **not** a safe default for a new reel, and it
  is also not the intended count-scales-with-content behaviour — it's a
  legacy fixed-4 placement, not an AI-judged one. Always derive both files
  from this reel's own transcript before running the B-roll steps.

## Document highlights (e.g. redacted visa grant letters)

`build_captions.py` can overlay a document as a designed "paper card + stamp"
at whatever point in the video the speaker is actually talking about it —
same anchor-phrase principle as B-roll: you name the words as spoken, and
`anchor_phrase.py`'s `resolve_anchor()` locates them in the transcript
(exact/fuzzy ≥0.8) and computes the window. If the phrase isn't found, the
document is **skipped with a loud warning**, never guessed onto a made-up
timecode — fix the `anchor_phrase` or add the window by hand.

**Redact BEFORE it ever touches this pipeline.** These letters carry PII
(name, DOB, passport/grant number). Run them through
`podcut/tools/letter-redactor/redact_letter.py` first:

```
python ../../tools/letter-redactor/redact_letter.py grant1.pdf grant1.png --format png
```

Only drop the **redacted** output into `<reel>/documents/`. Never put a raw,
unredacted letter there.

Then reference it from `<reel>/content.json`:

```json
{
  "documents": [
    { "image": "grant1.png", "anchor_phrase": "his 189 grant came through",
      "label": "189 VISA GRANT" }
  ]
}
```

A reel with no `documents` entry gets none — this is opt-in per reel, not a
forced element on every video.
