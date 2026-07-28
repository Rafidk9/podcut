"""Loud-warning check for <reel>/content.json top-level keys.

content.json has grown to ~24 recognized top-level keys across build_base.py
(zoom), build_composite.py (music, sfx, voice_denoise), build_captions.py
(most of them), build_thumbnail.py (thumbnail), and build_caption_txt.py
(caption_txt) -- documented only via inline comments spread across those
files. A typo'd key (e.g. "hero_word" instead of "hero_words") currently
fails SILENTLY: the feature just doesn't render, with no error anywhere.
This doesn't replace fixing that at the source -- it's a cheap net that
catches the typo class of bug before a multi-minute build finds out the
hard way. NOT a hard failure -- a new legitimate key added ahead of updating
this list shouldn't block a build, only get flagged."""
import json
import os

# Every top-level content.json key any build_*.py script reads. Update this
# alongside adding a new one (see the docstring above for why this is a
# warning, not a schema that blocks unrecognized keys).
KNOWN_KEYS = {
    "asr_fix", "gold", "name", "mara", "info", "cta", "documents",
    "cap_top", "list_top", "decor", "lists", "badges", "dm_bubbles", "roadshow",
    "urgency_chip", "hero_words", "hook_banner", "save_prompt", "flight_map",
    "landmark_sweep",
    "caption_highlight", "music", "sfx", "voice_denoise", "zoom",
    "thumbnail", "caption_txt", "accent",
}


def check(reel_dir):
    """Print a warning per unrecognized top-level key. No-op if content.json
    doesn't exist (that's valid -- every reel is opt-in per feature)."""
    cfg = os.path.join(reel_dir, "content.json")
    if not os.path.isfile(cfg):
        return
    content = json.load(open(cfg, encoding="utf-8"))
    # A leading underscore marks an intentional in-file note (e.g. "_comment",
    # "_zoom_note") rather than a field any script reads -- reels use these to
    # explain a non-obvious timing or ASR decision, so don't flag them.
    unknown = sorted(k for k in set(content.keys()) - KNOWN_KEYS
                     if not k.startswith("_"))
    for key in unknown:
        print(f"  [content_check] WARNING: content.json has unrecognized top-level "
              f"key {key!r} -- typo? (or update content_check.KNOWN_KEYS if this is "
              f"a genuinely new field)")
