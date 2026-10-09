# Logo assets

Put your company logo here.

- **Preferred: `logo.svg`** — HyperFrames renders HTML/CSS, so an SVG can be inlined
  directly, stays crisp at any resolution, and can be animated (color, stroke
  draw-in, path morphs) via GSAP for an animated logo sting if wanted.
- **Also fine: `logo.png`** (transparent background) as a fallback / for raster-only logos.

Once a file is here, PodCut's HyperFrames composition can reference it for
outro cards, corner watermarks, or intro stings.

## PFEC brand mark variants

- **`pfec-logo-colour.svg`** — full-colour mark (navy `.st0` wordmark +
  diagonal tint-ramp bars `.st1`/`.st2` in lighter blue/lavender tones).
  Use on light/white backgrounds only — `.st0`'s navy is low-contrast on
  the brand's own indigo/navy backgrounds.
- **`pfec-logo-white.svg`** — solid-white variant (`.st0`/`.st1`/`.st2` all
  `#FFFFFF`), same shapes/proportions, for use on indigo/navy backgrounds.
  Reference this file directly for any dark-background placement instead
  of inlining the colour SVG and runtime-patching `.st0` to white — the
  old per-file patch only fixed the wordmark's navy and left the diagonal
  tint-ramp bars in blue/lavender, giving a mixed blue+white look instead
  of a clean all-white logo.
