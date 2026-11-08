---
name: motion-pixel-art
description: 'Make an 8-bit pixel-art scene: a dithered sunset sky, setting sun, parallax hills, a hero running and jumping to collect spinning coins, and a HUD counter. Use for gaming, retro, kids and playful CTAs.'
---

# Pixel Art motion style

Make an 8-bit pixel-art scene: a dithered sunset sky, setting sun, parallax hills, a hero running and jumping to collect spinning coins, and a HUD counter.

This skill ships a **working animated template**. Claude changes the parameters, checks a few stills and renders an MP4 (or a transparent overlay). Nothing is generated from scratch, so the result looks the same every time.

## Files in this folder

| file | what it is |
|---|---|
| `template.html` | Self-contained animation (HTML canvas plus plain JS, no internet or CDN needed). Open it in a browser to preview it live. |
| `render.py` | Renders `template.html` frame by frame to `.mp4`, a transparent `.mov`/`.webm`, or a `.png` still. |
| `preview.jpg` | A still of the default look. |

## Style contract (keep these to stay on-style)

- Low-res buffer (about 90 px on the short side) scaled up with nearest-neighbour, no smoothing.
- Sky dithered from purple `#3a1460` through magenta to pink `#ff6b9a` and peach. Sun in yellow `#ffd23f` with scanline cuts.
- Green `#2c7a3a` ground over brown dirt. The hero sprite is red, skin and blue.
- Pixel font for the HUD with a hard drop shadow.

## Motion

- The ground and hills scroll at different speeds (parallax) and the sun sinks slowly.
- The hero runs on a 2-frame cycle and jumps every 1.5 s.
- Coins spin as they approach and are collected, and the counter ticks up.

## Parameters

Every template takes the same URL or `render.py` parameters:

| param | render.py flag | default | notes |
|---|---|---|---|
| width / height | `--w` `--h` | 1080 × 1920 | Any size works (layout scales from the short side). Use 1080×1080, 1080×1350 or 1920×1080 for other formats. |
| duration | `--dur` | see `DEFAULT_DUR` | Timings are mostly proportional, so longer means slower. |
| fps | `--fps` | 30 | |
| main text | `--text` | see `DEFAULT_TEXT` | |
| secondary text | `--sub` | see `DEFAULT_SUB` | Pass `--sub ""` to hide it. |
| colours | `--set key=hex` | see `DEFAULT_COLORS` | e.g. `--set c1=ff2a1a --set bg=000000` |
| transparent | `--alpha` | off | Background left empty; output `.mov` (ProRes 4444) or `.webm` (VP9 alpha). |

**This style:** `text` is the HUD label (`COINS`); `sub` is an optional blinking line (e.g. `PRESS START`). Colours: `bg` (sky top), `c1` (sun and coins), `c2` (horizon), `c3` (grass).

Defaults, at the top of `template.html`:

```js
const DEFAULT_DUR = 6, DEFAULT_TEXT = 'COINS', DEFAULT_SUB = '';
const DEFAULT_COLORS = { bg: '#3a1460', c1: '#ffd23f', c2: '#ff6b9a', c3: '#2c7a3a' };
```

## Quick start

```bash
pip install playwright && playwright install chromium   # once; also needs ffmpeg
python3 render.py template.html out.mp4                         # default 9:16, default text
python3 render.py template.html out.mp4 --w 1080 --h 1080 --text "YOUR WORD"
python3 render.py template.html overlay.mov --alpha             # for laying over footage
python3 render.py template.html check.png --still 2.5           # one frame, for checking
```

To preview live, open `template.html?text=HELLO&w=1080&h=1080` in Chrome.

## Workflow for Claude

1. **Settle three things.** Ask only if they're missing: the words (`text` / `sub`), the format (9:16 reel, 1:1, 4:5 or 16:9), and the length (the default is `DEFAULT_DUR`). Brand colours are optional; map them to `bg`/`c1`/`c2`/`c3`.
2. **Copy this folder** into the project and keep `template.html` unchanged unless the brief needs a structural change (see Variations).
3. **Check stills first.** Render `--still` at about 10%, 40% and 80% of the duration and look at them. Check that the text fits inside the frame with a 5% margin, stays readable, and that colours have contrast. If text overflows, shorten it or lower the size inside `fitFont(...)` calls.
4. **Render** the MP4 (or `--alpha` for an overlay). Add `--audio track.mp3` to mux music.
5. **Deliver** with one line on what was customised.

## Use it inside a video edit

- **Overlay on footage (ffmpeg):** `ffmpeg -i footage.mp4 -i overlay.mov -filter_complex "[0][1]overlay=0:0" -c:a copy out.mp4`
- **Premiere, Final Cut, CapCut, DaVinci:** import the `--alpha` `.mov` and put it on the track above the footage.
- **HyperFrames or any HTML-video composition:** render with `--alpha` to `.webm` and drop it in as a `<video>` clip. Or paste the template's `<canvas>` and script into the composition and call `renderFrame(localTime)` from the timeline's `onUpdate`, since the draw is fully deterministic.

## Good for

- Gaming channels
- Retro-themed promos
- A "level up" or milestone post
- Playful CTAs

## Variations

- Redraw `HERO` as your own 8×8 sprite (one character per pixel)
- Night scene: darker bands, moon instead of sun

## Avoid

- Anti-aliasing (keep `imageSmoothingEnabled = false`)
- Sub-pixel motion (always floor positions)

## Rules for editing the template

- `draw(t)` must be a pure function of `t`: no `Math.random()` (use the seeded `rnd()` after `reseed(n)`) and no `Date.now()`. This keeps every render frame-exact.
- Size everything from `U` (the short side) so any aspect ratio works.
- Keep it self-contained, with no external scripts or fonts from a CDN. Fonts fall back to system fonts; for a custom font, add an `@font-face` that points at a local file and include it next to the template.
