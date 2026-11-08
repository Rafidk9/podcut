---
name: motion-liquid-morph
description: 'Make liquid-chrome metaball blobs that merge and split with a pastel iridescent sheen. Use for abstract brand loops, product backdrops, AI or tech themes and soft openers.'
---

# Liquid Morph motion style

Make liquid-chrome metaball blobs that merge and split with a pastel iridescent sheen.

This skill ships a **working animated template**. Claude changes the parameters, checks a few stills and renders an MP4 (or a transparent overlay). Nothing is generated from scratch, so the result looks the same every time.

## Files in this folder

| file | what it is |
|---|---|
| `template.html` | Self-contained animation (HTML canvas plus plain JS, no internet or CDN needed). Open it in a browser to preview it live. |
| `render.py` | Renders `template.html` frame by frame to `.mp4`, a transparent `.mov`/`.webm`, or a `.png` still. |
| `preview.jpg` | A still of the default look. |

## Style contract (keep these to stay on-style)

- Background soft grey-lilac `#e9e8ef`.
- Blobs shaded per pixel: pastel pink, sky blue and lilac (`c1`/`c2`/`c3`) mapped by surface angle, so colour slides across the form.
- Chrome feel: a bright tight specular highlight at top-left and a cool rim light.
- A soft contact shadow under the group.

## Motion

- Five metaballs orbit at different speeds and radii and breathe in size.
- They continuously merge and split. One full orbit per loop, so the loop is seamless.

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

**This style:** `text` and `sub` are optional captions under the blobs. Colours: `bg` and `c1`-`c3` (the iridescent palette).

Defaults, at the top of `template.html`:

```js
const DEFAULT_DUR = 6, DEFAULT_TEXT = '', DEFAULT_SUB = '';
const DEFAULT_COLORS = { bg: '#e9e8ef', c1: '#ffb3d9', c2: '#9be7ff', c3: '#d6c2ff' };
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

- Background loop behind a talking head
- Abstract opener
- Product reveal backdrop

## Variations

- Use dark `bg` with saturated `c1`-`c3` for a night look
- Change `NB` (blob count) or the orbit radius in `balls()`

## Avoid

- Small sizes under 300 px (the shading gets muddy)
- Busy text on top

## Rules for editing the template

- `draw(t)` must be a pure function of `t`: no `Math.random()` (use the seeded `rnd()` after `reseed(n)`) and no `Date.now()`. This keeps every render frame-exact.
- Size everything from `U` (the short side) so any aspect ratio works.
- Keep it self-contained, with no external scripts or fonts from a CDN. Fonts fall back to system fonts; for a custom font, add an `@font-face` that points at a local file and include it next to the template.
