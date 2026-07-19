"""Run the full reel pipeline in the order documented in reels/README.md:
build_base -> (bg_swap, if this reel has one) -> build_broll -> build_wipe ->
insert_broll -> build_captions -> build_composite -> build_caption_txt ->
build_thumbnail -> qa_reel.

Usage:
    python build_all.py             # full build
    python build_all.py --preview   # fast draft build, never a deliverable --
                                     # see reel_paths.py's PREVIEW docstring

--preview: lower HyperFrames render quality, isolated work_preview/
intermediates, single-pass loudnorm (no limiter), and two stages skipped
entirely -- bg_swap.py (rembg matting is the most expensive single step in
the whole pipeline) and build_thumbnail.py (a still grabbed from the
non-existent deliverable makes no sense). qa_reel.py still runs and will
refuse the preview output as a deliverable (see its own docstring)."""
import importlib.util
import os
import sys

from reel_paths import REEL, PREVIEW  # noqa: E402 -- per-reel folders
import build_base
import build_broll
import build_wipe
import insert_broll
import build_captions
import build_composite
import build_caption_txt
import build_thumbnail
import qa_reel


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    if PREVIEW:
        print("[build_all] --preview: draft quality, isolated work_preview/, "
              "several stages skipped -- never a deliverable\n")

    print("[build_all] build_base.py")
    build_base.main()

    bg_swap_path = os.path.join(REEL, "bg_swap.py")
    if os.path.isfile(bg_swap_path):
        if PREVIEW:
            print("[build_all] bg_swap.py: skipped: preview mode")
        else:
            print("[build_all] bg_swap.py")
            _load_module(bg_swap_path, "reel_bg_swap").main()

    print("[build_all] build_broll.py")
    build_broll.main()

    print("[build_all] build_wipe.py")
    build_wipe.build()

    print("[build_all] insert_broll.py")
    insert_broll.main()

    print("[build_all] build_captions.py")
    build_captions.build(no_cache="--no-cache" in sys.argv, clear_cache="--clear-cache" in sys.argv)

    print("[build_all] build_composite.py")
    build_composite.main()

    print("[build_all] build_caption_txt.py")
    build_caption_txt.build()

    if PREVIEW:
        print("[build_all] build_thumbnail.py: skipped: preview mode")
    else:
        print("[build_all] build_thumbnail.py")
        build_thumbnail.build()

    print("[build_all] qa_reel.py")
    qa_code = qa_reel.main()
    if PREVIEW and qa_code:
        print("[build_all] preview build finished (QA correctly refused it as "
              "a deliverable -- this is expected, not a failure)")
        return 0
    return qa_code


if __name__ == "__main__":
    sys.exit(main())
