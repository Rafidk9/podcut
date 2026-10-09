"""reels/*.py are flat scripts (no package, sibling imports like
`from reel_paths import ...`), not an installed package -- so tests need
reels/ on sys.path to import them at all."""
import os
import sys
import tempfile

REELS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REELS_ROOT)

# reel_paths picks the active reel at import time and exits if there is none.
# A fresh clone (or CI) has no reel footage -- reel folders' input/ is never
# committed -- so point it at an empty scratch reel instead.
if "PODCUT_REEL" not in os.environ and not any(
        os.path.isdir(os.path.join(REELS_ROOT, d, "input")) for d in os.listdir(REELS_ROOT)):
    os.environ["PODCUT_REEL"] = tempfile.mkdtemp(prefix="podcut_test_reel_")
