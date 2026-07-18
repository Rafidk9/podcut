"""reels/*.py are flat scripts (no package, sibling imports like
`from reel_paths import ...`), not an installed package -- so tests need
reels/ on sys.path to import them at all."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
