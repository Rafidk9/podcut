# Motion styles (vendored)

20 deterministic canvas motion templates from the free "20 Claude Motion
Styles" pack (`claude-motion-styles-20.zip`, vendored 2026-10-21). Upstream's
own readme is `UPSTREAM_README.md`. Licence: free to use and remix incl.
client work; don't resell the pack as-is.

- `motion-<style>/template.html` — upstream template, **kept byte-identical**.
  Branding is applied to a temp copy at render time, never to these files.
- `motion-<style>/SKILL.md` — upstream notes: look, motion, colour slots,
  text limits, variations.
- `pfec_presets.json` — PFEC palette per style + sample text + `replace`
  swaps for baked-in demo content.
- `fonts/` — Poppins 300–900 (SIL OFL, `fonts/OFL.txt`), the reels' house font.
- `gallery.html`, `PREVIEW-all-20-styles.{jpg,mp4}` — previews (upstream colours).
- `render_upstream.py` — upstream's renderer, reference only. Use
  `reels/motion_style.py` (branded, pipeline-format encode) instead.

Audited on import: no network calls, external scripts, CDN, storage or cookie
access in any template. Dropped from the pack: 20 duplicate `render.py`
copies and the `upload-to-claude/` zips.

Usage: see "Motion styles" in `reels/README.md`.
