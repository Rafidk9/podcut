"""Resolve which reel folder the pipeline scripts operate on.

Layout: every reel lives in its own folder under reels/, named
<YYYY-MM-DD>_<slug> (date of the event/publication), each containing
input/ (raw clips), work/ (intermediates), output/ (final mp4 + caption.txt).
The pipeline scripts stay shared at reels/ and act on ONE reel at a time:

  - set PODCUT_REEL to a folder name (or absolute path) to pick a reel, or
  - leave it unset to use the newest reel (date-prefixed names sort
    chronologically, so lexicographically-last == newest).

Shared brand assets (logo, end cards, music) are NOT per-reel; they stay in
podcut/assets.
"""
import os
import sys

REELS_ROOT = os.path.dirname(os.path.abspath(__file__))
PODCUT_ROOT = os.path.dirname(REELS_ROOT)
ASSETS_ROOT = os.path.join(PODCUT_ROOT, "assets")


def _is_reel(name: str) -> bool:
    return os.path.isdir(os.path.join(REELS_ROOT, name, "input"))


def reel_dir() -> str:
    env = os.environ.get("PODCUT_REEL")
    if env:
        p = env if os.path.isabs(env) else os.path.join(REELS_ROOT, env)
        if not os.path.isdir(p):
            raise SystemExit(f"PODCUT_REEL points at a missing folder: {p}")
        return p
    reels = sorted(d for d in os.listdir(REELS_ROOT) if _is_reel(d))
    if not reels:
        raise SystemExit("no reel folders under reels/ (expected <date>_<slug>/input/)")
    picked = os.path.join(REELS_ROOT, reels[-1])
    print(f"[reel] {os.path.basename(picked)} (set PODCUT_REEL to override)")
    return picked


REEL = reel_dir()
IN = os.path.join(REEL, "input")
WORK = os.path.join(REEL, "work")
OUT = os.path.join(REEL, "output")
os.makedirs(WORK, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def hyperframes_cli() -> str:
    """Resolve the HyperFrames CLI script (dist/cli.js) so every reel script
    works on any machine that has this repo checked out -- not just the one
    HYPERFRAMES_PATH (engine/.env) happened to be set up on.

    HYPERFRAMES_PATH is a per-machine dev setting; it can go stale (point at a
    checkout that only ever existed on whoever's machine set it up). Prefer it
    if it actually resolves, otherwise fall back to the copy vendored in this
    repo under tools/hyperframes -- that one travels with the repo."""
    sys.path.insert(0, os.path.join(PODCUT_ROOT, "engine"))
    from podcut.config import Providers  # noqa: E402

    configured = Providers().hyperframes_path
    if configured and os.path.isfile(os.path.join(configured, "dist", "cli.js")):
        return os.path.join(configured, "dist", "cli.js")

    vendored = os.path.join(PODCUT_ROOT, "tools", "hyperframes", "node_modules", "hyperframes")
    if os.path.isfile(os.path.join(vendored, "dist", "cli.js")):
        return os.path.join(vendored, "dist", "cli.js")

    raise SystemExit(
        "Can't find the HyperFrames CLI (checked HYPERFRAMES_PATH and "
        "podcut/tools/hyperframes/node_modules/hyperframes) -- set "
        "HYPERFRAMES_PATH or `npm install` under tools/hyperframes.")
