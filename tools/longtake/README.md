# longtake — continuous-take motion films (PFEC, commercial-safe)

Short motion films (10–30 s, 9:16 by default) where **every beat grows out of
the one before**. Nothing is swapped in on a fade: a dot becomes a pill
becomes a card becomes the whole frame. Written from scratch for PodCut on
2026-10-21. It is PFEC's own code with no third-party motion code, so it's fine
for commercial reels.

```
tools/longtake/
  lib/longtake.js      motion library (window.LT) -- pure functions of time
  templates/comp.html  PFEC starter: seminar opener, 13.5 s, one take
  new.py               scaffold a self-contained project folder
  stills.py            contact sheet at beat boundaries (look before render)
  check.py             continuity + rhythm + safe-zone check (FAIL = slideshow)
  render.py            frame-exact render, shutter motion blur, SFX mix
  tests/               node tests/test_longtake.js ; pytest tests
```

Run with the engine venv python (has Playwright, numpy, Pillow):
`../../engine/.venv/Scripts/python.exe <script>.py ...` from this folder.

## Workflow

1. **Plan the chain, not the scenes.** Write the beats as one sentence of
   handoffs: *"the dot stretches into the pill, the pill opens into the card,
   the camera pushes until the card is the frame, the words crush into a line,
   the line underlines the logo."* For every boundary, name the thing that survives.
   If you can't name one, the beat is a cut. Make it a deliberate `cut: true`
   or redesign it.
2. **Vary the beat lengths.** Evenly spaced beats tick like a metronome. Mix
   short punches (≈1 s) with longer builds (2–3 s), and leave **rests** (≥0.3 s
   where nothing moves) after big moves so they land.
3. `python new.py <folder>` → edit `<folder>/comp.html` (keep `LT.comp`,
   `data-lt` ids and `beats`). Preview by opening it in Chrome: space pauses,
   and the bar scrubs.
4. `python stills.py <folder>/comp.html --out stills.png`: look at it
   **as a viewer**: overflow, legibility, the subject framing.
5. `python check.py <folder>/comp.html --sheet boundaries.png`: fix every
   FAIL before rendering, and read each WARN.
6. `python render.py <folder>/comp.html --out draft.mp4 --draft`, watch it
   with sound, iterate.
7. Final: `python render.py <folder>/comp.html --out film.mp4` (add
   `--loudnorm` for a standalone post; leave it off when the clip feeds the
   reel pipeline, which normalises the whole reel).

**In a reel:** scaffold into the reel folder and reference it from
`content.json`. `reels/build_motion.py` renders it into the slot:

```json
{ "motion": [ { "role": "opener", "take": "opener_take" } ] }
```

Roles: `opener` → `work/opener.mp4`, `sting` → `work/sting.mp4`, `broll` (+
`"name"`) → `work/<name>.mp4`. Takes re-render when any file in the folder
changes. `--preview` builds render as drafts.

## The composition contract

```js
LT.comp({
  width: 1080, height: 1920, dur: 13.5,
  render(t) { /* set every element from t alone */ },
  beats: [{ t: 1.3, name: "pill", handoff: "shape" }, { t: 6, cut: true }],
  cues:  [{ t: 0.25, file: "pop.mp3", vol: 0.5 }],
});
```

- `render(t)` must be a **pure function of t**: no `Date.now()`, no
  `Math.random()` (use `LT.noise`), no state between calls. The renderer seeks
  out of order and several times per frame for blur.
- Any element the checker should track gets `data-lt="<id>"`. Text elements
  are detected automatically, or mark one with `data-lt-text`.
- `beats[].handoff` is the `data-lt` id that must be on screen on both sides of
  the boundary. `cut: true` declares a hard cut (never blurred across).
- `cues[].file` resolves next to the comp first, then `podcut/assets/sfx/`
  (`pop`, `tick`, `transition-whoosh`, `whoosh-impact`, `success-chime`).
  Keep a comp's cue count around 8 or fewer; see `reels/README.md` on true peak.
- The stage is `#stage` (sized by `LT.comp`), and the camera moves `#world`.
  Keep the template's `body { margin: 0 }`; the renderer screenshots the
  viewport.

## Library (`LT.*`)

| Area | Helpers |
|---|---|
| numbers | `clamp`, `lerp`, `prog(t,a,b)`, `mix` |
| easing | `ease.{linear,in,out,inOut,outQuint,inOutQuint,outExpo,inExpo,inOutExpo,outBack,sine}` |
| springs | `spring(s, freq, damp)` (closed form), `springSettle`, `springEase(freq, damp)` → easing fn |
| keyframes | `key(t, [[t0,v0],[t1,v1,ease],…])` (numbers or arrays) |
| shapes | `morph(t, [[t,{x,y,w,h,r,fill,alpha}],…])`, `set(el, state)` (centre-anchored), `el(id)` |
| camera | `camera(t, shots, {hand, handSeed, holdStill, hits})`, `applyCamera`, `zoomToFit` |
| entrances | `pop(t,t0)` squash-settle, `reveal(t,t0,dur,dir)` mask, `split(el)` + `rise(t,spans,t0)`, `typed`, `count` |
| colour | `BRAND` (navy, deep, gold, cyan, green, red, white, ink), `hex`, `rgb`, `mixHex` |
| noise | `noise(x, seed)`, `drift(t, speed, seed)`; deterministic |

## Rules that carry over from the reel pipeline

- Words come from the job's real content. Template copy marked
  `SAMPLE COPY` is placeholder text; never ship it, and never invent a stat.
- End lockups list all **7 offices**, with Parramatta last.
- Keep text out of the platform UI zones (top 8%, bottom 15%, right 10%);
  `check.py` warns.
- Fonts: Poppins (OFL), copied in by `new.py`. Logo: `logo/pfec-logo-white.svg`.

## Render notes

- Default 4 browser workers. More parallel browsers stalled on this machine
  rather than going faster.
- Blur: 180° shutter, 6 captures minimum and up to 16 on fast frames (adaptive).
  Frames where nothing moves cost one capture. The 13.5 s starter takes ~80 s
  full quality and ~45 s as a draft.
- `--scale 2` renders 2160×3840 from a 1080×1920 comp. `--resume` continues a
  crashed render. `--keep-frames` keeps the PNGs.
