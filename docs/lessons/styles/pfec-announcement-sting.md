# HyperFrames style: PFEC announcement sting

A reusable PFEC-branded HyperFrames motion-graphic style — a short "event announcement" sting (rule-bar → typewriter headline → rotating 3D chrome brand mark → footer lockup). Load this whenever building or editing a PFEC HyperFrames motion graphic, regardless of which project directory the session is in.

**Reference implementation (working, verified composition — clone/adapt this, don't rebuild from scratch):**
`C:\Users\AU-0011-PFEC-G\Downloads\podcut\podcut\videos\pfec-livestream-sting\` (inside the `podcut` git repo, `videos/` subfolder — tracked on GitHub, branch `reel-pipeline-improvements`)
- `index.html` — the composition
- `shot-plan.json` — full IR spec (beats, palette, exact SVG bar coordinates for the hero mark)

Built via the `/motion-graphics` HyperFrames workflow (category `logo-reveal` + hand-authored gaps), 6.5s @ 30fps, 1080x1920 (9:16). Modeled on a Jitter.video "livestream announcement" template, then fully rebranded in PFEC's own identity.

## PFEC brand facts (so this file is self-contained)

- **Colors:** navy/primary `#100796` (near-identical logo variant `#100694`), gold/default accent `#FFC500`, cyan/alt accent `#00B3E3`, red/alert `#E84B37`, green/success `#31EB7C`. Logo tint ramp (dark→light): `#100694` → `#908EC0` → `#C9C9E2`.
- **Font:** Poppins (Google Font), weights 700/900 are real cuts — 800 is synthetic, avoid.
- **Logo:** `C:\Users\AU-0011-PFEC-G\Downloads\podcut\podcut\assets\logo\pfec-logo-colour.svg` (vector) and `...\podcut\podcut\assets\derived\logo_colour_1000.png` (raster, transparent bg). Abstract mark = 3 diagonal parallelogram bars, tint-ramp left to right. **No light/dark-mode variant exists** — the wordmark text and darkest bar are navy (`#100694`/`.st0`), so placed directly on a navy background they're nearly invisible. See gotcha below.
- **Company:** PFEC Global — Education | Migration. Website `www.pfecglobal.com.au`. Social handle `@PFECGlobal`.

## The style, beat by beat

1. Flat solid PFEC-navy (`#100796`) background, no gradient/texture.
2. Gold (`#FFC500`) horizontal rule-bar wipes in left-to-right (~0.3–0.8s), holds.
3. Multi-line headline types on one line at a time (typewriter effect), Poppins 900, gold, blinking cursor per line, small inline icon before one line.
4. A glossy "chrome" 3D hero mark (built from PFEC's 3-bar logo geometry) scales/fades in, then auto-rotates continuously as the visual anchor.
5. Footer row: logo lockup bottom-left, CTA text bottom-right.

## Build gotchas (learned the hard way — don't re-discover these)

- **Typewriter reveal:** implement as a deterministic mask-width tween (measure `scrollWidth` at build time, animate CSS `width` from 0), not literal character-by-character DOM stepping — stays seek-safe/deterministic per HyperFrames' render contract (no `Date.now()`/`Math.random()`).
- **Rotating flat 3D marks go illegible fast.** A thin flat-slab shape (extruded via a CSS 3D `translateZ` depth-layer stack, not a chunky/rounded object) turns into an unreadable edge-on sliver past roughly 35–40° of `rotateY` yaw. Cap the total on-screen rotation (e.g. ~36°) rather than letting it sweep toward 90–100°+, or the hero visual disappears exactly when it should be most prominent (typically right at the final hold frame).
- **Don't rely on flex-fill-to-bottom for a bottom-pinned `.clip` element.** A footer row that was both a flex child of the stage container AND a `.clip` (framework-toggled visibility) rendered pinned near the TOP instead of the bottom — root cause not fully isolated, but the reliable fix is explicit `position: absolute; left/right: <margin>; bottom: <margin>` on the footer, independent of the parent's flex flow.
- **PFEC's logo has no light/dark-mode variant** (see above). Fix for a dark-background placement: inline the logo SVG directly (don't use the flattened raster PNG) and override its `.st0` (navy) fill to white via CSS; leave the lighter tint-ramp bars (`.st1`/`.st2`) unchanged since they already read fine on navy.
- **Verify beyond the contact-sheet thumbnail.** The footer-position bug and the navy-on-navy logo bug were both invisible at contact-sheet thumbnail scale and were only caught by reading full-resolution snapshot frames — for position bugs, an objective pixel-bbox scan (not just eyeballing) is worth the extra step.

## Process notes

- Route: `/hyperframes` → `/motion-graphics` (short, unnarrated, motion-first, <10s → this route). Longer/narrated PFEC pieces belong to a different route — see `/hyperframes`'s routing table.
- The motion-graphics workflow dispatches a Director subagent (writes `shot-plan.json`) then a Builder subagent (writes the composition). Always run `npx hyperframes snapshot --at <beat times>` afterward and independently inspect full-res frames before approving — don't just trust a subagent's self-report of "fixed" (see gotchas above for what slipped through a first pass).
