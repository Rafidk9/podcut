# Lessons & learnings

Snapshot (2026-11-09) of rules and reusable styles learned while making PFEC reels.
Their live copies sit outside this repo, in Claude Code's memory and in `~/.claude/styles` / `~/.claude/skills`.
They're mirrored here so they survive a new machine. Re-sync them when they change.

- `feedback/`: editorial and production rules from reel reviews (VO pronunciation of acronyms
  and codes, no text overlaps / one-take transitions, a visual per sentence, relatable examples,
  storyboard before render, go deep not surface) plus the IG reel rules.
- `styles/`: reusable HyperFrames styles (PFEC announcement sting, torn-paper title,
  six explainer styles) with reference frames in `styles/assets/`.
- `skills/pfec-longtake/`: the in-house, commercial-safe continuous-take skill that drives `tools/longtake/`.
  Its licence is separate from onetake, which is for the non-profit wing only. Never copy onetake code here.

Per-pipeline lessons also live in `/CLAUDE.md` and `reels/README.md`.
