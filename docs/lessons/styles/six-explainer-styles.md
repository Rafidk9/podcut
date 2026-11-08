# Six short-form explainer styles (learned 2026-11-06)

Learned from a 22 s Facebook reel by Artem Novitckii
(facebook.com/reel/1510878837518529) that demos six Claude "animation skills",
each one prompt -> one 9:16 explainer. His skill files are not public here
(he gates them behind "comment ANIMATE"); everything below is reverse-engineered
from the frames. Rebuild each look from scratch in HyperFrames — never copy his
footage, characters or prompts.

Reference frames + the source reel: `~/.claude/styles/hyperframes/assets/six-explainer-styles/`
(`00-all-six-grid-*.jpg` shows all six side by side — look at that first).

Common to all six: 1080x1920, ~5-8 s per piece, one idea per clip, captions are
1-3 words at a time centred low-middle, no logos on screen.

## Trigger names (his) -> neutral names (ours)

| His slash name | Use this name | One-liner |
|---|---|---|
| /zach-d-films | **3d-whatif** | 3D cartoon "what if" explainer |
| /minimalistic-graphics | **minimal-line** | white-line metaphor on pure black |
| /stick-figure | **stick-figure** | flat 2D cartoon stick character in a scene |
| /breakdown | **exploded-breakdown** | isometric exploded view, numbered callouts |
| /map-route | **map-route** | 3D white city, blue route drawing to a pin |
| /graph | **graph-count** | smooth line graph + one big number counting up |

Don't call ours "zach-d-films": that names a real creator (Zack D. Films);
copying a named creator's look is off-limits. 3d-whatif is the generic genre.

## 1. 3d-whatif
- Look: stylised 3D character (clay-smooth skin, oversized nose, simple brows,
  stripe lips), soft sky-gradient background, glossy PBR props (here: steel plate
  armour). Shallow DOF, slow push-in.
- Payoff shot: a cutaway/x-ray of the object with a **red concentric "impact
  ripple"** heatmap spreading across the surface ("the blunt force… across more area").
- Captions: white Montserrat/Poppins-style bold, lowercase, 2 words, soft shadow,
  centred at ~75% height; spoken VO, word-by-word.
- Build: needs real 3D (Three.js in HyperFrames, or Blender renders). Hardest of the six.

## 2. minimal-line
- Pure #000 background, 1-2 px white strokes only, one white filled circle as the
  "subject". Lowercase sentence top-centre with a period ("every step feels small.").
- Motion: outlined bars rise as a staircase left->right; the dot hops bar to bar;
  second line swaps in ("until you look back.") and the camera pulls back so the
  dot becomes an eye/planet with an orbit ring and star dots. Slow, calm, no music hits.
- Build: easiest. Pure SVG/canvas, GSAP. Great for a reflective hook or end beat.

## 3. stick-figure
- Flat vector 2D, thick black outlines (~6 px), round white head, dot eyes in big
  white circles, simple mouth swaps (smile <-> open). Character costume carries the
  topic (pirate bandana + eye patch). Painted parallax background slightly blurred.
- Captions: heavy white sans with thick black stroke, 2 words, mid-frame over the body.
- Motion: idle bob, blink, mouth flaps on syllables, hand on hip; cuts to wide shots.
- Build: SVG rig in HyperFrames — maps directly onto our Alex & Mia setup.

## 4. exploded-breakdown
- Near-black radial-gradient bg (#0d1110 -> #000). Header top-left in mono caps,
  letter-spaced: `PHONE / EXPLODED VIEW` (second half dimmed).
- Isometric exploded stack of parts drifting apart vertically. Each part gets a
  leader line from a small coral dot to a callout: coral mono number (`01`), white
  semibold name, grey mono spec line (`toughened · 0.6 mm`). Callouts fade/slide in
  one by one, the next one dimmed until its turn.
- Build: CSS 3D transforms (rotateX 55deg rotateZ -35deg) on flat layers; easy-medium.

## 5. map-route
- Light 3D city: white extruded blocks, soft shadows, mint parks with blob trees,
  pale streets, small grey area labels ("Elm Park").
- Thick blue (#2f6fe4) route line with white casing draws itself; a blue dot rides
  the head; camera tilts/follows. Nav card top-left (white pill, blue arrow icon,
  "1 min / 0.1 km to go"), ends at a red pin + "Arrived" card + destination label.
- Build: Three.js boxes or CSS 3D grid + SVG path with stroke-dashoffset; medium.

## 6. graph-count
- Off-white card, tiny grey label top-left ("Followers"), huge black bold number
  counting up (80,278 -> 100,000) with tabular figures; thin black smooth curve
  draws left->right with a dot at the head, faint month axis below.
- Build: easiest after minimal-line. SVG path + number tween synced to the line.

## The reel's own wrapper (meta-format)
Each style is introduced by a phone screen-recording of a chat app: prompt chip
-> `/skill-name` -> "Animating with…" dot-matrix loader -> the clip expands to
full screen. Ends on a grid of all six + "Comment X and I'll send you all 6"
CTA. That wrapper uses Anthropic's Claude app UI; for our channels make a
generic/own-brand version, never a copy of a real app's UI.

## Fit for Visa Compass AU (navy #102D3A, amber #F3B85B, mint #E9F2EF, Nunito)
- **graph-count** -> fee rises, processing times, cap numbers (each number needs a sourced claim).
- **map-route** -> "your visa journey": student -> 485 -> skilled, stops as stations (no promises of outcome).
- **exploded-breakdown** -> "a visa grant, every part labelled": conditions, dates, VEVO, 8105, 8501.
- **minimal-line** -> calm hook/outro beats; recolour line to mint on navy.
- **stick-figure** -> close to Alex & Mia already; borrow the caption stroke + costume trick.
- **3d-whatif** -> built anyway (Three.js clay character works fine); usable.
For PFEC work use PFEC brand instead and the commercial-safe tooling.

## Built references (2026-11-06)
Working HyperFrames builds of all six, in Visa Compass colours:
`~/Downloads/visa-compass-au/videos/style-{graph,minimal,breakdown,map,stick,whatif}/`
(notes in `videos/STYLE-TESTS.md`). Clone one rather than starting from scratch.
Gotchas found while building:
- Three.js: put the `<script src=…three.min.js>` inside the scene file (the
  lint looks there), `preserveDrawingBuffer: true`, drive it from a GSAP proxy
  tween's `onUpdate(render(t))`. r160 lights need ~2x the legacy intensities.
- CSS 3D stacks: never fade an element that has `preserve-3d` (opacity flattens
  it); fade a parent without it. Measure callout anchors once at the final
  exploded state, before building the timeline.
- Edit files with the Edit tool, not PowerShell `Get/Set-Content` (it
  mangles UTF-8, e.g. `·` → `Â·`).

## Motion review checklist (run on every piece before render)
Agreed 2026-11-06. Read it against the timeline, not just stills.
**Layout**
- One hero per frame (scale / weight / contrast); clear reading order.
- Inside Instagram's safe zones first (right rail and bottom caption area), rule of thirds second.
- Negative space: no frame more than about 60% full; nothing crowds the edges.
- Contrast passes WCAG (`hyperframes check` enforces it); text ≥ 28 px; captions stroked or shadowed over busy backgrounds.
- One type family plus at most one accent (Nunito + a mono for labels).
- Gestalt: grouped items sit close together; leader lines and paths lead the eye to the next item.
**Motion**
- Nothing moves linearly unless it is a deliberate mechanical or progress move.
- Anticipation before every big move (a wind-up, a crouch, the camera leaning in).
- Overshoot on arrivals (`back.out`), follow-through on loose parts (hair, straps, cards rocking), staggered settles.
- Squash/stretch keeps roughly the same area (e.g. scaleX 1.18 × scaleY 0.85).
- Organic motion travels on arcs; exaggerate reactions so they read at phone size.
- Use hold/stepped interpolation (`ease: "steps(n)"`) on purpose for typewriter, ticker or stop-motion beats.
**Sequence**
- Vary shot scale (ECU / medium / wide) and move the camera with purpose (push, pull, follow, punch-in).
- Prefer a match cut (shared shape, colour or position) or a camera-driven transition over a plain cut.
- Pacing follows the VO: captions on word timings, a sound effect on every visible action.
**Channel**
- Hook in the first second; the closing line stays on screen ≥ 2 s.
- Every claim is sourced (research sheet + `caption_txt.sources`); fictional examples are labelled.
