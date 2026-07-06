"""Scaffold a new reel folder.

Usage:
    python new_reel.py 2026-08-02_parramatta-expo

Creates reels/<name>/{input,work,output} and an input/README.md. Then drop the
raw clips into input/ and run the pipeline scripts in order (see reels/README.md).
"""
import os
import re
import sys

from reel_paths import REELS_ROOT


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    name = sys.argv[1]
    if not re.match(r"^\d{4}-\d{2}-\d{2}_[a-z0-9][a-z0-9-]*$", name):
        raise SystemExit("name must look like 2026-08-02_parramatta-expo "
                         "(YYYY-MM-DD_lowercase-slug) so folders sort chronologically")
    reel = os.path.join(REELS_ROOT, name)
    if os.path.exists(reel):
        raise SystemExit(f"already exists: {reel}")
    for sub in ("input", "work", "output"):
        os.makedirs(os.path.join(reel, sub))
    with open(os.path.join(reel, "input", "README.md"), "w", encoding="utf-8") as f:
        f.write("Drop the raw clips for this reel here (phone footage is fine — "
                "the pipeline tone-maps HDR).\n\nThen from reels/ run:\n"
                f"    set PODCUT_REEL={name}\n"
                "    python build_base.py\n"
                "…and the rest of the pipeline (see reels/README.md).\n")
    print(f"scaffolded {reel}")
    print(f"next: put raw clips in {name}/input/, then run the pipeline "
          f"(PODCUT_REEL={name} or just let auto-pick choose the newest).")


if __name__ == "__main__":
    main()
