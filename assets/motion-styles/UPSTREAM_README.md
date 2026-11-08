# 20 Claude Motion Styles: free skill pack

Twenty ready-to-use **motion-graphics skills** for Claude. Each one is a working animated template plus a frame-exact renderer, so Claude can turn "make me a neon intro that says LIVE" into an MP4 in one go.

Open `PREVIEW-all-20-styles.mp4` to see all of them moving, or open `gallery.html` in Chrome to see them running live.

| # | Style | Skill name | What it makes |
|---|---|---|---|
| 01 | **Particles** | `motion-particles` | Make a particle-swarm motion graphic |
| 02 | **Liquid Morph** | `motion-liquid-morph` | Make liquid-chrome metaball blobs that merge and split with a pastel iridescent sheen |
| 03 | **Holographic** | `motion-holographic` | Make a holographic foil ring |
| 04 | **Neon Glow** | `motion-neon-glow` | Make a neon sign that flickers on |
| 05 | **Wireframe 3D** | `motion-wireframe-3d` | Make a 3D wireframe object (a torus-knot tube) that draws itself on, then spins in perspective |
| 06 | **Glassmorphism** | `motion-glassmorphism` | Make frosted-glass UI widgets (music player, weather and toggle, progress) floating over moving colour blobs |
| 07 | **Kinetic Type** | `motion-kinetic-type` | Make punchy kinetic typography |
| 08 | **Isometric** | `motion-isometric` | Make an isometric block city |
| 09 | **Clay 3D** | `motion-clay-3d` | Make soft clay-style 3D toys (sphere, rounded cube, ring) bouncing with squash and stretch and soft shadows |
| 10 | **ASCII Art** | `motion-ascii-art` | Make ASCII art |
| 11 | **Gradient Mesh** | `motion-gradient-mesh` | Make a flowing mesh gradient |
| 12 | **Comic Book** | `motion-comic-book` | Make a comic-book page |
| 13 | **Split-Flap** | `motion-split-flap` | Make an airport split-flap departures board |
| 14 | **Retro VHS** | `motion-retro-vhs` | Make an 80s synthwave VHS scene |
| 15 | **Halftone** | `motion-halftone` | Make halftone print art |
| 16 | **Bauhaus** | `motion-bauhaus` | Make a Bauhaus geometric grid |
| 17 | **Pixel Art** | `motion-pixel-art` | Make an 8-bit pixel-art scene |
| 18 | **Blueprint** | `motion-blueprint` | Make a technical blueprint |
| 19 | **Art Deco** | `motion-art-deco` | Make an Art Deco gold reveal |
| 20 | **Neo-Brutalism** | `motion-neo-brutalism` | Make neo-brutalist UI motion |

## What's inside each skill

```
motion-neon-glow/
├── SKILL.md        ← instructions Claude follows (look, motion, parameters, workflow)
├── template.html   ← the animation (canvas + plain JS, works offline)
├── render.py       ← renders to MP4 / transparent MOV / PNG
└── preview.jpg
```

## Install

**Claude app (claude.ai / desktop):** open the Skills section in Settings and upload the zips from the `upload-to-claude/` folder, one zip per skill. Add only the ones you want.

**Claude Code:** copy the skill folders into `~/.claude/skills/` (for every project) or `.claude/skills/` (for one project).

Rendering needs Python 3, `pip install playwright && playwright install chromium`, and ffmpeg. Claude's own workspace usually has these already.

## How to ask Claude

- "Use motion-neon-glow: sign says LIVE, sub line TONIGHT 9PM, 9:16, 5 seconds."
- "Kinetic type for my hook: STOP SCROLLING NOW, red and white, square."
- "Particles forming my brand name ACME, gold on black, as a transparent overlay."
- "Split-flap board: NOW|BOARDING|DXB, 16:9."

Every template takes the same controls: size (`--w --h`), duration (`--dur`), main and secondary text (`--text --sub`), colours (`--set c1=ff0000`), and `--alpha` for a transparent background you can lay over footage in Premiere, CapCut, DaVinci or Final Cut.

## Try one yourself, without Claude

```bash
cd motion-kinetic-type
python3 render.py template.html out.mp4 --text "MAKE IT MOVE" --w 1080 --h 1920
```

## Notes

- Everything is original code with no external libraries or CDNs. The templates use system fonts (Inter or Arial fallbacks); to brand them, add your own font file.
- Animations are deterministic (seeded randomness), so the same settings always give the same video.
- Free to use, remix and share, including in client work. Please don't resell the pack as-is.
