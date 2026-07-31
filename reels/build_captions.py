"""PFEC reel captions + overlay cards: 2-word UPPERCASE Poppins Bold chunks with
real kinetic motion (back-ease overshoot entrance, gold-keyword pulse), plus
overlay cards (top kicker for the seminar date, bottom red-pill CTA, and
optional document-highlight "paper card + stamp" cards -- e.g. a redacted
visa grant letter -- placed wherever the transcript's anchor_phrase resolves).

Architecture: render ONLY the graphics as a TRANSPARENT layer via HyperFrames
(fast -- Chrome never touches the footage), then ffmpeg-composite that overlay
onto base_broll.mp4 (one clean encode, footage/B-roll quality preserved)."""
import os, json, shutil, subprocess, sys

from reel_paths import WORK, REEL, ASSETS_ROOT, HF_QUALITY, HF_FPS, X264_PRESET, hyperframes_cli  # noqa: E402 -- per-reel folders
from anchor_phrase import resolve_anchor  # noqa: E402 -- per-reel folders
from ffmpeg_util import FF, FFPROBE, COLOR_TAGS, run  # noqa: E402 -- shared ffmpeg wrappers
import caption_cache  # noqa: E402 -- per-reel folders

FILLERS = {"um", "uh", "erm", "er", "ah", "hmm", "mm", "mm-hmm", "mmhmm", "uh-huh"}
SENTENCE_END = (".", "?", "!")
MARA_BADGE_CROP = "1030:920:112:165"   # ffmpeg crop=w:h:x:y -> just the badge

# Per-reel content. DEFAULT_CONTENT reproduces the Lakemba reel exactly; any reel
# can override any key via <reel>/content.json (see load_content()). Card times
# are on the OUTPUT timeline (unaffected by B-roll splicing). The "info" card
# reuses a 3-beat top card (kicker / big line1 / smaller line2). "name" + "mara"
# render as ONE merged lower-third (badge tile + name/role panel) sharing
# "name"'s start/end -- "mara" no longer carries its own timing. MARA badge
# "mode": "image" = official OMARA sticker PNG in the tile; "styled" = a CSS/SVG
# recreation of that same sticker (dotted-Australia map + registration number)
# for agents with no official artwork on file; "none" = no badge tile at all
# (presenter isn't a registered migration agent, e.g. an education counsellor
# or team lead -- "marn" is ignored in this mode) -- the info-panel (name/role)
# fills the full card width instead.
DEFAULT_CONTENT = {
    "asr_fix": {"pfc": "PFEC", "pfpc": "PFEC", "ils": "IELTS"},
    # {} = this project's usual gold/red lead; see _set_accent() to shift it.
    "accent": {},
    "gold": ["VISA", "EOI", "IELTS", "PTE", "NAATI", "189", "POINTS", "PR",
             "RESIDENCY", "PERMANENT", "PATHWAY", "PATHWAYS", "MIGRATION",
             "SEMINAR", "PFEC", "ASSESSMENT", "INVITATION", "ROUND"],
    "name": {"text": "Niyama Tabassum", "role": "Education Counsellor",
             "start": 0.6, "end": 4.8},
    "mara": {"mode": "image",
             "src": os.path.join(ASSETS_ROOT, "marn designs", "Ali's MARN.png"),
             "marn": "2117037"},
    "info": {"kicker": "FREE MIGRATION SEMINAR", "line1": "13 JULY", "line1_size": 80,
             "line2": "Lakemba Senior Citizens' Centre", "start": 40.2, "end": 43.5},
    # "subheading" (opt-in, default "" = no subheading, container sits at the
    # usual y1420): a short line above the pill, e.g. a rhetorical hook --
    # "Ready to start your Nursing Journey?" -- the container shifts up so
    # the pill itself still lands at its usual position either way.
    "cta": {"text": "REGISTER NOW!", "subheading": "", "start": 48.75, "end": 50.75},
    # Document highlights (e.g. redacted visa grant letters): each entry names
    # an anchor_phrase (words as spoken, NOT a timecode) -- resolve_anchor()
    # locates it in the transcript. "image" is a filename under <reel>/documents/
    # (put the letter-redactor's REDACTED output there, never the raw original).
    "documents": [],   # e.g. [{"image": "grant1.png", "anchor_phrase": "his 189 grant came through", "label": "189 VISA GRANT"}]
    # Vertical anchor of the 2-word caption band (CSS top, band is centred on it
    # via translateY(-50%)). Default 62% suits a normally-framed talking head;
    # raise it (smaller %) toward the headroom when the subject sits low in frame
    # so captions never land on their face.
    "cap_top": "62%",
    # Vertical anchor of the animated checklist card ("lists" below). Default
    # 44% suits a normally-framed talking head; raise this (larger %) when the
    # subject sits lower/larger in frame so the card clears their chin instead
    # of covering their mouth while they keep talking through it.
    "list_top": "44%",
    # Light decorative layer for reels with lots of dead wall space (subject
    # framed small / plain backdrop). OFF by default. Per reel:
    #   "decor": {"handle": "@PFECGlobal", "accents": true}
    # "accents" = soft, low-opacity brand-colour orbs that drift gently in the
    # empty margins; "handle" = a small social handle pill low-centre. Both sit
    # BEHIND the captions/cards and animate on the same seek-safe timeline.
    "decor": {},
    # Animated checklist overlays (opt-in). When the speaker LISTS several items,
    # they tick into a designed panel one at a time instead of just flashing past
    # as 2-word captions. Each spec names an anchor_phrase (the listing as spoken)
    # -> resolve_anchor locates the window; each item's own time is resolved
    # inside that window so it lands as it's said. The plain 2-word caption is
    # SUPPRESSED inside the window so the checklist is the clean focus. e.g.:
    #   "lists": [{"anchor_phrase": "eligibility qualifications and visa options",
    #              "title": "WE ASSESS YOUR",
    #              "items": ["Eligibility", "Qualifications", "Visa options"]}]
    "lists": [],
    # Visa-pathway chain (opt-in): a 3-step "A -> B -> C" flow with an icon per
    # step and animated arrows drawing between them, sitting under a stylized
    # Australia map with one city pinned. Use it when the speaker describes a
    # SEQUENCE (student visa -> 485 -> PR) rather than an unordered list --
    # "lists" ticks items off, this one shows progression. Like "lists" it owns
    # its window and suppresses the plain 2-word caption there. e.g.:
    #   "pathway": {"anchor_phrase": "from student visa to a temporary graduate 485",
    #     "kicker": "YOUR PATH IN WA", "top": "600px", "city": "PERTH",
    #     "pad_after": 4.4,
    #     "steps": [{"label": "Student Visa", "sub": "Subclass 500", "icon": "cap"},
    #               {"label": "SC485", "sub": "Temporary Graduate", "icon": "brief"},
    #               {"label": "PR Pathway", "sub": "Permanent Residency", "icon": "flag"}]}
    # "city" must be a key of _AU_CITY_VB; "icon" is cap | brief | flag | people
    # | star | check | medical. Exactly 3 steps fit the 960px card -- more will overflow.
    "pathway": {},
    # Quick emphasis badges (opt-in): a small designed icon+text pill that pops
    # in at a key spoken moment, floats, then leaves -- for punching up the hook
    # and a couple of payoff beats. anchor_phrase-driven (same rule as the rest);
    # icon: check|star|brief|people|flag|medical, color: navy|cyan|green|gold|red, pos: top|top-left|
    # top-right (all sit in the upper zone, clear of the caption band + face).
    # "effect" (opt-in, per-badge, catalog-sourced -- see registry blocks/
    # components explored via `hyperframes catalog`): none/absent = the
    # default pop+float+exit; "particles" = a burst of small dots radiates
    # from the badge on entrance (adapted from the catalog's
    # caption-particle-burst component -- suits alarm/urgency badges);
    # "shimmer" = a light sweep crosses the pill right after it settles
    # (adapted from the catalog's shimmer-sweep component -- suits
    # value/premium badges); "pixelate" = the pill materializes out of a
    # small grid of cells instead of scaling in (adapted from the catalog's
    # grid-pixelate-wipe component -- the SAME technique already used for
    # this reel's cut transitions, so it reads as a brand callback; suits an
    # announcement/reveal badge). Use effects deliberately, not on every
    # badge -- variety comes from contrast against a plain baseline, not
    # from every element doing something different. e.g.:
    #   "badges": [{"anchor_phrase": "successfully hired", "text": "YOU GET HIRED",
    #               "icon": "check", "color": "green", "pos": "top", "effect": "shimmer"}]
    "badges": [],
    # DM/notification mockup (opt-in): a small phone-style incoming-message
    # card pops in at a key spoken moment -- for a beat where the speaker is
    # literally describing someone messaging/DMing them. anchor_phrase-driven
    # (same rule as the rest). "flag": "red" (default) tints the card's border/
    # glow danger-red and gives it a small shady wobble -- suits an unsolicited/
    # scammy DM (e.g. "random agent DM-ing you, guaranteed PR"); "green" tints
    # it brand-teal with a calmer settle, no wobble -- suits a legitimate
    # message. "sender"/"avatar" (emoji)/"message" are the mockup's own text --
    # keep "message" short (it's rendered at real notification size, not a
    # caption). e.g.:
    #   "dm_bubbles": [{"anchor_phrase": "DM-ing you", "sender": "unknown_agent",
    #     "avatar": "👤", "message": "GUARANTEED PR!! 💰 dm me now",
    #     "flag": "red"}]
    "dm_bubbles": [],
    # Multi-city roadshow/event card (opt-in): unlike "info" (ONE kicker/date/
    # venue, meant for a short beat), this pins a kicker + a stacked list of
    # city cards (date/time/venue each) on screen for a LONG window -- e.g.
    # from the moment the speaker says "limited spots" through to near the
    # end of the video, so viewers have time to actually read/screenshot every
    # city's details. Explicit "start"/"end" (not anchor_phrase-resolved) since
    # the intent is usually "hold this until the video's almost over", not a
    # single spoken moment. Sits in the upper zone (clear of the 62% caption
    # band and the bottom CTA slot). e.g.:
    #   "roadshow": {"kicker": "MIGRATION 360 ROADSHOW", "top": "900px",
    #     "start": 34.7, "end": 40.1, "cities": [{"city": "ADELAIDE",
    #     "date": "4 AUGUST", "time": "12 PM ONWARDS",
    #     "venue": "PFEC Global Adelaide Office"}, ...]}
    # "top" (CSS value, default "130px") -- pick it from where THIS footage's
    # face/headroom actually is (check a frame), not a fixed guess; a talking
    # head can be framed higher/lower/closer take to take.
    "roadshow": {"kicker": "", "top": "130px", "start": 0.0, "end": 0.0, "cities": []},
    # Urgency chip (opt-in): a small pill just above the roadshow kicker,
    # sharing the roadshow card's on-screen window. Static text -- compute
    # any "N DAYS TO GO" wording at BUILD time (Python, off the reel's real
    # calendar) and pass the finished string; never compute a live date in
    # the browser JS, since HyperFrames re-seeks/re-renders frames and needs
    # every value fixed ahead of time. e.g.: {"text": "18 DAYS TO GO"}
    "urgency_chip": {"text": ""},
    # Flying-plane multi-city map (opt-in): a small stylized Australia
    # silhouette (same brand shape as build_opener.py's cold-open) with a
    # plane emoji hopping city to city in the given order, each landing
    # marked with a pin + impact pulse + city/date label that stays on
    # screen (accumulates, like "roadshow"'s stacked cards). Explicit
    # start/end (own dedicated visual beat, not anchor_phrase-resolved).
    # City positions are looked up by name from a fixed built-in map
    # (_AU_CITY_VB) -- only name the city + date here, not coordinates.
    # e.g.: {"flight_map": {"kicker": "5 CITIES. ONE ROADSHOW.", "top": "600px",
    #   "start": 23.7, "end": 27.9, "cities": [{"city": "PERTH", "date": "4 AUG"},
    #   {"city": "ADELAIDE", "date": "6 AUG"}, ...]}}
    "flight_map": {"kicker": "", "top": "600px", "start": 0.0, "end": 0.0, "cities": []},
    # Landmark sweep (opt-in): a small icon+name/date chip per city sweeps
    # across the headroom band as a FRONT overlay, timed to the moment the
    # speaker actually says that city's name -- never behind the subject, so
    # it always reads clearly. "top" (default "300px") -- pick clear
    # headroom from a real frame of THIS footage. e.g.:
    #   "landmark_sweep": {"top": "260px", "cities": [
    #     {"city": "PERTH", "date": "4 AUG"}, {"city": "ADELAIDE", "date": "6 AUG"}]}
    # Known glyphs live in _LANDMARK_SVG -- a city with no glyph is skipped
    # with a loud warning, never silently dropped or guessed at.
    "landmark_sweep": {"top": "300px", "cities": []},
    # Full-screen "hero word" slam (opt-in, sparingly): like "lists"/
    # "roadshow", each entry names an anchor_phrase and OWNS that window --
    # the normal 2-word caption is suppressed there and this renders instead:
    # one giant centered word/phrase, punch-scale entrance, brief hold, quick
    # exit. Reserve for the single strongest hook or payoff line in a reel;
    # using it more than once or twice defeats the point (impact comes from
    # rarity). e.g.: [{"anchor_phrase": "stop scrolling", "text": "SCROLLING"}]
    "hero_words": [],
    # Tiny top-of-frame hook banner (opt-in), on screen only for the first
    # beat before the viewer's thumb decides to scroll past. Sits above the
    # logo's row (y<38) is too tight -- pin it just below the intro card
    # instead via explicit start/end, short window (~1s). e.g.:
    #   "hook_banner": {"text": "READ THIS IF YOU'RE ON A STUDENT VISA",
    #                   "start": 0.0, "end": 0.9}
    "hook_banner": {"text": "", "start": 0.0, "end": 0.0},
    # Save/share prompt (opt-in): a closing beat late in a long dwell window
    # (pass the same start/end as e.g. "roadshow" minus a couple seconds) --
    # native engagement bait for advice/informational content, not a hard
    # sell like the CTA pill. e.g.:
    #   "save_prompt": {"text": "SAVE THIS FOR LATER", "start": 33.5, "end": 35.0}
    "save_prompt": {"text": "", "start": 0.0, "end": 0.0},
    # Caption background-highlight mode (opt-in, boolean): gives every 2-word
    # caption card a solid rounded-box background behind the text (adapted
    # from the catalog's caption-highlight component, brand colour instead of
    # TikTok red) instead of plain drop-shadowed text on the raw footage --
    # the native short-form-platform caption look. Off by default so every
    # existing reel keeps rendering exactly as before.
    "caption_highlight": False,
}

# Small dot-matrix silhouette of mainland Australia (same visual language as
# the cold-open world map in build_opener.py), reused here as the icon on the
# recreated OMARA sticker for agents with no official artwork on file.
_AU_DOTS = [
    "..111100.",
    "..1111111",
    ".11111111",
    "11111111.",
    "..111111.",
    "....1....",
]


def _dotmap_html():
    cells = []
    for row in _AU_DOTS:
        for ch in row:
            cells.append('<i class="on"></i>' if ch == "1" else "<i></i>")
    return "".join(cells)


# Eyeballed viewBox (0-100 x, 0-86 y) positions on the SAME stylized Australia
# path used by build_opener.py's cold-open (#aus svg, viewBox "0 0 100 86")
# -- Sydney is calibrated there at (75,45) and Tasmania at (66,70) (the
# separate ellipse south of the mainland path); these five are placed
# relative to those two known points, not a precise geographic projection
# (the underlying shape itself is a stylized silhouette, not a real map).
_AU_CITY_VB = {
    "PERTH": (14, 32), "ADELAIDE": (38, 56), "BRISBANE": (78, 26),
    "MELBOURNE": (64, 62), "TASMANIA": (68, 78), "SYDNEY": (75, 45),
    # Split out of the combined "TASMANIA" point for reels that name the two
    # Tasmanian legs individually -- Launceston sits in the state's north,
    # Hobart in the south, so nudge them apart from the original point.
    "HOBART": (69, 81), "LAUNCESTON": (66, 74),
}

# Bold flat-vector glyphs for content.json "landmark_sweep" -- one iconic,
# recognizable silhouette per city (never scraped/generated photography, so
# no licensing risk in commercial reels). viewBox 0 0 100 100, white fill
# with a gold accent, sized/read at ~118px so kept deliberately simple.
_LANDMARK_SVG = {
    "MELBOURNE": (
        '<svg viewBox="0 0 100 100">'
        '<rect x="10" y="55" width="10" height="30" fill="#fff"/>'
        '<rect x="24" y="45" width="10" height="40" fill="#fff"/>'
        '<rect x="38" y="35" width="12" height="50" fill="#fff"/>'
        '<rect x="54" y="50" width="9" height="35" fill="#fff"/>'
        '<rect x="66" y="40" width="12" height="45" fill="#fff"/>'
        '<rect x="44" y="10" width="4" height="28" fill="#fff"/>'
        '<rect x="42.5" y="10" width="7" height="7" fill="#FFC500"/>'
        '<line x1="5" y1="85" x2="90" y2="85" stroke="#fff" stroke-width="3"/></svg>'),
    "ADELAIDE": (
        '<svg viewBox="0 0 100 100">'
        '<ellipse cx="50" cy="55" rx="38" ry="26" fill="none" stroke="#fff" stroke-width="5"/>'
        '<ellipse cx="50" cy="55" rx="24" ry="16" fill="none" stroke="#FFC500" stroke-width="3"/></svg>'),
    "PERTH": (
        '<svg viewBox="0 0 100 100">'
        '<rect x="46" y="15" width="6" height="55" fill="#fff"/>'
        '<path d="M52 15 L78 48 L52 60 Z" fill="#FFC500"/>'
        '<path d="M10 75 Q50 95 90 75" fill="none" stroke="#fff" stroke-width="4"/></svg>'),
    "BRISBANE": (
        '<svg viewBox="0 0 100 100">'
        '<line x1="8" y1="65" x2="92" y2="65" stroke="#fff" stroke-width="4"/>'
        '<rect x="22" y="30" width="5" height="35" fill="#fff"/>'
        '<rect x="73" y="30" width="5" height="35" fill="#fff"/>'
        '<path d="M15 65 Q50 20 85 65" fill="none" stroke="#FFC500" stroke-width="4"/></svg>'),
    "HOBART": (
        '<svg viewBox="0 0 100 100">'
        '<polygon points="50,10 10,80 90,80" fill="#fff"/>'
        '<line x1="30" y1="40" x2="30" y2="55" stroke="#100796" stroke-width="2"/>'
        '<line x1="40" y1="35" x2="40" y2="52" stroke="#100796" stroke-width="2"/>'
        '<line x1="50" y1="32" x2="50" y2="50" stroke="#100796" stroke-width="2"/>'
        '<line x1="60" y1="35" x2="60" y2="52" stroke="#100796" stroke-width="2"/>'
        '<line x1="70" y1="40" x2="70" y2="55" stroke="#100796" stroke-width="2"/>'
        '<path d="M10 88 Q50 98 90 88" fill="none" stroke="#FFC500" stroke-width="3"/></svg>'),
    "LAUNCESTON": (
        '<svg viewBox="0 0 100 100">'
        '<polygon points="8,85 8,45 35,60 35,85" fill="#fff"/>'
        '<polygon points="92,85 92,38 65,55 65,85" fill="#fff"/>'
        '<path d="M35 60 Q50 45 65 55" fill="none" stroke="#FFC500" stroke-width="4"/>'
        '<line x1="35" y1="60" x2="35" y2="40" stroke="#FFC500" stroke-width="3"/>'
        '<line x1="65" y1="55" x2="65" y2="35" stroke="#FFC500" stroke-width="3"/></svg>'),
}


def load_content():
    import copy
    c = copy.deepcopy(DEFAULT_CONTENT)
    cfg = os.path.join(REEL, "content.json")
    if os.path.isfile(cfg):
        for k, v in json.load(open(cfg, encoding="utf-8")).items():
            if isinstance(v, dict) and isinstance(c.get(k), dict):
                c[k].update(v)
            else:
                c[k] = v   # lists (e.g. "documents") replace wholesale, not merge
    _set_accent(c.get("accent") or {})
    return c


# Per-reel accent override. The caption/hero styling in _CAP_BLOCK hardcodes
# this project's usual lead colours (gold #FFC500 words, red #E84B37 highlight
# boxes). A reel can shift that lead via content.json:
#
#   "accent": {"word": "#00B3E3", "highlight_bg": "#0a63c4",
#              "highlight_word_bg": "#100796", "hero": "#00B3E3"}
#
# Every key is optional and every value should still be a brand colour --
# this shifts WHICH brand colour leads, it does not invent new ones. Stored
# module-level because per-element renders (_render_cacheable) style
# themselves from the same stylesheet but only receive their own element's
# content dict, not the reel's.
_ACCENT_CSS = ""


def _set_accent(accent):
    global _ACCENT_CSS
    rules = []
    word = accent.get("word")
    hero = accent.get("hero", word)
    hl_bg = accent.get("highlight_bg")
    hl_word_bg = accent.get("highlight_word_bg")
    if word:
        rules.append(".w.gold{color:%s}" % word)
    if hl_bg:
        rules.append("#cap.highlight .w{background:%s}" % hl_bg)
    if hl_word_bg or word:
        # In highlight mode the accent word is a filled box, so its text needs
        # its own colour -- reusing "word" here would put the accent colour on
        # an accent-coloured box and make it unreadable.
        rules.append("#cap.highlight .w.gold{background:%s;color:%s}"
                     % (hl_word_bg or "#100796",
                        accent.get("highlight_word_fg") or word or "#FFC500"))
    if hero:
        rules.append(".hero-slam span{color:%s}" % hero)
    _ACCENT_CSS = "\n  ".join(rules)


def norm(t):
    return t.strip().strip(".,!?;:'\"").lower()


def crop_mara_badge(dest_dir, src):
    """Tight-crop the official MARA mark into <dest>/mara_badge.png (removes the
    white margin so it mounts cleanly on the navy plate)."""
    run(["-i", src, "-vf", f"crop={MARA_BADGE_CROP}",
         os.path.join(dest_dir, "mara_badge.png")])


def load_words(content):
    asr_fix = content["asr_fix"]
    d = json.load(open(os.path.join(WORK, "assembled.transcript.json")))
    out = []
    for w in d["words"]:
        n = norm(w["text"])
        if n in FILLERS:
            continue
        text = w["text"]
        if n in asr_fix:
            trail = text[len(text.rstrip(".,!?;:")):]
            text = asr_fix[n] + trail
        out.append({"text": text, "start": w["start"], "end": w["end"]})
    return out


def chunk_2word(words):
    chunks, i = [], 0
    while i < len(words):
        w = words[i]
        if w["text"].strip().endswith(SENTENCE_END) or i + 1 >= len(words):
            chunks.append([w]); i += 1
        else:
            chunks.append([w, words[i + 1]]); i += 2
    return chunks


def make_proj(base):
    """Generate the transparent captions/overlay HyperFrames project (cap_proj)
    for the given base video (used for its duration). No render — returns
    (proj_dir, n_cards). Split out so the layout can be live-previewed fast."""
    content = load_content()
    gold = set(g.upper() for g in content["gold"])
    words = load_words(content)
    chunks = chunk_2word(words)

    # Animated checklist overlays: resolve each list's window + each item's own
    # time (searched only WITHIN the window so a word that recurs elsewhere in
    # the reel can't hijack it), then suppress the plain 2-word caption inside
    # the window so the ticking list is the clean focus.
    lists = []
    for spec in content.get("lists", []):
        lstart, lend, score = resolve_anchor(words, spec["anchor_phrase"], pad_after=0.2)
        if lstart is None:
            print(f"  [lists] SKIPPING {spec.get('title') or spec['items']!r}: anchor_phrase "
                  f"{spec['anchor_phrase']!r} not found (best {score:.2f} < 0.8)")
            continue
        items = spec["items"]
        win = [w for w in words if lstart <= w["start"] <= lend]
        span = max(0.8, lend - lstart)
        times = []
        for i, it in enumerate(items):
            s, _e, _sc = resolve_anchor(win, it, pad_before=0.05, pad_after=0.0)
            times.append(round(s, 3) if s is not None
                         else round(lstart + 0.2 + i * (span - 0.9) / max(1, len(items)), 3))
        lists.append({"title": spec.get("title", ""), "items": items, "times": times,
                      "start": round(lstart, 3), "end": round(lend, 3)})
        print(f"  [lists] {spec.get('title')!r} {items} -> {lstart:.2f}s-{lend:.2f}s "
              f"(anchor match {score:.2f})")

    def _in_list_window(t):
        return any(l["start"] <= t < l["end"] for l in lists)

    # Visa-pathway chain: one per reel, same anchor + own-window + caption
    # suppression contract as "lists". pad_after is usually generous here --
    # the speaker typically keeps talking through the steps he just named, and
    # the chain should stay up for that whole explanation rather than vanish
    # on the last word of the anchor phrase.
    pathway = None
    pw_spec = content.get("pathway") or {}
    if pw_spec.get("steps"):
        pstart, pend, score = resolve_anchor(
            words, pw_spec["anchor_phrase"],
            pad_before=pw_spec.get("pad_before", 0.15),
            pad_after=pw_spec.get("pad_after", 0.3))
        if pstart is None:
            print(f"  [pathway] SKIPPING: anchor_phrase {pw_spec['anchor_phrase']!r} "
                  f"not found (best {score:.2f} < 0.8)")
        elif pw_spec.get("city") and pw_spec["city"].upper() not in _AU_CITY_VB:
            print(f"  [pathway] SKIPPING: city {pw_spec['city']!r} has no known map "
                  f"position (known: {', '.join(sorted(_AU_CITY_VB))})")
        else:
            pathway = {"kicker": pw_spec.get("kicker", ""),
                       "top": pw_spec.get("top", "600px"),
                       "city": (pw_spec.get("city") or "").upper(),
                       "steps": pw_spec["steps"][:3],
                       "start": round(pstart, 3), "end": round(pend, 3)}
            print(f"  [pathway] {[s['label'] for s in pathway['steps']]} -> "
                  f"{pstart:.2f}s-{pend:.2f}s (anchor match {score:.2f})")

    def _in_pathway_window(t):
        return bool(pathway) and pathway["start"] <= t < pathway["end"]

    # Full-screen hero-word slams: like "lists", each owns its window and
    # suppresses the plain 2-word caption there. Used sparingly (see
    # DEFAULT_CONTENT docstring) for the single strongest hook/payoff line.
    hero_words = []
    for spec in content.get("hero_words", []):
        # "hold" (opt-in, default 0.3s -- matches every existing reel's
        # unspecified behaviour): extra time the word stays up after
        # resolve_anchor's own padded end. Shrink this (e.g. to hard-cut
        # STRAIGHT into the next scene the instant the word is said, no
        # lingering) for a hook payoff that should feel like a snap-cut
        # rather than a held beat.
        hold = float(spec.get("hold", 0.3))
        # "pad_after" (opt-in, default 0.6s -- resolve_anchor's own default,
        # same as every existing reel): how far past the anchor phrase's true
        # end the resolved window itself extends, BEFORE "hold" is added on
        # top. Shrink this too for a snap-cut hero word (both knobs stack).
        pad_after = float(spec.get("pad_after", 0.6))
        hstart, hend, score = resolve_anchor(words, spec["anchor_phrase"], pad_after=pad_after)
        if hstart is None:
            print(f"  [hero] SKIPPING {spec.get('text')!r}: anchor_phrase "
                  f"{spec['anchor_phrase']!r} not found (best {score:.2f} < 0.8)")
            continue
        hero_words.append({"text": spec["text"], "start": round(hstart, 3),
                           "end": round(hend + hold, 3)})
        print(f"  [hero] {spec['text']!r} -> {hstart:.2f}s-{hend + hold:.2f}s (anchor match {score:.2f})")

    def _in_hero_window(t):
        return any(h["start"] <= t < h["end"] for h in hero_words)

    # Quick emphasis badges: resolve each to its spoken moment; it pops at the
    # phrase and lingers a beat past it. Placed in the upper zone so it never
    # collides with the caption band or the speaker's face.
    BADGE_COLORS = {"navy": ("#100796", "#fff"), "cyan": ("#00B3E3", "#fff"),
                    "green": ("#31EB7C", "#0a2e17"), "gold": ("#FFC500", "#100796"),
                    "red": ("#E84B37", "#fff")}
    BADGE_POS = {"top": {"center": True}, "top-left": {"left": 48},
                 "top-right": {"right": 48}}
    badges = []
    for spec in content.get("badges", []):
        bstart, bend, score = resolve_anchor(words, spec["anchor_phrase"])
        if bstart is None:
            print(f"  [badges] SKIPPING {spec.get('text')!r}: anchor_phrase "
                  f"{spec['anchor_phrase']!r} not found (best {score:.2f} < 0.8)")
            continue
        bg, fg = BADGE_COLORS.get(spec.get("color", "navy"), BADGE_COLORS["navy"])
        pos = BADGE_POS.get(spec.get("pos", "top"), BADGE_POS["top"])
        badges.append({"text": spec["text"], "icon": spec.get("icon", "star"),
                       "bg": bg, "fg": fg, "center": pos.get("center", False),
                       "left": pos.get("left"), "right": pos.get("right"), "top": 232,
                       "effect": spec.get("effect"),
                       "start": round(bstart, 3), "end": round(bend + 0.6, 3)})
        print(f"  [badges] {spec['text']!r} -> {bstart:.2f}s (anchor match {score:.2f})")

    # DM/notification mockup: resolves the same way as badges (anchor_phrase ->
    # spoken moment), pops in, holds through the message, exits. See
    # DEFAULT_CONTENT docstring for the red/green "flag" styling contract.
    dm_bubbles = []
    for spec in content.get("dm_bubbles", []):
        dstart, dend, score = resolve_anchor(words, spec["anchor_phrase"], pad_after=1.2)
        if dstart is None:
            print(f"  [dm_bubbles] SKIPPING {spec.get('message')!r}: anchor_phrase "
                  f"{spec['anchor_phrase']!r} not found (best {score:.2f} < 0.8)")
            continue
        dm_bubbles.append({"sender": spec.get("sender", "unknown"),
                           "avatar": spec.get("avatar", "\U0001F464"),
                           "message": spec["message"], "flag": spec.get("flag", "red"),
                           "start": round(dstart, 3), "end": round(dend + 0.5, 3)})
        print(f"  [dm_bubbles] {spec['message']!r} -> {dstart:.2f}s (anchor match {score:.2f})")

    proj = os.path.join(WORK, "cap_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)

    # Landmark sweep (opt-in): a small photo+name/date chip per city sweeps
    # across the headroom band, timed to the moment the speaker actually
    # says that city's name (anchor_phrase defaults to the city name itself
    # -- override per entry if a particular reel's ASR mangles it). Photos
    # come from <reel>/assets/landmarks/<city>.jpg (see that folder's
    # CREDITS.txt for source/license -- always freely-licensed with
    # attribution, never assumed public domain); a city with no photo on
    # file falls back to the bold flat SVG glyph in _LANDMARK_SVG, and only
    # skips (loud warning) if NEITHER exists.
    ls_cities = []
    for spec in content.get("landmark_sweep", {}).get("cities", []):
        cname = spec["city"].strip().upper()
        photo_src = os.path.join(REEL, "assets", "landmarks", cname.lower() + ".jpg")
        photo_dest = None
        if os.path.isfile(photo_src):
            photo_dest = f"landmark_{len(ls_cities)}_{cname.lower()}.jpg"
            shutil.copy2(photo_src, os.path.join(proj, photo_dest))
        svg = _LANDMARK_SVG.get(cname)
        if photo_dest is None and svg is None:
            print(f"  [landmark_sweep] SKIPPING {cname!r}: no photo under "
                  f"assets/landmarks/ and no known glyph in _LANDMARK_SVG.")
            continue
        phrase = spec.get("anchor_phrase", cname)
        lstart, lend, score = resolve_anchor(words, phrase, pad_before=0.0, pad_after=0.0)
        if lstart is None:
            print(f"  [landmark_sweep] SKIPPING {cname!r}: anchor_phrase "
                  f"{phrase!r} not found (best {score:.2f} < 0.8)")
            continue
        ls_cities.append({"city": cname, "date": spec.get("date", ""), "svg": svg,
                          "photo": photo_dest, "at": round(lstart, 3)})
        print(f"  [landmark_sweep] {cname!r} -> {lstart:.2f}s (anchor match {score:.2f})"
              f"{' [photo]' if photo_dest else ' [glyph]'}")

    # Multi-city roadshow card (opt-in): explicit start/end window, holds a
    # kicker + N stacked city date/time/venue blocks on screen. Like "lists",
    # it SUPPRESSES the plain 2-word caption for its window -- it's meant to
    # be read calmly over a long hold, and a caption band fighting for the
    # same vertical space (or the card having to dodge it) defeats that.
    roadshow = content.get("roadshow") or {}
    rs_cities = roadshow.get("cities") or []
    if rs_cities:
        print(f"  [roadshow] {len(rs_cities)} cities -> "
              f"{roadshow['start']:.2f}s-{roadshow['end']:.2f}s")

    def _in_roadshow_window(t):
        return bool(rs_cities) and roadshow["start"] <= t < roadshow["end"]

    # Urgency chip (opt-in): shares the roadshow card's window verbatim, sits
    # just above its kicker. Static build-time text only (see DEFAULT_CONTENT).
    urgency_chip = content.get("urgency_chip") or {}

    # Flying-plane multi-city map (opt-in): explicit start/end, same
    # caption-suppression principle as "roadshow". Positions are resolved
    # here (by city name, from _AU_CITY_VB) so content.json only ever names
    # cities, never coordinates.
    flight_map = content.get("flight_map") or {}
    fm_cities = []
    for c in flight_map.get("cities") or []:
        pos = _AU_CITY_VB.get(c["city"].strip().upper())
        if pos is None:
            print(f"  [flight_map] SKIPPING {c['city']!r}: no known map position "
                  f"for this city -- add it to _AU_CITY_VB.")
            continue
        fm_cities.append({"city": c["city"], "date": c.get("date", ""), "pos": list(pos)})
    if fm_cities:
        print(f"  [flight_map] {len(fm_cities)} cities -> "
              f"{flight_map['start']:.2f}s-{flight_map['end']:.2f}s")

    def _in_flight_map_window(t):
        return bool(fm_cities) and flight_map["start"] <= t < flight_map["end"]

    # Tiny hook banner (opt-in): explicit start/end, own tiny window at the
    # very top of the video before the viewer decides to keep scrolling.
    hook_banner = content.get("hook_banner") or {}

    # Save/share prompt (opt-in): explicit start/end, a closing engagement
    # beat layered into an existing long dwell window (e.g. late in roadshow).
    save_prompt = content.get("save_prompt") or {}

    mara = content["mara"]
    if mara["mode"] == "image":
        crop_mara_badge(proj, mara["src"])
        badge_class, badge_inner = "has-image", '<img src="mara_badge.png" alt="MARA registration"/>'
    elif mara["mode"] == "none":
        # Presenter isn't a registered migration agent (e.g. an education
        # counsellor/team lead) -- no MARN to show, so drop the badge tile
        # entirely rather than render a MARA sticker with a blank number.
        # The info-panel (name/role) naturally fills the full card width.
        badge_class, badge_inner = "hidden", ""
    else:   # "styled": recreate the OMARA sticker (dot-map + reg-number strip)
        badge_class = ""
        badge_inner = (f'<div class="dotmap">{_dotmap_html()}</div>'
                      f'<div class="hdr">MIGRATION AGENTS<br>REGISTRATION NUMBER</div>'
                      f'<div class="numstrip">{mara["marn"]}</div>'
                      f'<div class="url">www.mara.gov.au</div>')

    # Document highlights: each spec names an anchor_phrase (words as spoken),
    # never a timecode -- resolve_anchor() locates it in the transcript
    # (exact/fuzzy >=0.8) or the spot is dropped with a loud warning, NEVER a
    # guessed window (same principle as B-roll anchor-phrase placement).
    #
    # A spec can carry either "image" (one document) or "images" (a LIST) --
    # the latter renders as one fan-of-cards group sharing a single resolved
    # window (several documents genuinely tied to the same spoken moment,
    # e.g. one family's several grant letters), staggered in one at a time
    # rather than colliding at the same on-screen slot.
    docs = []
    for spec in content["documents"]:
        # "pad_after" (opt-in, default 0.6s -- resolve_anchor's own default,
        # unchanged for every existing reel): how long the window holds past
        # the anchor phrase's true end. A dense promotional graphic (lots of
        # text to actually read) needs much more than the default hold a
        # quick redacted-letter highlight needs.
        pad_after = float(spec.get("pad_after", 0.6))
        # "pad_before" (opt-in, default 0.15s -- resolve_anchor's own
        # default): when this document also suppresses the plain caption
        # (see "suppress_captions"), the caption's own 2-word chunking can
        # start a hair before the anchor phrase's first word (e.g. a leading
        # "a"/"the" grouped into the same chunk) -- widen this so that lead-
        # in chunk's START also falls inside the suppression window, instead
        # of rendering right up until the window opens.
        pad_before = float(spec.get("pad_before", 0.15))
        start, end, score = resolve_anchor(words, spec["anchor_phrase"],
                                            pad_before=pad_before, pad_after=pad_after)
        if start is None:
            print(f"  [documents] SKIPPING {spec.get('image') or spec.get('images')!r}: "
                  f"anchor_phrase {spec['anchor_phrase']!r} not found (best match "
                  f"{score:.2f} < 0.8) -- needs a manual window in content.json instead.")
            continue
        if spec.get("images"):
            group = []
            for fname in spec["images"]:
                src = os.path.join(REEL, "documents", fname)
                if not os.path.isfile(src):
                    print(f"  [documents] SKIPPING '{fname}' in group: not found under "
                          f"{os.path.join(REEL, 'documents')} -- run tools/letter-redactor "
                          f"first and drop the REDACTED output there, never the raw original.")
                    continue
                dest_name = f"doc_{len(docs)}_{len(group)}_{os.path.basename(fname)}"
                shutil.copy2(src, os.path.join(proj, dest_name))
                group.append({"img": dest_name})
            if not group:
                continue
            group[-1]["label"] = spec.get("label", "")   # front-most card carries the caption
            docs.append({"group": group, "start": start, "end": end})
            print(f"  [documents] fan-group of {len(group)} -> {start:.2f}s-{end:.2f}s "
                  f"(anchor match {score:.2f})")
            continue
        src = os.path.join(REEL, "documents", spec["image"])
        if not os.path.isfile(src):
            print(f"  [documents] SKIPPING '{spec['image']}': not found under "
                  f"{os.path.join(REEL, 'documents')} -- run tools/letter-redactor "
                  f"first and drop the REDACTED output there, never the raw original.")
            continue
        dest_name = f"doc_{len(docs)}_{os.path.basename(spec['image'])}"
        shutil.copy2(src, os.path.join(proj, dest_name))
        # "poster" (opt-in, default False): a landscape promotional graphic
        # (event flyer, banner) rather than a portrait redacted letter -- a
        # wider card with no "official stamp" seal (a stamp on a marketing
        # flyer doesn't mean anything; it's meaningful only on a document
        # being authenticated). "width" overrides the card width (default
        # 640, same as every existing reel's letter cards; a wide landscape
        # image needs more). "top" overrides the card's vertical anchor
        # (default 300px, same as every existing letter card -- a wide
        # poster is much taller relative to its width than a portrait
        # letter, so it needs its own top picked from where THIS footage's
        # headroom/face actually is, same principle as "roadshow"'s "top").
        # "suppress_captions" (default False, matches every existing use)
        # hides the plain 2-word caption for this document's window --
        # appropriate when the image IS the full announcement, not a quick
        # highlight alongside continued speech.
        docs.append({"img": dest_name, "label": spec.get("label", ""),
                     "start": start, "end": end,
                     "poster": bool(spec.get("poster", False)),
                     "width": int(spec.get("width", 640)),
                     "top": spec.get("top", "300px"),
                     "suppress_captions": bool(spec.get("suppress_captions", False))})
        print(f"  [documents] '{spec['image']}' -> {start:.2f}s-{end:.2f}s "
              f"(anchor match {score:.2f})")

    def _in_doc_suppress_window(t):
        return any(d.get("suppress_captions") and d["start"] <= t < d["end"] for d in docs)

    # A CTA subheading sits ABOVE the pill, pushing the card up into the
    # plain caption band's usual vertical range -- the two-word caption's
    # opaque box would otherwise render on top of (and hide) the subheading
    # text. Only suppress when a subheading is actually present; the
    # text-only pill (no subheading) sits low enough to never collide.
    def _in_cta_sub_window(t):
        _cta = content.get("cta") or {}
        return bool(_cta.get("subheading")) and _cta.get("start", 0) <= t < _cta.get("end", 0)

    cards = []
    for k, g in enumerate(chunks):
        start = g[0]["start"]
        end = chunks[k + 1][0]["start"] if k + 1 < len(chunks) else g[-1]["end"] + 0.4
        if (_in_list_window(start) or _in_roadshow_window(start) or _in_hero_window(start)
                or _in_doc_suppress_window(start) or _in_flight_map_window(start)
                or _in_pathway_window(start) or _in_cta_sub_window(start)):
            continue   # the checklist/roadshow/hero-slam/poster-document/flight-map/pathway/cta-sub overlay owns this window
        spans = []
        for w in g:
            is_gold = norm(w["text"]).upper() in gold
            spans.append({"text": w["text"].strip().upper(), "gold": is_gold})
        cards.append({"start": round(start, 3), "end": round(max(start + 0.2, end), 3),
                      "words": spans})

    dur = float(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nokey=1", base], capture_output=True, text=True).stdout.strip())

    # Light decorative layer (opt-in). Orbs + handle live behind the captions
    # and animate on the SAME paused timeline (tl) so they survive frame-seek.
    decor = content.get("decor") or {}
    decor_dom, decor_js = "", ""
    if decor.get("accents") or decor.get("handle") or decor.get("sparkles"):
        orbs = ("".join(f'<span class="orb o{i}"></span>' for i in range(1, 6))
                if decor.get("accents") else "")
        sparks = ("".join(f'<span class="spk s{i}{"" if i % 2 else " white"}"></span>'
                           for i in range(1, 6))
                  + '<span class="ring r1"></span><span class="ring r2"></span>'
                  if decor.get("sparkles") else "")
        handle = (f'<div id="handle">{decor["handle"]}</div>'
                  if decor.get("handle") else "")
        decor_dom = f'<div id="decor">{orbs}{sparks}{handle}</div>'
        parts = []
        if decor.get("accents"):
            # each orb: fade to a low opacity, then a slow full-length vertical
            # drift (varied px + sign) so the cluster breathes without syncing.
            parts.append(
                "  var DDUR=__DDUR__;\n"
                "  [['o1',0.20,-46],['o2',0.17,40],['o3',0.16,34],"
                "['o4',0.18,-30],['o5',0.15,26]].forEach(function(c,i){\n"
                "    var el=document.querySelector('#decor .'+c[0]); if(!el) return;\n"
                "    tl.to(el,{opacity:c[1],duration:1.3,ease:'sine.out'}, 0.3+i*0.15);\n"
                "    tl.to(el,{y:c[2],duration:DDUR,ease:'sine.inOut'}, 0);\n"
                "  });")
        if decor.get("sparkles"):
            # stars twinkle (finite yoyo repeats spanning the clip); rings fade
            # in then slowly rotate + drift like the orbs.
            rep = int(dur / 0.9) + 2
            parts.append(
                "  document.querySelectorAll('#decor .spk').forEach(function(el,i){\n"
                "    tl.fromTo(el,{opacity:0,scale:0.55,rotation:-20},"
                "{opacity:0.85,scale:1,rotation:0,duration:0.9,ease:'sine.inOut',"
                f"repeat:{rep},yoyo:true}}, 0.4+i*0.5);\n"
                "  });\n"
                "  [['r1',0.24,34],['r2',0.20,-28]].forEach(function(c){\n"
                "    var el=document.querySelector('#decor .'+c[0]); if(!el) return;\n"
                "    tl.to(el,{opacity:c[1],duration:1.2,ease:'sine.out'}, 0.6);\n"
                "    tl.to(el,{rotation:c[2],y:c[2],duration:__DDUR__,ease:'sine.inOut'}, 0);\n"
                "  });")
        if decor.get("handle"):
            parts.append(
                "  var hd=document.getElementById('handle');\n"
                "  if(hd){tl.to(hd,{opacity:0.9,duration:0.6,ease:'power2.out'}, 1.0);}")
        decor_js = ("\n".join(parts)).replace("__DDUR__", f"{dur:.3f}")

    nm, info, cta = content["name"], content["info"], content["cta"]
    # This "base" project renders everything EXCEPT the 5 cache-eligible
    # element types (cards, hero words, badges, lists, roadshow+urgency) --
    # those render independently (see caption_cache.py) and get composited
    # back on at their own resolved timestamps in build(). _CAP_BLOCK's JS
    # for each of those is already empty-array/empty-object safe (CARDS
    # .forEach on [] is a no-op, roadshow's `if (RS.cities.length)` guard
    # skips cleanly, etc.) -- so reusing the SAME unmodified template with
    # empty data for just those five is enough; no separate reduced
    # template needed, which keeps this the exact template preview_window.py
    # also relies on (see its own docstring) untouched.
    html = (_CAP_BLOCK.replace("__DUR__", f"{dur:.3f}")
            .replace("__CAP_TOP__", str(content["cap_top"]))
            .replace("__LIST_TOP__", str(content["list_top"]))
            .replace("__DECOR_DOM__", decor_dom)
            .replace("__DECOR_JS__", decor_js)
            .replace("__CARDS__", "[]")
            .replace("__DOCS__", json.dumps(docs))
            .replace("__LISTS__", "[]")
            .replace("__BADGES__", "[]")
            .replace("__HERO_WORDS__", "[]")
            .replace("__URGENCY_CHIP__", "{}")
            .replace("__HOOK_BANNER__", json.dumps(hook_banner))
            .replace("__SAVE_PROMPT__", json.dumps(save_prompt))
            .replace("__CAP_HIGHLIGHT_CLASS__", "highlight" if content.get("caption_highlight") else "")
            .replace("__ROADSHOW__", json.dumps({"kicker": "", "start": 0.0, "end": 0.0, "cities": []}))
            .replace("__ROADSHOW_TOP__", str(roadshow.get("top", "130px")))
            .replace("__ROADSHOW_SCALE__", str(roadshow.get("scale", 1.0)))
            .replace("__FLIGHT__", json.dumps({"kicker": flight_map.get("kicker", ""),
                     "start": flight_map.get("start", 0.0), "end": flight_map.get("end", 0.0),
                     "cities": fm_cities}))
            .replace("__FLIGHT_TOP__", str(flight_map.get("top", "600px")))
            .replace("__FLIGHT_SCALE__", str(flight_map.get("scale", 1.0)))
            .replace("__LANDMARK_SWEEP__", json.dumps(ls_cities))
            .replace("__SWEEP_TOP__", str(content.get("landmark_sweep", {}).get("top", "300px")))
            .replace("__DATE_START__", str(info["start"]))
            .replace("__DATE_END__", str(info["end"]))
            .replace("__INFO_KICKER__", info["kicker"])
            .replace("__INFO_LINE1__", info["line1"])
            .replace("__INFO_L1_SIZE__", str(info.get("line1_size", 80)))
            .replace("__INFO_LINE2__", info["line2"])
            .replace("__CTA_START__", str(cta["start"]))
            .replace("__CTA_END__", str(cta["end"]))
            .replace("__CTA_TEXT__", cta["text"])
            .replace("__CTA_SUB__", cta.get("subheading", ""))
            .replace("__CTA_CARD_CLASS__", "has-sub" if cta.get("subheading") else "")
            .replace("__NAME_START__", str(nm["start"]))
            .replace("__NAME_END__", str(nm["end"]))
            .replace("__NAME_TEXT__", nm["text"])
            .replace("__NAME_ROLE__", nm["role"])
            .replace("__BADGE_CLASS__", badge_class)
            .replace("__ACCENT_CSS__", _ACCENT_CSS)
            .replace("__PATHWAY_TOP__", str((content.get("pathway") or {}).get("top", "600px")))
            .replace("__BADGE_INNER__", badge_inner))
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(html)
    json.dump({"id": "pfec-captions", "name": "PFEC captions + overlays"},
              open(os.path.join(proj, "meta.json"), "w"))

    # Caption/audio drift check (qa_reel.py): persist the first and last
    # rendered caption cue's own text + start time, so QA can later re-read
    # the CURRENT assembled.transcript.json and confirm the word these cues
    # were baked against hasn't moved -- catching e.g. a re-run of
    # build_base.py (different clip trims) without a matching re-run of this
    # script, which would leave stale captions baked into the video at the
    # wrong timestamps. Only meaningful if at least one card rendered.
    if cards:
        first, last = cards[0], cards[-1]
        json.dump({"first_cue": {"text": first["words"][0]["text"], "start": first["start"]},
                   "last_cue": {"text": last["words"][0]["text"], "start": last["start"]}},
                  open(os.path.join(WORK, "caption_sync.json"), "w", encoding="utf-8"))

    # Everything needed to render the 5 cache-eligible element types
    # independently in build() (see caption_cache.py) -- cards/hero_words/
    # badges/lists were emptied out of the base HTML above specifically so
    # build() can render+composite them separately instead.
    cacheable = {
        "cards": cards, "hero_words": hero_words, "badges": badges, "lists": lists,
        "dm_bubbles": dm_bubbles, "pathway": pathway,
        "accent_word": (content.get("accent") or {}).get("word", "#FFC500"),
        "roadshow": {"kicker": roadshow.get("kicker", ""), "top": roadshow.get("top", "130px"),
                     "scale": roadshow.get("scale", 1.0), "start": roadshow.get("start", 0.0),
                     "end": roadshow.get("end", 0.0), "cities": rs_cities,
                     "urgency_text": (urgency_chip or {}).get("text", "")},
        "cap_top": content["cap_top"], "list_top": content["list_top"],
        "caption_highlight": bool(content.get("caption_highlight")),
    }
    return proj, len(cards), cacheable


### Per-element cached renders (content-hash cache -- see caption_cache.py) ###
# Each of the 5 cache-eligible types below renders as its OWN isolated
# HyperFrames composition on a LOCAL 0-based timeline (duration = its own
# end-start) instead of inside the one shared timeline `make_proj()` used to
# put everything on. The JS is the SAME animation code as before, just with
# every reference to the element's own absolute start/end swapped for 0/D
# (D = local duration) -- entrance-at-start becomes entrance-at-0, exit-
# before-end becomes exit-before-D, etc. decor is deliberately NOT here (see
# caption_cache.py's module docstring for why: its GSAP timing depends on
# the WHOLE video's duration, not just its own window, so it stays part of
# the base composition instead of being independently cacheable).

def _card_element(card, cap_top, highlight_class):
    D = round(card["end"] - card["start"], 3)
    words_html = " ".join(
        '<span class="w' + (' gold' if w["gold"] else '') + '">' + w["text"] + '</span>'
        for w in card["words"])
    body = (f'<div id="cap" class="{highlight_class}">'
            f'<div class="card" id="elCard">{words_html}</div></div>')
    js = ("""
  var el = document.getElementById("elCard");
  tl.set(el, {visibility:"visible"}, 0);
  tl.fromTo(el,
    {opacity:0, y:34, scale:0.78, rotation:-3},
    {opacity:1, y:0, scale:1, rotation:0, duration:0.22, ease:"back.out(2.2)"},
    0);
  var goldEls = el.querySelectorAll(".gold");
  if (goldEls.length) {
    tl.fromTo(goldEls, {scale:1}, {scale:1.08, duration:0.1, ease:"power2.out"}, 0.16);
    tl.to(goldEls, {scale:1, duration:0.16, ease:"power2.inOut"}, 0.26);
  }
  tl.to(el, {opacity:0, scale:0.92, duration:0.08, ease:"power1.in"}, Math.max(0.12, __D__-0.08));
  tl.set(el, {visibility:"hidden"}, __D__);
""").replace("__D__", f"{D:.3f}")
    content = {"words": card["words"], "cap_top": cap_top, "highlight_class": highlight_class}
    return content, D, body, js


def _hero_element(hero):
    D = round(hero["end"] - hero["start"], 3)
    body = f'<div id="heroHost"><div class="hero-slam" id="elHero"><span>{hero["text"]}</span></div></div>'
    js = ("""
  var el = document.getElementById("elHero");
  tl.set(el, {visibility:"visible"}, 0);
  tl.fromTo(el, {opacity:0, scale:0.5},
    {opacity:1, scale:1, duration:0.26, ease:"back.out(2.6)"}, 0);
  tl.to(el, {opacity:0, scale:1.15, duration:0.2, ease:"power2.in"}, __D__ - 0.2);
  tl.set(el, {visibility:"hidden"}, __D__);
""").replace("__D__", f"{D:.3f}")
    content = {"text": hero["text"]}
    return content, D, body, js


def _badge_element(badge, index):
    D = round(badge["end"] - badge["start"], 3)
    style = f'background:{badge["bg"]};color:{badge["fg"]};top:{badge["top"]}px;'
    if badge.get("left") is not None:
        style += f'left:{badge["left"]}px;'
    if badge.get("right") is not None:
        style += f'right:{badge["right"]}px;'
    if badge.get("center"):
        style += 'left:50%;'
    body = f'<div id="badgeHost"><div class="badge-pop" id="elBadge" style="{style}"></div></div>'
    js = ("""
  var BICONS = {
    check: '<svg viewBox="0 0 24 24" fill="none"><path d="M5 12.6l4.4 4.4L19 7" stroke="COL" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    star:  '<svg viewBox="0 0 24 24" fill="COL"><path d="M12 2l1.9 7.1L21 11l-7.1 1.9L12 20l-1.9-7.1L3 11l7.1-1.9z"/></svg>',
    brief: '<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="8" width="18" height="12" rx="2.4" fill="COL"/><path d="M8.5 8V6.4A2 2 0 0110.5 4.4h3A2 2 0 0115.5 6.4V8" stroke="COL" stroke-width="2.2"/></svg>',
    people: '<svg viewBox="0 0 24 24" fill="none"><circle cx="8" cy="8" r="3" fill="COL"/><circle cx="16" cy="8" r="3" fill="COL"/><path d="M2 20c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="COL" stroke-width="2" stroke-linecap="round"/><path d="M12 20c0-2.6 1.9-4.8 4.4-5.5" stroke="COL" stroke-width="2" stroke-linecap="round"/></svg>',
    flag: '<svg viewBox="0 0 24 24" fill="none"><path d="M6 21V3" stroke="COL" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 4h12l-3.4 4L18 12H6Z" fill="COL"/></svg>',
    medical: '<svg viewBox="0 0 24 24" fill="none"><path d="M5 3v5a3.5 3.5 0 0 0 7 0V3" stroke="COL" stroke-width="2" stroke-linecap="round"/><path d="M8.5 9.5v2.5a5.5 5.5 0 0 0 11 0v-2" stroke="COL" stroke-width="2" stroke-linecap="round"/><circle cx="19.5" cy="9.5" r="2.3" fill="COL"/><circle cx="5" cy="3" r="1.2" fill="COL"/><circle cx="12" cy="3" r="1.2" fill="COL"/></svg>'
  };
  function mulberry32(seed){
    return function(){
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  var el = document.getElementById("elBadge");
  var FG = "__FG__", BG = "__BG__", EFFECT = "__EFFECT__", BI = __BI__, TXT = __TEXT_JSON__;
  var ico = (BICONS["__ICON__"] || BICONS.star).replace(/COL/g, FG);
  el.innerHTML = '<span class="bp-ico">' + ico + '</span><span class="bp-txt">' + TXT + '</span>';
  if (el.style.left === "50%") gsap.set(el, {xPercent:-50});

  tl.set(el, {visibility:"visible"}, 0);
  if (EFFECT === "pixelate") {
    tl.fromTo(el, {opacity:0}, {opacity:1, duration:0.1}, 0);
  } else {
    tl.fromTo(el, {opacity:0, scale:0.6, y:-16},
      {opacity:1, scale:1, y:0, duration:0.34, ease:"back.out(2.4)"}, 0);
  }
  tl.to(el, {y:8, duration:0.9, ease:"sine.inOut", repeat:1, yoyo:true}, 0.4);
  tl.to(el, {opacity:0, scale:0.9, y:-14, duration:0.24, ease:"power2.in"}, __D__ - 0.24);
  tl.set(el, {visibility:"hidden"}, __D__);

  if (EFFECT === "shimmer") {
    var mask = document.createElement("div");
    mask.className = "bp-shimmer";
    el.appendChild(mask);
    gsap.set(el, {"--shimmer-pos": "-20%"});
    tl.fromTo(el, {"--shimmer-pos": "-20%"}, {"--shimmer-pos": "120%",
      duration: 0.7, ease: "power2.inOut"}, 0.34);
  } else if (EFFECT === "particles") {
    var rng = mulberry32(BI * 137 + 99);
    var N = 10;
    for (var p = 0; p < N; p++) {
      var angle = (p / N) * Math.PI * 2 + rng() * 0.6;
      var dist = 46 + rng() * 40;
      var sz = 4 + rng() * 5;
      var dx = Math.cos(angle) * dist, dy = -Math.sin(angle) * dist;
      var dot = document.createElement("div");
      dot.className = "bp-particle";
      dot.style.width = sz.toFixed(1) + "px"; dot.style.height = sz.toFixed(1) + "px";
      dot.style.background = (p % 2 === 0) ? FG : "#fff";
      el.appendChild(dot);
      tl.set(dot, {x:0, y:0, opacity:0}, 0);
      tl.to(dot, {x:dx, y:dy, opacity:1, duration:0.16, ease:"power3.out"}, 0.30 + p*0.012);
      tl.to(dot, {opacity:0, duration:0.35, ease:"power1.in"}, 0.46 + p*0.012);
    }
  } else if (EFFECT === "pixelate") {
    var cols = 8, rows2 = 3;
    var overlay = document.createElement("div");
    overlay.className = "bp-pixel-overlay";
    overlay.style.gridTemplateColumns = "repeat(" + cols + ",1fr)";
    overlay.style.gridTemplateRows = "repeat(" + rows2 + ",1fr)";
    var cells = [];
    for (var c = 0; c < cols * rows2; c++) {
      var cell = document.createElement("div");
      cell.className = "bp-cell";
      cell.style.background = BG;
      overlay.appendChild(cell);
      cells.push(cell);
    }
    el.appendChild(overlay);
    tl.set(cells, {scale:1}, 0);
    tl.to(cells, {scale:0, duration:0.36, stagger:{amount:0.3, from:"center"}, ease:"power2.in"}, 0.06);
    tl.set(cells, {display:"none"}, 0.42);
  }
""").replace("__FG__", badge["fg"]).replace("__BG__", badge["bg"]) \
    .replace("__EFFECT__", badge.get("effect") or "") \
    .replace("__BI__", str(index)).replace("__ICON__", badge.get("icon", "star")) \
    .replace("__TEXT_JSON__", json.dumps(badge["text"])).replace("__D__", f"{D:.3f}")
    content = {"text": badge["text"], "icon": badge.get("icon", "star"), "bg": badge["bg"],
               "fg": badge["fg"], "center": badge.get("center", False), "left": badge.get("left"),
               "right": badge.get("right"), "top": badge["top"], "effect": badge.get("effect"),
               "index": index}
    return content, D, body, js


# DM/notification mockup colours (content.json "dm_bubbles", see DEFAULT_CONTENT
# docstring): "red" = unsolicited/scammy DM (danger-red glow, shady wobble on
# entrance, a flag stamp slaps onto the corner); "green" = legitimate message
# (calm brand-teal glow, no wobble, no stamp -- the absence of an alarm IS the
# point).
_DM_FLAG_STYLE = {
    "red": {"accent": "#E84B37", "glow": "rgba(232,75,55,.55)", "stamp": "\U0001F6A9"},
    "green": {"accent": "#00B3E3", "glow": "rgba(0,179,227,.45)", "stamp": ""},
}


def _dm_bubble_element(dm):
    D = round(dm["end"] - dm["start"], 3)
    style = _DM_FLAG_STYLE.get(dm["flag"], _DM_FLAG_STYLE["red"])
    stamp_html = (f'<div class="dm-stamp" id="elDmStamp">{style["stamp"]}</div>'
                  if style["stamp"] else "")
    body = (f'<div id="dmHost"><div class="dm-card" id="elDm" '
            f'style="--dm-accent:{style["accent"]};--dm-glow:{style["glow"]}">'
            f'<div class="dm-avatar">{dm["avatar"]}</div>'
            f'<div class="dm-meta"><div class="dm-sender">{dm["sender"]}</div>'
            f'<div class="dm-msg">{dm["message"]}</div></div>'
            f'{stamp_html}</div></div>')
    js = ("""
  var el = document.getElementById("elDm");
  var stamp = document.getElementById("elDmStamp");
  var WOBBLE = __WOBBLE__;

  tl.set(el, {visibility:"visible"}, 0);
  tl.fromTo(el, {opacity:0, scale:0.7, y:-46},
    {opacity:1, scale:1, y:0, duration:0.32, ease:"back.out(2.3)"}, 0);
  if (WOBBLE) {
    tl.to(el, {rotation:-2.4, duration:0.09, ease:"sine.inOut"}, 0.32);
    tl.to(el, {rotation:2.4, duration:0.13, ease:"sine.inOut"}, 0.41);
    tl.to(el, {rotation:-1.4, duration:0.13, ease:"sine.inOut"}, 0.54);
    tl.to(el, {rotation:0, duration:0.13, ease:"sine.inOut"}, 0.67);
  }
  if (stamp) {
    tl.fromTo(stamp, {opacity:0, scale:0, rotation:-24},
      {opacity:1, scale:1, rotation:-10, duration:0.26, ease:"back.out(3)"}, 0.5);
  }
  tl.to(el, {y:6, duration:1.0, ease:"sine.inOut", repeat:1, yoyo:true}, 0.85);
  tl.to(el, {opacity:0, scale:0.88, y:-30, duration:0.26, ease:"power2.in"}, __D__ - 0.26);
  tl.set(el, {visibility:"hidden"}, __D__);
""").replace("__WOBBLE__", "true" if dm["flag"] == "red" else "false").replace("__D__", f"{D:.3f}")
    content = {"sender": dm["sender"], "avatar": dm["avatar"], "message": dm["message"],
               "flag": dm["flag"]}
    return content, D, body, js


def _list_element(lst, list_top):
    D = round(lst["end"] - lst["start"], 3)
    inner = f'<div class="lc-title">{lst["title"]}</div>' if lst["title"] else ""
    chk = ('<svg viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.4 4.4L19 7" '
           'stroke="#0a2e17" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    for it in lst["items"]:
        inner += f'<div class="lc-row"><span class="lc-check">{chk}</span><span class="lc-label">{it}</span></div>'
    body = f'<div id="listHost"><div class="list-card" id="elList">{inner}</div></div>'
    times_rel = [round(t - lst["start"], 3) for t in lst["times"]]
    js = ("""
  var card = document.getElementById("elList");
  tl.set(card, {visibility:"visible"}, 0);
  tl.fromTo(card, {opacity:0, y:28, scale:0.92},
    {opacity:1, y:0, scale:1, duration:0.34, ease:"back.out(1.7)"}, 0);
  var rows = card.querySelectorAll(".lc-row");
  var TIMES = __TIMES__;
  TIMES.forEach(function(t, i){
    var row = rows[i]; if (!row) return;
    var chk = row.querySelector(".lc-check");
    tl.fromTo(row, {opacity:0, x:-28}, {opacity:1, x:0, duration:0.26, ease:"power2.out"}, t);
    tl.fromTo(chk, {scale:0, rotation:-30}, {scale:1, rotation:0, duration:0.3, ease:"back.out(2.6)"}, t + 0.04);
  });
  tl.to(card, {opacity:0, y:-18, scale:0.96, duration:0.26, ease:"power2.in"}, __D__ - 0.26);
  tl.set(card, {visibility:"hidden"}, __D__);
""").replace("__TIMES__", json.dumps(times_rel)).replace("__D__", f"{D:.3f}")
    content = {"title": lst["title"], "items": lst["items"], "times_rel": times_rel, "list_top": list_top}
    return content, D, body, js


# Step icons for the pathway chain. Same flat-vector, no-licence approach as
# ICONS above; "COL" is substituted with the accent colour at build time.
_PW_ICONS = {
    "cap": ('<svg viewBox="0 0 24 24" fill="none"><path d="M12 3 22 8l-10 5L2 8l10-5Z" fill="COL"/>'
            '<path d="M6 11.2V16c0 1.7 2.7 3 6 3s6-1.3 6-3v-4.8" stroke="COL" stroke-width="2.1" '
            'stroke-linecap="round"/></svg>'),
    "brief": ('<svg viewBox="0 0 24 24" fill="none"><rect x="2.5" y="7.5" width="19" height="12.5" rx="2.4" fill="COL"/>'
              '<path d="M8.5 7.5V6A2 2 0 0110.5 4h3A2 2 0 0115.5 6v1.5" stroke="COL" stroke-width="2.2" '
              'stroke-linecap="round"/></svg>'),
    "flag": ('<svg viewBox="0 0 24 24" fill="none"><path d="M5.5 21V3" stroke="COL" stroke-width="2.4" '
             'stroke-linecap="round"/><path d="M5.5 4h13l-3.6 4.2L18.5 12.6h-13Z" fill="COL"/></svg>'),
    "people": ('<svg viewBox="0 0 24 24" fill="none"><circle cx="8" cy="8" r="3" fill="COL"/>'
               '<circle cx="16" cy="8" r="3" fill="COL"/><path d="M2 20c0-3.3 2.7-6 6-6s6 2.7 6 6" '
               'stroke="COL" stroke-width="2" stroke-linecap="round"/>'
               '<path d="M12 20c0-2.6 1.9-4.8 4.4-5.5" stroke="COL" stroke-width="2" stroke-linecap="round"/></svg>'),
    "star": '<svg viewBox="0 0 24 24" fill="COL"><path d="M12 2l1.9 7.1L21 11l-7.1 1.9L12 20l-1.9-7.1L3 11l7.1-1.9z"/></svg>',
    "check": ('<svg viewBox="0 0 24 24" fill="none"><path d="M5 12.6l4.4 4.4L19 7" stroke="COL" '
              'stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'),
    "medical": ('<svg viewBox="0 0 24 24" fill="none"><path d="M5 3v5a3.5 3.5 0 0 0 7 0V3" stroke="COL" '
                'stroke-width="2" stroke-linecap="round"/><path d="M8.5 9.5v2.5a5.5 5.5 0 0 0 11 0v-2" '
                'stroke="COL" stroke-width="2" stroke-linecap="round"/>'
                '<circle cx="19.5" cy="9.5" r="2.3" fill="COL"/>'
                '<circle cx="5" cy="3" r="1.2" fill="COL"/><circle cx="12" cy="3" r="1.2" fill="COL"/></svg>'),
}

# Curly (wavy, hand-drawn feel) connector between pathway steps, replacing a
# plain straight bar + triangular arrowhead. "curl-path" is a 1.5-hump wave
# drawn in with a stroke-dashoffset animation (pathLength="100" normalizes
# the dash math regardless of true SVG path length); "tip-path" is a small
# curved hook (not a triangle) that pops in once the wave finishes drawing.
_PW_ARROW_SVG = (
    '<svg viewBox="0 0 70 24" fill="none">'
    '<path class="curl-path" pathLength="100" d="M3,13 Q13,2 23,13 T43,13 T61,13" '
    'stroke="COL" stroke-width="3.4" stroke-linecap="round"/>'
    '<path class="tip-path" d="M54,6 Q65,13 54,20" '
    'stroke="COL" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>'
    '</svg>')

# The same stylized Australia silhouette build_opener.py's cold-open uses, so
# the two read as the same map. viewBox 0 0 100 86; _AU_CITY_VB is calibrated
# against exactly this path.
_AU_MAP_SVG = (
    '<svg viewBox="0 0 100 86">'
    '<path d="M 68 2 L 72 10 L 78 22 L 80 32 L 76 44 L 70 52 L 60 58 L 48 54 L 36 56'
    ' L 20 58 L 12 50 L 8 38 L 10 24 L 16 14 L 26 8 L 34 12 L 40 6 L 48 4'
    ' L 52 14 L 58 12 L 62 2 Z" fill="rgba(255,255,255,.10)" stroke="ACC" stroke-width="1.6"/>'
    '<ellipse cx="66" cy="70" rx="5" ry="4" fill="rgba(255,255,255,.10)" stroke="ACC" stroke-width="1.4"/>'
    '</svg>')

_PW_MAP_W, _PW_MAP_H = 132, 113


def _pathway_element(pw, accent):
    """3-step visa-pathway chain with icons + animated arrows, under a stylized
    Australia map with the reel's city pinned. Steps and arrows land one after
    another so the sequence reads as a progression, not a static diagram."""
    D = round(pw["end"] - pw["start"], 3)
    kicker = (f'<div class="pw-kicker">{pw["kicker"]}</div>' if pw["kicker"] else "")

    pin = ""
    if pw["city"]:
        vx, vy = _AU_CITY_VB[pw["city"]]
        px = round(vx / 100.0 * _PW_MAP_W, 1)
        py = round(vy / 86.0 * _PW_MAP_H, 1)
        pin = (f'<div class="pw-pulse" style="left:{px}px;top:{py}px"></div>'
               f'<div class="pw-pin" style="left:{px}px;top:{py}px"></div>'
               f'<div class="pw-pinlbl" style="left:{px}px;top:{py}px">{pw["city"]}</div>')
    map_html = (f'<div class="pw-map">{_AU_MAP_SVG.replace("ACC", accent)}{pin}</div>')

    chain = ""
    for i, st in enumerate(pw["steps"]):
        if i:
            chain += (f'<div class="pw-arrow">{_PW_ARROW_SVG.replace("COL", accent)}</div>')
        ico = _PW_ICONS.get(st.get("icon", "check"), _PW_ICONS["check"]).replace("COL", accent)
        final = " final" if i == len(pw["steps"]) - 1 else ""
        sub = f'<div class="pw-sub">{st["sub"]}</div>' if st.get("sub") else ""
        chain += (f'<div class="pw-step{final}"><span class="pw-ico">{ico}</span>'
                  f'<div class="pw-lbl">{st["label"]}</div>{sub}</div>')

    scoped = f'<style>#pathwayHost{{--pw-acc:{accent}}}</style>'
    body = (f'{scoped}<div id="pathwayHost"><div class="pw-card" id="elPathway">'
            f'{kicker}{map_html}<div class="pw-chain">{chain}</div></div></div>')

    js = ("""
  var card = document.getElementById("elPathway");
  tl.set(card, {visibility:"visible"}, 0);
  tl.fromTo(card, {opacity:0, y:30, scale:0.93},
    {opacity:1, y:0, scale:1, duration:0.34, ease:"back.out(1.7)"}, 0);

  var svg = card.querySelector(".pw-map svg");
  if (svg) tl.fromTo(svg, {opacity:0}, {opacity:1, duration:0.30, ease:"power2.out"}, 0.14);
  var pin = card.querySelector(".pw-pin");
  var pulse = card.querySelector(".pw-pulse");
  var pinlbl = card.querySelector(".pw-pinlbl");
  if (pin) {
    tl.fromTo(pin, {opacity:0, scale:0}, {opacity:1, scale:1, duration:0.26, ease:"back.out(3)"}, 0.44);
    tl.fromTo(pulse, {opacity:0.85, scale:1}, {opacity:0, scale:3.4, duration:0.9, ease:"power2.out"}, 0.50);
    tl.fromTo(pinlbl, {opacity:0, y:6}, {opacity:1, y:0, duration:0.22, ease:"power2.out"}, 0.56);
  }

  // steps land in order, each arrow drawing into the next step
  var steps = card.querySelectorAll(".pw-step");
  var arrows = card.querySelectorAll(".pw-arrow");
  var t0 = 0.72, gap = 0.55;
  steps.forEach(function(s, i){
    var at = t0 + i * gap;
    tl.fromTo(s, {opacity:0, y:22, scale:0.86},
      {opacity:1, y:0, scale:1, duration:0.30, ease:"back.out(2.4)"}, at);
    var a = arrows[i];
    if (a) {
      var curl = a.querySelector(".curl-path"), tip = a.querySelector(".tip-path");
      if (curl) tl.fromTo(curl, {strokeDashoffset:100},
        {strokeDashoffset:0, duration:0.30, ease:"power2.out"}, at + 0.24);
      if (tip) tl.fromTo(tip, {opacity:0, scale:0.4},
        {opacity:1, scale:1, duration:0.18, ease:"back.out(2.6)"}, at + 0.54);
    }
  });
  // final step gets one confirming pop once the chain is complete
  var last = steps[steps.length - 1];
  if (last) tl.to(last, {scale:1.06, duration:0.16, yoyo:true, repeat:1,
                         ease:"sine.inOut"}, t0 + steps.length * gap);

  tl.to(card, {opacity:0, y:-20, scale:0.96, duration:0.28, ease:"power2.in"}, __D__ - 0.28);
  tl.set(card, {visibility:"hidden"}, __D__);
""").replace("__D__", f"{D:.3f}")

    content = {"kicker": pw["kicker"], "city": pw["city"], "steps": pw["steps"],
               "top": pw["top"], "accent": accent}
    return content, D, body, js


def _roadshow_element(rs):
    D = round(rs["end"] - rs["start"], 3)
    body = '<div id="roadshowCard"></div><div id="urgencyChip"><span></span></div>'
    js = ("""
  var rsHost = document.getElementById("roadshowCard");
  var rsKicker = document.createElement("div");
  rsKicker.className = "rs-kicker";
  rsKicker.textContent = __KICKER__;
  rsHost.appendChild(rsKicker);
  var rsCities = document.createElement("div");
  rsCities.className = "rs-cities";
  rsHost.appendChild(rsCities);

  tl.set(rsHost, {visibility:"visible"}, 0);
  tl.fromTo(rsHost, {opacity:0}, {opacity:1, duration:0.01}, 0);
  tl.fromTo(rsKicker, {opacity:0, scale:0.85, y:-18},
    {opacity:1, scale:1, y:0, duration:0.3, ease:"back.out(2.2)"}, 0);

  var CITIES = __CITIES__;
  CITIES.forEach(function(c, i){
    var el = document.createElement("div");
    el.className = "rs-city";
    el.innerHTML =
      '<div class="rs-city-name">' + c.city + '</div><br>' +
      '<div class="rs-row"><span class="rs-date">' + c.date + '</span>' +
      // omit the time pill entirely when no time is known -- an empty span
      // still renders as a small stray cyan blob next to the date
      (c.time ? '<span class="rs-time">' + c.time + '</span>' : '') + '</div>' +
      '<div class="rs-venue">' + c.venue + '</div>';
    rsCities.appendChild(el);

    var enter = 0.32 + i * 0.4;
    tl.fromTo(el, {opacity:0, y:46, scale:0.92},
      {opacity:1, y:0, scale:1, duration:0.4, ease:"back.out(1.8)"}, enter);
    var dateEl = el.querySelector(".rs-date");
    tl.fromTo(dateEl, {scale:1.3}, {scale:1, duration:0.24, ease:"back.out(3)"}, enter + 0.08);
  });

  tl.to(rsHost, {opacity:0, y:-16, duration:0.25, ease:"power2.in"}, __D__ - 0.25);
  tl.set(rsHost, {visibility:"hidden"}, __D__);

  var UC_TEXT = __UC_TEXT__;
  if (UC_TEXT) {
    var ucEl = document.getElementById("urgencyChip");
    ucEl.querySelector("span").textContent = UC_TEXT;
    tl.set(ucEl, {visibility:"visible"}, 0);
    tl.fromTo(ucEl, {opacity:0, scale:0.8, y:-10},
      {opacity:1, scale:1, y:0, duration:0.26, ease:"back.out(2.4)"}, 0);
    tl.to(ucEl, {opacity:0, y:-10, duration:0.2, ease:"power2.in"}, __D__ - 0.2);
    tl.set(ucEl, {visibility:"hidden"}, __D__);
  }
""").replace("__KICKER__", json.dumps(rs["kicker"])).replace("__CITIES__", json.dumps(rs["cities"])) \
    .replace("__UC_TEXT__", json.dumps(rs.get("urgency_text", ""))).replace("__D__", f"{D:.3f}")
    content = {"kicker": rs["kicker"], "cities": rs["cities"], "top": rs["top"], "scale": rs["scale"],
               "urgency_text": rs.get("urgency_text", "")}
    return content, D, body, js


def _shared_css():
    """The exact CSS ruleset _CAP_BLOCK uses, extracted verbatim (not
    retyped) so every per-element render styles identically to the combined
    composition -- unused selectors for elements not present in a given
    element's own render are harmless."""
    return _CAP_BLOCK.split("<style>", 1)[1].split("</style>", 1)[0]


def _render_cacheable(element_type, content, duration, body_html, js_body, cache_dir, no_cache):
    css = (_shared_css()
           .replace("__CAP_TOP__", str(content.get("cap_top", "62%")))
           .replace("__LIST_TOP__", str(content.get("list_top", "44%")))
           .replace("__ROADSHOW_TOP__", str(content.get("top", "130px")))
           .replace("__ROADSHOW_SCALE__", str(content.get("scale", 1.0)))
           .replace("__ACCENT_CSS__", _ACCENT_CSS)
           .replace("__PATHWAY_TOP__", str(content.get("top", "600px")))
           .replace("__INFO_L1_SIZE__", "80"))
    path, hit = caption_cache.render_element(
        element_type, content, duration, css, body_html, js_body,
        WORK, cache_dir, hyperframes_cli(), HF_QUALITY, HF_FPS, no_cache=no_cache)
    return path, hit


def build(no_cache=False, clear_cache=False):
    cache_dir = caption_cache.cache_root(REEL)
    if clear_cache:
        caption_cache.clear_cache(REEL)

    base = os.path.join(WORK, "base_broll.mp4")
    proj, n_cards, cacheable = make_proj(base)

    overlay = os.path.join(WORK, "captions_overlay.webm")
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    print(f"rendering {n_cards} caption cards + overlay cards (transparent)...")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(overlay),
                    "-f", str(HF_FPS), "--format", "webm", "-q", HF_QUALITY, "--quiet"],
                   cwd=proj, check=True, env=env)

    # Cache-eligible elements: each renders (or reuses a cache hit for) its
    # own short clip, then gets positioned onto the footage at its resolved
    # absolute timestamp via -itsoffset -- same technique insert_broll.py's
    # overlay_wipes() already uses for the grid-wipe transition.
    layers = []  # (webm_path, abs_start, abs_end)
    hits = misses = 0

    for card in cacheable["cards"]:
        content, D, body, js = _card_element(
            card, cacheable["cap_top"], "highlight" if cacheable["caption_highlight"] else "")
        path, hit = _render_cacheable("card", content, D, body, js, cache_dir, no_cache)
        layers.append((path, card["start"], card["start"] + D))
        hits += hit; misses += not hit

    for hero in cacheable["hero_words"]:
        content, D, body, js = _hero_element(hero)
        path, hit = _render_cacheable("hero", content, D, body, js, cache_dir, no_cache)
        layers.append((path, hero["start"], hero["start"] + D))
        hits += hit; misses += not hit

    for i, badge in enumerate(cacheable["badges"]):
        content, D, body, js = _badge_element(badge, i)
        path, hit = _render_cacheable("badge", content, D, body, js, cache_dir, no_cache)
        layers.append((path, badge["start"], badge["start"] + D))
        hits += hit; misses += not hit

    for lst in cacheable["lists"]:
        content, D, body, js = _list_element(lst, cacheable["list_top"])
        path, hit = _render_cacheable("list", content, D, body, js, cache_dir, no_cache)
        layers.append((path, lst["start"], lst["start"] + D))
        hits += hit; misses += not hit

    for dm in cacheable["dm_bubbles"]:
        content, D, body, js = _dm_bubble_element(dm)
        path, hit = _render_cacheable("dm_bubble", content, D, body, js, cache_dir, no_cache)
        layers.append((path, dm["start"], dm["start"] + D))
        hits += hit; misses += not hit

    pw = cacheable.get("pathway")
    if pw:
        content, D, body, js = _pathway_element(pw, cacheable.get("accent_word", "#FFC500"))
        path, hit = _render_cacheable("pathway", content, D, body, js, cache_dir, no_cache)
        layers.append((path, pw["start"], pw["start"] + D))
        hits += hit; misses += not hit

    rs = cacheable["roadshow"]
    if rs["cities"]:
        content, D, body, js = _roadshow_element(rs)
        path, hit = _render_cacheable("roadshow", content, D, body, js, cache_dir, no_cache)
        layers.append((path, rs["start"], rs["start"] + D))
        hits += hit; misses += not hit

    if hits or misses:
        print(f"  [cache] {hits} hit(s), {misses} miss(es) "
              f"({len(layers)} cache-eligible element(s) total)")

    # CRITICAL: force libvpx-vp9 decode -- ffmpeg's default vp9 decoder drops the
    # alpha plane (reports yuv420p) and would paint opaque black over the footage.
    # Composite: base footage -> base composition overlay -> each cached
    # element at its own -itsoffset (mirrors insert_broll.py's overlay_wipes()).
    out = os.path.join(WORK, "captioned.mp4")
    # Composite in batches of BATCH_SIZE layers per ffmpeg invocation, each
    # pass's output becoming the next pass's base -- rather than one giant
    # command with every layer's "-itsoffset ... -i <path>" plus the whole
    # filter_complex chain. A single-command build works fine for the usual
    # 30-45s reel's few dozen elements, but a much longer reel (this one:
    # 163s, 265 cache-eligible elements) pushes the ffmpeg argv well past
    # Windows' CreateProcess command-line ceiling -- hit for the first time
    # on the 2026-07-31 Shahid Dhaka/Chattogram reel (FileNotFoundError
    # [WinError 206] "filename or extension is too long"). Batching produces
    # an identical final composite; it only bounds each individual command's
    # length so this scales to any reel length. crf=18 on every intermediate
    # pass costs a little generational quality vs. one pass, but crf=18 is
    # visually near-transparent and the pipeline already re-encodes several
    # times downstream (wipe overlay, broll splice, final composite), so a
    # few extra generations on an unusually long reel is an acceptable
    # trade-off against a build that can't complete at all.
    BATCH_SIZE = 40
    cur_base = base
    cur_has_overlay = True
    n_batches = max(1, -(-len(layers) // BATCH_SIZE)) if layers else 1
    for batch_num, start_i in enumerate(range(0, max(len(layers), 1), BATCH_SIZE), start=1):
        chunk = layers[start_i:start_i + BATCH_SIZE]
        is_last = start_i + BATCH_SIZE >= len(layers)
        pass_out = out if is_last else os.path.join(WORK, f"captioned_pass{batch_num}.mp4")

        cmd = ["-i", cur_base]
        if cur_has_overlay:
            cmd += ["-c:v", "libvpx-vp9", "-i", overlay]
            filt = ["[0:v][1:v]overlay=0:0:format=auto[v0]"]
            prev, layer_start_idx = "v0", 2
        else:
            filt, prev, layer_start_idx = [], "0:v", 1
        for path, start, _end in chunk:
            cmd += ["-itsoffset", f"{max(0.0, start):.3f}", "-c:v", "libvpx-vp9", "-i", path]

        for i, (_path, start, end) in enumerate(chunk):
            idx = layer_start_idx + i
            nxt = f"v{i + 1}"
            filt.append(f"[{idx}:v]format=yuva420p[w{idx}]")
            filt.append(f"[{prev}][w{idx}]overlay=0:0:format=auto:"
                        f"enable='between(t,{start:.3f},{end:.3f})'[{nxt}]")
            prev = nxt
        filt.append(f"[{prev}]format=yuv420p[vout]")

        cmd += ["-filter_complex", ";".join(filt), "-map", "[vout]", "-map", "0:a",
                "-c:v", "libx264", "-preset", X264_PRESET, "-crf", "18", *COLOR_TAGS, "-c:a", "copy",
                "-video_track_timescale", "90000", pass_out]
        run(cmd)
        print(f"  [captions] batch {batch_num}/{n_batches}: {len(chunk)} layer(s) "
              f"-> {os.path.basename(pass_out)}")
        cur_base, cur_has_overlay = pass_out, False
    print("rendered:", out)


_CAP_BLOCK = """<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1080px;height:1920px;overflow:hidden;background:transparent}
  #cap{position:absolute;left:0;right:0;top:__CAP_TOP__;transform:translateY(-50%);text-align:center}
  .card{position:absolute;left:0;right:0;top:0;padding:0 70px;opacity:0;visibility:hidden}
  .w{font-family:"Poppins",sans-serif;font-weight:800;font-size:96px;line-height:1.05;color:#fff;
     letter-spacing:.01em;text-shadow:0 6px 22px rgba(0,0,0,.75),0 2px 4px rgba(0,0,0,.95);
     display:inline-block;margin:0 26px}
  .w.gold{color:#FFC500}
  /* Caption background-highlight mode (opt-in via content.json
     "caption_highlight" -- see DEFAULT_CONTENT docstring; adapted from the
     catalog's caption-highlight component in brand colour instead of TikTok
     red). Each word gets its own solid rounded box instead of plain
     drop-shadowed text over the raw footage -- reads as native short-form
     platform captions, which is the point: audience-recognizable format. */
  #cap.highlight .w{background:#E84B37;padding:4px 18px;border-radius:14px;
     text-shadow:none;box-shadow:0 8px 20px rgba(0,0,0,.35)}
  #cap.highlight .w.gold{background:#100796;color:#FFC500}

  /* Full-screen hero-word slam (content.json "hero_words") -- one giant
     centered word/phrase for the single strongest hook/payoff line in a
     reel; see DEFAULT_CONTENT docstring for why this must stay rare. */
  #heroHost{position:absolute;inset:0;pointer-events:none}
  .hero-slam{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);
     text-align:center;opacity:0;visibility:hidden;padding:0 40px}
  .hero-slam span{font-family:"Poppins",sans-serif;font-weight:800;font-size:150px;
     line-height:0.98;color:#FFC500;letter-spacing:.01em;display:inline-block;
     text-shadow:0 10px 30px rgba(0,0,0,.6),0 3px 6px rgba(0,0,0,.9)}

  /* Tiny top-of-frame hook banner (content.json "hook_banner"): a small pill
     for the first ~1s, before the viewer decides whether to keep scrolling. */
  #hookBanner{position:absolute;left:0;right:0;top:235px;text-align:center;
     opacity:0;visibility:hidden}
  #hookBanner span{display:inline-block;background:rgba(16,7,150,.88);color:#fff;
     font-family:"Poppins",sans-serif;font-weight:700;font-size:27px;letter-spacing:.02em;
     padding:12px 30px;border-radius:999px;box-shadow:0 10px 26px rgba(0,0,0,.4);
     border:1px solid rgba(255,255,255,.16)}

  /* Save/share prompt (content.json "save_prompt"): a closing engagement
     beat, sits in the upper zone (freed up once the roadshow card moved
     down for face-clearance) during the tail of an existing dwell window. */
  #savePrompt{position:absolute;left:0;right:0;top:400px;text-align:center;
     opacity:0;visibility:hidden}
  #savePrompt span{display:inline-block;background:#FFC500;color:#100796;
     font-family:"Poppins",sans-serif;font-weight:800;font-size:30px;letter-spacing:.01em;
     padding:14px 32px;border-radius:999px;box-shadow:0 12px 28px rgba(0,0,0,.35)}

  /* Urgency chip (content.json "urgency_chip"): sits just above the roadshow
     kicker, shares its window verbatim. */
  #urgencyChip{position:absolute;left:0;right:0;top:660px;text-align:center;
     opacity:0;visibility:hidden}
  #urgencyChip span{display:inline-block;background:#E84B37;color:#fff;
     font-family:"Poppins",sans-serif;font-weight:800;font-size:26px;letter-spacing:.04em;
     padding:9px 26px;border-radius:999px;box-shadow:0 8px 20px rgba(0,0,0,.35)}

  /* Overlay card: seminar date kicker (top). Each element gets its own
     colour-block backdrop + a distinct entrance so the three facts (what /
     when / where) read as three punchy, separately-highlighted beats rather
     than one flat text stack. */
  #dateCard{position:absolute;left:0;right:0;top:210px;text-align:center}

  #dateCard .kickerWrap{position:relative;display:inline-block;opacity:0;visibility:hidden}
  #dateCard .kicker{position:relative;display:inline-block;background:#100796;color:#fff;
     font-family:"Poppins",sans-serif;font-weight:700;font-size:34px;letter-spacing:.06em;
     padding:14px 36px;border-radius:999px;box-shadow:0 10px 30px rgba(0,0,0,.35);overflow:hidden}
  #dateCard .kicker .shine{position:absolute;top:-40%;left:-60%;width:40%;height:180%;
     background:linear-gradient(75deg,transparent,rgba(255,255,255,.55),transparent);
     transform:translateX(-120%) skewX(-20deg)}

  #dateCard .dateWrap{position:relative;display:inline-block;margin-top:22px;opacity:0;visibility:hidden;
     transform-origin:center}
  #dateCard .dateBlock{position:absolute;inset:-6px -28px;background:#E84B37;border-radius:16px;
     transform:scaleX(0);transform-origin:center;box-shadow:0 14px 32px rgba(0,0,0,.4);z-index:0}
  #dateCard .date{position:relative;z-index:1;font-family:"Poppins",sans-serif;font-weight:900;
     font-size:__INFO_L1_SIZE__px;color:#fff;padding:6px 4px;text-shadow:0 4px 10px rgba(0,0,0,.35)}

  #dateCard .venueWrap{position:relative;display:inline-block;margin-top:16px;opacity:0;visibility:hidden}
  #dateCard .venueBlock{position:absolute;inset:-8px -22px;background:#00B3E3;border-radius:999px;
     transform:scaleX(0);transform-origin:left center;z-index:0;box-shadow:0 8px 22px rgba(0,0,0,.3)}
  #dateCard .venue{position:relative;z-index:1;font-family:"Poppins",sans-serif;font-weight:700;
     font-size:30px;color:#fff;padding:8px 6px}

  /* Multi-city roadshow card: kicker + stacked city blocks, pinned on screen
     for a long window (unlike the single-shot #dateCard). "top" is per-reel
     configurable (__ROADSHOW_TOP__) -- position it clear of the speaker's
     face for THIS footage's framing, not a fixed guess (check where their
     head actually sits across the WHOLE window, not just one frame -- a
     talking head can lean/move during a multi-second hold). "scale" is an
     opt-in uniform enlarge (__ROADSHOW_SCALE__, default 1.0) for reels that
     need the card to read bigger/bolder; transform-origin is top-center so
     scaling grows downward from the fixed "top" anchor instead of drifting
     the kicker's position. Compact sizing (vs. #dateCard) since it has to
     fit in whatever headroom/chest band is actually free, not the whole
     upper zone. */
  #roadshowCard{position:absolute;left:0;right:0;top:__ROADSHOW_TOP__;text-align:center;
     opacity:0;visibility:hidden;transform:scale(__ROADSHOW_SCALE__);transform-origin:top center}
  #roadshowCard .rs-kicker{position:relative;display:inline-block;background:#100796;
     color:#fff;font-family:"Poppins",sans-serif;font-weight:700;font-size:26px;
     letter-spacing:.05em;padding:10px 28px;border-radius:999px;
     box-shadow:0 8px 22px rgba(0,0,0,.35);opacity:0;transform:scale(.85) translateY(-18px)}
  #roadshowCard .rs-cities{margin-top:16px;display:flex;flex-direction:column;
     align-items:center;gap:14px}
  #roadshowCard .rs-city{position:relative;width:960px;border-radius:20px;
     background:linear-gradient(135deg,#100796 0%,#1c1099 60%,#2a0f8f 100%);
     padding:14px 26px 16px;box-shadow:0 14px 32px rgba(0,0,0,.45);
     border:1px solid rgba(255,255,255,.14);opacity:0;transform:translateY(36px) scale(.92)}
  #roadshowCard .rs-city-name{display:inline-block;background:#FFC500;color:#100796;
     font-family:"Poppins",sans-serif;font-weight:800;font-size:26px;letter-spacing:.05em;
     padding:4px 20px;border-radius:999px;margin-bottom:8px}
  #roadshowCard .rs-row{display:flex;align-items:center;justify-content:center;gap:14px;
     flex-wrap:wrap}
  #roadshowCard .rs-date{position:relative;display:inline-block;background:#E84B37;
     color:#fff;font-family:"Poppins",sans-serif;font-weight:900;font-size:34px;
     padding:6px 18px;border-radius:12px;box-shadow:0 6px 16px rgba(0,0,0,.3);
     transform-origin:center}
  #roadshowCard .rs-time{display:inline-block;background:#00B3E3;color:#fff;
     font-family:"Poppins",sans-serif;font-weight:700;font-size:22px;
     padding:7px 16px;border-radius:999px;box-shadow:0 5px 14px rgba(0,0,0,.25)}
  #roadshowCard .rs-venue{margin-top:8px;font-family:"Poppins",sans-serif;font-weight:700;
     font-size:21px;color:#FFE9B0;letter-spacing:.01em}

  /* Flying-plane multi-city map (content.json "flight_map"): stylized AU
     silhouette (same shape/brand colours as build_opener.py's cold-open),
     plane emoji hops city to city, each landing pinned+labelled and left on
     screen. "top" per-reel configurable, same reasoning as roadshow's. */
  #flightMap{position:absolute;left:0;right:0;top:__FLIGHT_TOP__;text-align:center;
     opacity:0;visibility:hidden;transform:scale(__FLIGHT_SCALE__);transform-origin:top center}
  #flightMap .fm-kicker{position:relative;display:inline-block;background:#100796;
     color:#fff;font-family:"Poppins",sans-serif;font-weight:700;font-size:26px;
     letter-spacing:.05em;padding:10px 28px;border-radius:999px;
     box-shadow:0 8px 22px rgba(0,0,0,.35);opacity:0;transform:scale(.85) translateY(-18px)}
  #flightMap .fm-stage{position:relative;width:740px;height:637px;margin:20px auto 0;
     opacity:0;transform-origin:center}
  #flightMap .fm-stage svg{position:absolute;left:0;top:0;width:740px;height:637px;
     filter:drop-shadow(0 10px 26px rgba(0,0,0,.4))}
  #flightMap .fm-plane{position:absolute;font-size:46px;line-height:1;
     transform:translate(-50%,-50%);filter:drop-shadow(0 4px 10px rgba(0,0,0,.45))}
  #flightMap .fm-pin{position:absolute;width:16px;height:16px;margin:-8px 0 0 -8px;
     border-radius:50%;background:#E84B37;border:3px solid #fff;opacity:0;
     box-shadow:0 4px 10px rgba(0,0,0,.4)}
  #flightMap .fm-pulse{position:absolute;width:16px;height:16px;margin:-8px 0 0 -8px;
     border-radius:50%;border:4px solid #FFC500;opacity:0}
  #flightMap .fm-label{position:absolute;transform:translate(-50%,-150%);opacity:0;
     background:#100796;color:#fff;font-family:"Poppins",sans-serif;font-weight:800;
     font-size:19px;padding:6px 14px;border-radius:999px;white-space:nowrap;
     box-shadow:0 6px 16px rgba(0,0,0,.35)}
  #flightMap .fm-label.below{transform:translate(-50%,50%)}
  #flightMap .fm-label .dt{color:#FFC500;margin-left:7px;font-size:16px}

  /* Landmark sweep (content.json "landmark_sweep"): a small icon+name/date
     chip for ONE city sweeps horizontally across the headroom band, timed to
     land right as the speaker says that city's name -- a front overlay
     (never behind the subject), so it always reads clearly regardless of
     framing. "top" per-reel configurable (pick clear headroom from a frame). */
  #landmarkSweep{position:absolute;left:0;top:__SWEEP_TOP__;width:100%;height:190px;
     overflow:visible;pointer-events:none}
  #landmarkSweep .ls-chip{position:absolute;left:0;top:0;display:flex;align-items:center;
     gap:18px;background:linear-gradient(115deg,#100796,#7a1a8a 55%,#E84B37);
     border-radius:26px;padding:14px 30px 14px 14px;box-shadow:0 14px 30px rgba(0,0,0,.45);
     opacity:0}
  #landmarkSweep .ls-icon{width:130px;height:130px;flex:none;border-radius:20px;
     overflow:hidden;box-shadow:0 6px 16px rgba(0,0,0,.35),inset 0 0 0 3px rgba(255,255,255,.55)}
  #landmarkSweep .ls-icon svg{width:100%;height:100%}
  #landmarkSweep .ls-icon img{width:100%;height:100%;object-fit:cover;display:block}
  #landmarkSweep .ls-text{display:flex;flex-direction:column}
  #landmarkSweep .ls-city{font-family:"Poppins",sans-serif;font-weight:800;font-size:38px;
     color:#fff;letter-spacing:.01em;white-space:nowrap;text-shadow:0 4px 12px rgba(0,0,0,.4)}
  #landmarkSweep .ls-date{font-family:"Poppins",sans-serif;font-weight:700;font-size:22px;
     color:#FFC500;letter-spacing:.03em;margin-top:2px}

  /* Overlay card: optional subheading + CTA red pill (bottom, pill lands
     ~y1420 per spec whether or not a subheading is present -- the container
     top shifts up by the subheading's own rendered height so the pill's
     final position stays put). */
  #ctaCard{position:absolute;left:0;right:0;top:1420px;text-align:center;opacity:0;visibility:hidden}
  #ctaCard.has-sub{top:1348px}
  #ctaCard .sub{display:none;font-family:"Poppins",sans-serif;font-weight:800;font-size:32px;
     color:#fff;letter-spacing:.01em;line-height:1.15;margin:0 40px 16px;
     text-shadow:0 4px 14px rgba(0,0,0,.55)}
  #ctaCard.has-sub .sub{display:block}
  #ctaCard .pill{display:inline-block;background:#E84B37;color:#fff;font-family:"Poppins",sans-serif;
     font-weight:800;font-size:42px;letter-spacing:.03em;padding:26px 56px;border-radius:999px;
     box-shadow:0 14px 34px rgba(0,0,0,.4)}

  /* Confetti burst: fires once when the CTA lands, for a "fun" celebratory beat */
  #confetti{position:absolute;left:50%;top:1462px;width:0;height:0}
  #confetti .p{position:absolute;left:0;top:0;width:16px;height:16px;border-radius:3px;opacity:0}

  /* Speaker intro lower-third: ONE merged card -- gold OMARA badge tile (left)
     + navy-to-gold name/role panel (right), bottom-left, on screen only for
     the opening seconds (never overlaps the bottom CTA slot -- that card runs
     much later). Badge + name share this single entrance/exit. */
  #introCard{position:absolute;left:44px;top:1490px;opacity:0;visibility:hidden;
     display:flex;align-items:stretch;border-radius:20px;overflow:hidden;
     box-shadow:0 16px 40px rgba(0,0,0,.5)}
  #introCard .badge-tile{position:relative;flex:none;width:152px;background:#FFC500;
     display:flex;flex-direction:column;align-items:center;justify-content:center;
     text-align:center;padding:12px 8px;gap:3px;overflow:hidden}
  #introCard .badge-tile.has-image{padding:0}
  #introCard .badge-tile.hidden{display:none}
  #introCard .badge-tile.has-image img{display:block;width:100%;height:100%;object-fit:cover}
  #introCard .dotmap{display:grid;grid-template-columns:repeat(9,4.2px);
     grid-auto-rows:4.2px;gap:1.6px}
  #introCard .dotmap i{width:4.2px;height:4.2px;border-radius:50%;background:transparent}
  #introCard .dotmap i.on{background:#1A1A1A}
  #introCard .hdr{font-family:"Poppins",sans-serif;font-weight:800;font-size:10.5px;
     line-height:1.2;color:#1A1A1A;letter-spacing:.01em}
  #introCard .numstrip{background:#fff;border-radius:4px;padding:3px 9px;
     font-family:"Poppins",sans-serif;font-weight:800;font-size:19px;color:#100796;
     letter-spacing:.01em}
  #introCard .url{font-family:"Poppins",sans-serif;font-weight:700;font-size:8px;color:#1A1A1A}
  #introCard .info-panel{flex:auto;display:flex;flex-direction:column;justify-content:center;
     background:linear-gradient(90deg,#100796 58%,#B9821E 100%);padding:20px 34px;text-align:left}
  #introCard .nm{font-family:"Poppins",sans-serif;font-weight:800;font-size:38px;color:#fff;
     letter-spacing:.01em;line-height:1.1}
  #introCard .role{font-family:"Poppins",sans-serif;font-weight:700;font-size:21px;color:#FFE9B0;
     letter-spacing:.03em;margin-top:5px}

  /* Document highlight: redacted letter shown as a "paper card + stamp" --
     never a raw full-bleed photo -- landing in the upper zone so it never
     collides with the caption band (top 62%) or the bottom CTA slot (1420px). */
  .doc-card{position:absolute;left:50%;top:300px;width:640px;margin-left:-320px;
     opacity:0;visibility:hidden}
  /* fan-group variant: smaller, docked top-left so it never covers the
     speaker's face -- x/y offsets are applied per-card via GSAP (see script). */
  .doc-card.fan{left:36px;top:250px;width:340px;margin-left:0}
  /* poster variant (landscape promo graphic, e.g. an event flyer): no torn-
     paper bottom margin reserved for a label (the image already carries its
     own text) and no stamp -- see the "poster" doc property in the script. */
  .doc-card.poster .paper{padding:14px;background:#fff}
  .doc-card.poster .paper img{max-height:none}
  .doc-card .paper{position:relative;background:#fdfdf5;border-radius:8px;
     padding:20px 20px 64px;box-shadow:0 26px 60px rgba(0,0,0,.55),0 2px 0 rgba(0,0,0,.08)}
  .doc-card .paper img{display:block;width:100%;height:auto;max-height:760px;
     object-fit:contain;border-radius:2px;box-shadow:inset 0 0 0 1px rgba(0,0,0,.08)}
  .doc-card .label{position:absolute;left:0;right:0;bottom:16px;text-align:center;
     font-family:"Poppins",sans-serif;font-weight:800;font-size:26px;letter-spacing:.07em;
     color:#100796;text-transform:uppercase}
  .doc-card .stamp{position:absolute;right:-28px;top:-28px;width:114px;height:114px;
     border-radius:50%;background:radial-gradient(circle at 35% 30%,#4CFF9A,#31EB7C 60%,#1CB35E);
     display:flex;align-items:center;justify-content:center;transform:scale(0) rotate(-18deg);
     box-shadow:0 10px 26px rgba(0,0,0,.4);border:4px solid #fff}
  .doc-card .stamp svg{width:58px;height:58px}

  /* Light decorative layer (opt-in via content.json "decor"): soft brand-colour
     orbs drifting in the empty wall margins + a small social handle low-centre.
     Deliberately low-opacity/blurred so it reads as airy atmosphere, never
     competing with the speaker or captions. Sits behind everything (first in
     the DOM). */
  #decor{position:absolute;inset:0;pointer-events:none;z-index:0}
  #decor .orb{position:absolute;border-radius:50%;filter:blur(14px);opacity:0}
  #decor .o1{width:150px;height:150px;background:#FFC500;left:120px;top:330px}
  #decor .o2{width:120px;height:120px;background:#00B3E3;left:840px;top:250px}
  #decor .o3{width:96px;height:96px;background:#E84B37;left:140px;top:1180px}
  #decor .o4{width:130px;height:130px;background:#100796;left:880px;top:1300px}
  #decor .o5{width:80px;height:80px;background:#FFC500;left:860px;top:660px}
  #decor #handle{position:absolute;left:0;right:0;bottom:64px;text-align:center;
     font-family:"Poppins",sans-serif;font-weight:700;font-size:30px;color:#fff;
     letter-spacing:.05em;opacity:0;text-shadow:0 3px 12px rgba(0,0,0,.7)}
  /* extra "little visuals" (decor.sparkles): 4-point twinkle stars + thin
     outline rings, crisp counterpoints to the soft orbs, in the empty margins. */
  #decor .spk{position:absolute;opacity:0;background:#FFC500;
     clip-path:polygon(50% 0,61% 39%,100% 50%,61% 61%,50% 100%,39% 61%,0 50%,39% 39%)}
  #decor .spk.white{background:#fff}
  #decor .s1{width:30px;height:30px;left:180px;top:540px}
  #decor .s2{width:24px;height:24px;left:872px;top:470px}
  #decor .s3{width:20px;height:20px;left:112px;top:980px}
  #decor .s4{width:28px;height:28px;left:946px;top:1050px}
  #decor .s5{width:22px;height:22px;left:928px;top:1500px}
  #decor .ring{position:absolute;opacity:0;border-radius:50%;background:transparent;border:3px solid}
  #decor .r1{width:56px;height:56px;left:120px;top:1150px;border-color:#00B3E3}
  #decor .r2{width:44px;height:44px;left:900px;top:620px;border-color:#FFC500}

  /* Animated checklist overlay (content.json "lists"): a designed navy panel
     that sits over the speaker's chest (clear of the face) while they list
     items -- each row ticks in with a green check as it's spoken. Replaces the
     2-word caption for the window so the two never fight. */
  #listHost{position:absolute;inset:0;pointer-events:none}
  .list-card{position:absolute;left:50%;top:__LIST_TOP__;transform:translateX(-50%);width:780px;
     opacity:0;visibility:hidden;background:rgba(16,7,150,.82);border-radius:28px;
     padding:26px 40px 30px;box-shadow:0 26px 64px rgba(0,0,0,.55);
     border:1px solid rgba(255,255,255,.14)}
  .list-card .lc-title{font-family:"Poppins",sans-serif;font-weight:800;font-size:34px;
     color:#FFC500;letter-spacing:.06em;margin-bottom:14px;text-align:left}
  .list-card .lc-row{display:flex;align-items:center;gap:22px;padding:11px 0;opacity:0}
  .list-card .lc-check{flex:none;width:58px;height:58px;border-radius:50%;background:#31EB7C;
     display:flex;align-items:center;justify-content:center;transform:scale(0);
     box-shadow:0 6px 16px rgba(49,235,124,.45)}
  .list-card .lc-check svg{width:34px;height:34px}
  .list-card .lc-label{font-family:"Poppins",sans-serif;font-weight:800;font-size:48px;
     color:#fff;letter-spacing:.01em}

  /* Quick emphasis badges (content.json "badges"): a small icon+text pill that
     pops in at a key spoken moment in the upper zone, floats, then leaves. */
  #badgeHost{position:absolute;inset:0;pointer-events:none}
  .badge-pop{position:absolute;opacity:0;visibility:hidden;display:flex;align-items:center;
     gap:15px;padding:15px 30px;border-radius:999px;white-space:nowrap;
     box-shadow:0 14px 34px rgba(0,0,0,.42)}
  .badge-pop .bp-ico{flex:none;width:42px;height:42px;display:flex;align-items:center;
     justify-content:center}
  .badge-pop .bp-ico svg{width:42px;height:42px}
  .badge-pop .bp-txt{font-family:"Poppins",sans-serif;font-weight:800;font-size:42px;
     letter-spacing:.02em}
  /* Badge effect: "shimmer" -- a light sweep masked over the pill, position
     driven by a GSAP-tweened CSS custom property (catalog: shimmer-sweep). */
  .badge-pop .bp-shimmer{position:absolute;inset:0;pointer-events:none;border-radius:inherit;
     mix-blend-mode:overlay;background:linear-gradient(120deg,transparent 0%,
     transparent calc(var(--shimmer-pos,-20%) - 15%),rgba(255,255,255,.85) var(--shimmer-pos,-20%),
     transparent calc(var(--shimmer-pos,-20%) + 15%),transparent 100%)}
  /* Badge effect: "particles" -- small dots radiating from the pill on entry
     (catalog: caption-particle-burst, seeded RNG so it's frame-deterministic). */
  .badge-pop .bp-particle{position:absolute;left:50%;top:50%;border-radius:50%;
     opacity:0;pointer-events:none}
  /* Badge effect: "pixelate" -- pill materializes out of a small cell grid
     instead of scaling in (catalog: grid-pixelate-wipe -- same technique as
     this reel's cut transitions, scoped down to badge size). */
  .badge-pop .bp-pixel-overlay{position:absolute;inset:0;pointer-events:none;display:grid;
     border-radius:inherit;overflow:hidden}
  .badge-pop .bp-pixel-overlay .bp-cell{transform:scale(1);transform-origin:center center}

  /* DM/notification mockup (content.json "dm_bubbles"): a phone-style incoming-
     message card for a beat where the speaker describes someone messaging them.
     "red" flag = danger glow + shady wobble + flag stamp (see _DM_FLAG_STYLE);
     "green" flag = calm brand-teal glow, no wobble/stamp. */
  #dmHost{position:absolute;inset:0;pointer-events:none}
  .dm-card{position:absolute;left:50%;top:365px;transform:translateX(-50%);
     opacity:0;visibility:hidden;display:flex;align-items:center;gap:16px;
     max-width:860px;padding:18px 26px;border-radius:22px;background:rgba(18,18,26,.92);
     border:2.5px solid var(--dm-accent);box-shadow:0 0 0 1px rgba(255,255,255,.04),
     0 16px 38px rgba(0,0,0,.5),0 0 40px var(--dm-glow)}
  .dm-card .dm-avatar{flex:none;width:60px;height:60px;border-radius:50%;
     background:rgba(255,255,255,.08);display:flex;align-items:center;
     justify-content:center;font-size:32px;border:2px solid var(--dm-accent)}
  .dm-card .dm-meta{flex:1;min-width:0}
  .dm-card .dm-sender{font-family:"Poppins",sans-serif;font-weight:700;font-size:24px;
     color:var(--dm-accent);letter-spacing:.01em;margin-bottom:4px}
  .dm-card .dm-msg{font-family:"Poppins",sans-serif;font-weight:800;font-size:32px;
     line-height:1.14;color:#fff;white-space:nowrap}
  .dm-card .dm-stamp{position:absolute;top:-26px;right:-20px;opacity:0;
     width:72px;height:72px;border-radius:50%;background:var(--dm-accent);
     display:flex;align-items:center;justify-content:center;font-size:38px;
     box-shadow:0 8px 22px rgba(0,0,0,.45)}

  /* Visa-pathway chain (content.json "pathway"): a navy card holding a small
     stylized Australia map with one city pinned, above a 3-step icon chain
     joined by arrows that draw in sequence. Widths are fixed rather than
     fluid so the row can never reflow mid-animation: 3x250 + 2x70 = 890 into
     908px of inner width. The arrow bar scales while its head is a separate
     absolutely-positioned element -- scaling a border-triangle pseudo-element
     would distort the arrowhead, and animating width would reflow the row. */
  #pathwayHost{position:absolute;left:0;right:0;top:__PATHWAY_TOP__;text-align:center}
  .pw-card{position:relative;display:inline-block;width:960px;padding:24px 24px 28px;
     border-radius:24px;background:linear-gradient(135deg,#100796 0%,#1c1099 60%,#2a0f8f 100%);
     box-shadow:0 18px 40px rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.14);
     opacity:0;visibility:hidden}
  .pw-kicker{display:inline-block;background:var(--pw-acc,#FFC500);color:#0a2e17;
     font-family:"Poppins",sans-serif;font-weight:800;font-size:23px;letter-spacing:.05em;
     padding:8px 22px;border-radius:999px;margin-bottom:12px}
  .pw-map{position:relative;width:132px;height:113px;margin:0 auto 8px}
  .pw-map svg{position:absolute;left:0;top:0;width:132px;height:113px;opacity:0}
  .pw-pin{position:absolute;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;
     background:var(--pw-acc,#FFC500);border:3px solid #fff;opacity:0}
  .pw-pulse{position:absolute;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;
     border:3px solid var(--pw-acc,#FFC500);opacity:0}
  .pw-pinlbl{position:absolute;transform:translate(-50%,-200%);opacity:0;white-space:nowrap;
     font-family:"Poppins",sans-serif;font-weight:800;font-size:17px;color:#fff;
     background:rgba(16,7,150,.92);border:1px solid var(--pw-acc,#FFC500);
     border-radius:999px;padding:3px 12px}
  .pw-chain{display:flex;align-items:stretch;justify-content:center}
  .pw-step{width:250px;flex:0 0 250px;background:rgba(255,255,255,.07);
     border:1px solid rgba(255,255,255,.16);border-radius:18px;padding:11px 8px 13px;opacity:0}
  .pw-step.final{background:rgba(255,255,255,.15);border-color:var(--pw-acc,#FFC500)}
  .pw-ico{width:50px;height:50px;margin:0 auto 8px;display:block}
  .pw-ico svg{width:50px;height:50px;display:block}
  .pw-lbl{font-family:"Poppins",sans-serif;font-weight:900;font-size:25px;color:#fff;line-height:1.12}
  .pw-sub{font-family:"Poppins",sans-serif;font-weight:600;font-size:16px;color:#C9C9E2;margin-top:4px}
  .pw-arrow{width:70px;flex:0 0 70px;position:relative;align-self:center;height:24px}
  .pw-arrow svg{width:100%;height:100%;display:block;overflow:visible}
  .pw-arrow .curl-path{stroke-dasharray:100;stroke-dashoffset:100}
  .pw-arrow .tip-path{opacity:0;transform-origin:54px 13px}

  /* Per-reel accent override (content.json "accent") -- emitted LAST so it
     wins on equal specificity. Empty for every reel that doesn't opt in, so
     existing reels keep rendering byte-identically. See _accent_css(). */
  __ACCENT_CSS__
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="__DUR__" data-fps="30" data-width="1080" data-height="1920">
  __DECOR_DOM__
  <div id="cap" class="__CAP_HIGHLIGHT_CLASS__"></div>
  <div id="heroHost"></div>
  <div id="hookBanner"><span></span></div>
  <div id="savePrompt"><span></span></div>
  <div id="dateCard">
    <div class="kickerWrap"><div class="kicker">__INFO_KICKER__<div class="shine"></div></div></div>
    <br>
    <div class="dateWrap"><div class="dateBlock"></div><div class="date">__INFO_LINE1__</div></div>
    <br>
    <div class="venueWrap"><div class="venueBlock"></div><div class="venue">__INFO_LINE2__</div></div>
  </div>
  <div id="urgencyChip"><span></span></div>
  <div id="roadshowCard"></div>
  <div id="flightMap"></div>
  <div id="landmarkSweep"></div>
  <div id="ctaCard" class="__CTA_CARD_CLASS__"><div class="sub">__CTA_SUB__</div><div class="pill">__CTA_TEXT__</div></div>
  <div id="introCard">
    <div class="badge-tile __BADGE_CLASS__">__BADGE_INNER__</div>
    <div class="info-panel"><div class="nm">__NAME_TEXT__</div><div class="role">__NAME_ROLE__</div></div>
  </div>
  <div id="confetti"></div>
  <div id="docHost"></div>
  <div id="listHost"></div>
  <div id="badgeHost"></div>
</div>
<script>
(function(){
  window.__timelines=window.__timelines||{};
  var CARDS=__CARDS__;
  var host=document.getElementById("cap");
  var tl=gsap.timeline({paused:true});

  CARDS.forEach(function(c){
    var el=document.createElement("div");
    el.className="card";
    el.innerHTML = c.words.map(function(w){
      return '<span class="w'+(w.gold?' gold':'')+'">'+w.text+'</span>';
    }).join(" ");
    host.appendChild(el);

    // Kinetic entrance: slide up + back-ease overshoot scale + slight de-rotate.
    tl.set(el,{visibility:"visible"},c.start);
    tl.fromTo(el,
      {opacity:0, y:34, scale:0.78, rotation:-3},
      {opacity:1, y:0, scale:1, rotation:0, duration:0.22, ease:"back.out(2.2)"},
      c.start);

    // Gold-keyword pulse: the highlighted term gets an extra emphasis beat
    // shortly after the card lands, drawing the eye to the key term.
    // Scale modestly (1.08, not 1.16) -- with adjacent gold words the fixed
    // 22px side margins above must survive two neighbors growing toward each
    // other at once; a smaller pulse keeps a safe gap even at peak.
    var goldEls = el.querySelectorAll(".gold");
    if (goldEls.length) {
      tl.fromTo(goldEls, {scale:1}, {scale:1.08, duration:0.1, ease:"power2.out"}, c.start+0.16);
      tl.to(goldEls, {scale:1, duration:0.16, ease:"power2.inOut"}, c.start+0.26);
    }

    // Quick exit right before the next card lands (still a hard cut overall).
    tl.to(el,{opacity:0, scale:0.92, duration:0.08, ease:"power1.in"}, Math.max(c.start+0.12, c.end-0.08));
    tl.set(el,{visibility:"hidden"},c.end);
  });

  // Overlay card 1: seminar date kicker, staggered 3-beat reveal -- each fact
  // (what / when / where) gets its own colour-block backdrop and its own
  // distinct entrance so all three read as separately-highlighted moments.
  var DS = __DATE_START__, DE = __DATE_END__;
  var kickerWrap = document.querySelector("#dateCard .kickerWrap");
  var dateWrap = document.querySelector("#dateCard .dateWrap");
  var venueWrap = document.querySelector("#dateCard .venueWrap");
  var dateBlock = document.querySelector("#dateCard .dateBlock");
  var venueBlock = document.querySelector("#dateCard .venueBlock");
  var shine = document.querySelector("#dateCard .kicker .shine");

  // Beat 1 (t+0.00): "FREE MIGRATION SEMINAR" kicker pops in, then a light
  // sweep shines across it.
  tl.set(kickerWrap,{visibility:"visible"}, DS);
  tl.fromTo(kickerWrap, {opacity:0, y:-22, scale:0.88},
    {opacity:1, y:0, scale:1, duration:0.26, ease:"back.out(2)"}, DS);
  tl.fromTo(shine, {x:"-120%"}, {x:"260%", duration:0.5, ease:"power1.inOut"}, DS+0.3);

  // Beat 2 (t+0.30): a red colour block "stamps" in behind "13 JULY" with an
  // overshoot bounce -- the boldest, most attention-grabbing beat since the
  // date is the single most actionable fact.
  tl.set(dateWrap,{visibility:"visible"}, DS+0.30);
  tl.fromTo(dateBlock, {scaleX:0}, {scaleX:1, duration:0.22, ease:"power3.out"}, DS+0.30);
  tl.set(dateWrap, {opacity:1}, DS+0.30);
  tl.fromTo(dateWrap, {scale:1.35}, {scale:1, duration:0.3, ease:"back.out(3)"}, DS+0.34);

  // Beat 3 (t+0.62): a blue pill slides in left-to-right under the venue name.
  tl.set(venueWrap,{visibility:"visible"}, DS+0.62);
  tl.set(venueWrap, {opacity:1}, DS+0.62);
  tl.fromTo(venueBlock, {scaleX:0}, {scaleX:1, duration:0.26, ease:"power2.out"}, DS+0.62);
  tl.fromTo(venueWrap, {x:-30, opacity:0}, {x:0, opacity:1, duration:0.26, ease:"power2.out"}, DS+0.62);

  // All three exit together just before the card's window ends.
  [kickerWrap, dateWrap, venueWrap].forEach(function(el){
    tl.to(el, {opacity:0, y:-14, duration:0.2, ease:"power2.in"}, DE-0.2);
    tl.set(el, {visibility:"hidden"}, DE);
  });

  // Multi-city roadshow card: kicker pops, then each city card stamps in one
  // after another (staggered), then the WHOLE thing holds on screen (no
  // per-element exit choreography needed -- it just fades out near RS.end,
  // since the point is dwell time, not a quick beat like #dateCard).
  var RS = __ROADSHOW__;
  if (RS && RS.cities && RS.cities.length) {
    var rsHost = document.getElementById("roadshowCard");
    var rsKicker = document.createElement("div");
    rsKicker.className = "rs-kicker";
    rsKicker.textContent = RS.kicker || "";
    rsHost.appendChild(rsKicker);
    var rsCities = document.createElement("div");
    rsCities.className = "rs-cities";
    rsHost.appendChild(rsCities);

    var RS_S = RS.start, RS_E = RS.end;
    tl.set(rsHost, {visibility:"visible"}, RS_S);
    tl.fromTo(rsHost, {opacity:0}, {opacity:1, duration:0.01}, RS_S);
    tl.fromTo(rsKicker, {opacity:0, scale:0.85, y:-18},
      {opacity:1, scale:1, y:0, duration:0.3, ease:"back.out(2.2)"}, RS_S);

    RS.cities.forEach(function(c, i){
      var el = document.createElement("div");
      el.className = "rs-city";
      el.innerHTML =
        '<div class="rs-city-name">' + c.city + '</div><br>' +
        '<div class="rs-row"><span class="rs-date">' + c.date + '</span>' +
        // omit the time pill entirely when no time is known -- an empty span
        // still renders as a small stray cyan blob next to the date
        (c.time ? '<span class="rs-time">' + c.time + '</span>' : '') + '</div>' +
        '<div class="rs-venue">' + c.venue + '</div>';
      rsCities.appendChild(el);

      var enter = RS_S + 0.32 + i * 0.4;
      tl.fromTo(el, {opacity:0, y:46, scale:0.92},
        {opacity:1, y:0, scale:1, duration:0.4, ease:"back.out(1.8)"}, enter);
      var dateEl = el.querySelector(".rs-date");
      tl.fromTo(dateEl, {scale:1.3}, {scale:1, duration:0.24, ease:"back.out(3)"}, enter + 0.08);
    });

    // Whole card slips out just before the window closes.
    tl.to(rsHost, {opacity:0, y:-16, duration:0.25, ease:"power2.in"}, RS_E - 0.25);
    tl.set(rsHost, {visibility:"hidden"}, RS_E);

    // Urgency chip: shares the roadshow card's window verbatim, pops in
    // just ahead of the kicker.
    var UC = __URGENCY_CHIP__;
    if (UC && UC.text) {
      var ucEl = document.getElementById("urgencyChip");
      ucEl.querySelector("span").textContent = UC.text;
      tl.set(ucEl, {visibility:"visible"}, RS_S);
      tl.fromTo(ucEl, {opacity:0, scale:0.8, y:-10},
        {opacity:1, scale:1, y:0, duration:0.26, ease:"back.out(2.4)"}, RS_S);
      tl.to(ucEl, {opacity:0, y:-10, duration:0.2, ease:"power2.in"}, RS_E - 0.2);
      tl.set(ucEl, {visibility:"hidden"}, RS_E);
    }
  }

  // Flying-plane multi-city map: kicker + AU silhouette scale in, then the
  // plane hops city to city (positions already resolved to viewBox coords
  // in Python) -- each arrival gets a pin + expanding pulse ring + label,
  // all of which stay on screen so by the last city the whole route reads
  // as one accumulated map, mirroring "roadshow"'s stacked-cards payoff.
  var FM = __FLIGHT__;
  if (FM && FM.cities && FM.cities.length) {
    var fmHost = document.getElementById("flightMap");
    var fmKicker = document.createElement("div");
    fmKicker.className = "fm-kicker";
    fmKicker.textContent = FM.kicker || "";
    fmHost.appendChild(fmKicker);
    var fmStage = document.createElement("div");
    fmStage.className = "fm-stage";
    fmStage.innerHTML = '<svg viewBox="0 0 100 86">' +
      '<path d="M 68 2 L 72 10 L 78 22 L 80 32 L 76 44 L 70 52 L 60 58 L 48 54 L 36 56' +
      ' L 20 58 L 12 50 L 8 38 L 10 24 L 16 14 L 26 8 L 34 12 L 40 6 L 48 4' +
      ' L 52 14 L 58 12 L 62 2 Z" fill="#1A10C0" stroke="#00B3E3" stroke-width="1.6"/>' +
      '<ellipse cx="66" cy="70" rx="5" ry="4" fill="#1A10C0" stroke="#00B3E3" stroke-width="1.4"/></svg>';
    fmHost.appendChild(fmStage);
    var fmPlane = document.createElement("div");
    fmPlane.className = "fm-plane";
    fmPlane.textContent = "✈️";
    fmStage.appendChild(fmPlane);

    var FM_S = FM.start, FM_E = FM.end;
    var stageW = 740, stageH = 637;
    function fmPx(vb) { return [vb[0] / 100 * stageW, vb[1] / 86 * stageH]; }

    tl.set(fmHost, {visibility:"visible"}, FM_S);
    tl.fromTo(fmHost, {opacity:0}, {opacity:1, duration:0.01}, FM_S);
    tl.fromTo(fmKicker, {opacity:0, scale:0.85, y:-18},
      {opacity:1, scale:1, y:0, duration:0.26, ease:"back.out(2.2)"}, FM_S);
    tl.fromTo(fmStage, {opacity:0, scale:0.88},
      {opacity:1, scale:1, duration:0.3, ease:"power2.out"}, FM_S + 0.1);

    var hopDur = 0.28, holdDur = 0.32;
    var t0 = FM_S + 0.46;
    var startPx = fmPx(FM.cities[0].pos);
    tl.set(fmPlane, {left:startPx[0], top:startPx[1]}, t0 - 0.12);
    tl.fromTo(fmPlane, {opacity:0, scale:0.4}, {opacity:1, scale:1, duration:0.14, ease:"back.out(2.6)"}, t0 - 0.12);

    FM.cities.forEach(function(c, i){
      var px = fmPx(c.pos);
      var arriveAt = t0 + i * (hopDur + holdDur);
      if (i > 0) {
        tl.to(fmPlane, {left:px[0], top:px[1], duration:hopDur, ease:"power1.inOut"}, arriveAt - hopDur);
      }
      var pin = document.createElement("div");
      pin.className = "fm-pin";
      pin.style.left = px[0] + "px"; pin.style.top = px[1] + "px";
      fmStage.appendChild(pin);
      var pulse = document.createElement("div");
      pulse.className = "fm-pulse";
      pulse.style.left = px[0] + "px"; pulse.style.top = px[1] + "px";
      fmStage.appendChild(pulse);
      var label = document.createElement("div");
      // crowded southern cluster (Adelaide/Melbourne/Tasmania) sits close
      // together -- flip the label to sit BELOW the pin there so it doesn't
      // collide with a neighbour's label above; northern cities (Perth,
      // Brisbane) have open space above their pin, so the default stands.
      label.className = "fm-label" + (px[1] > stageH * 0.5 ? " below" : "");
      label.style.left = px[0] + "px"; label.style.top = px[1] + "px";
      label.innerHTML = c.city + '<span class="dt">' + c.date + '</span>';
      fmStage.appendChild(label);

      tl.fromTo(pin, {opacity:0, scale:0}, {opacity:1, scale:1, duration:0.16, ease:"back.out(3)"}, arriveAt);
      tl.fromTo(pulse, {opacity:0.9, scale:0.4}, {opacity:0, scale:6, duration:0.55, ease:"power1.out"}, arriveAt);
      tl.fromTo(label, {opacity:0, y:8}, {opacity:1, y:0, duration:0.22, ease:"back.out(2.4)"}, arriveAt + 0.08);
    });

    tl.to(fmHost, {opacity:0, y:-16, duration:0.25, ease:"power2.in"}, FM_E - 0.25);
    tl.set(fmHost, {visibility:"hidden"}, FM_E);
  }

  // Landmark sweep: one icon+name/date chip per city sweeps in from the
  // right, HOLDS steady front-and-center for at least a full second (long
  // enough to actually read), then sweeps on out to the left -- a front
  // overlay, always legible, never behind the subject. Chips queue
  // sequentially (never two on screen at once) so each genuinely gets its
  // full hold; a chip only starts once the previous one has cleared, so
  // later cities can lag behind their own spoken cue -- readability over
  // split-second sync.
  var LS = __LANDMARK_SWEEP__;
  if (LS && LS.length) {
    var lsHost = document.getElementById("landmarkSweep");
    var IN_DUR = 0.22, HOLD_DUR = 1.1, OUT_DUR = 0.22;
    var CHIP_TOTAL = IN_DUR + HOLD_DUR + OUT_DUR;
    var REST_X = 300;   // roughly centers a ~480px chip on a 1080px canvas
    var lsNextStart = null;
    LS.forEach(function(c){
      var chip = document.createElement("div");
      chip.className = "ls-chip";
      var iconHtml = c.photo ? '<img src="' + c.photo + '" alt="' + c.city + '"/>' : c.svg;
      chip.innerHTML = '<div class="ls-icon">' + iconHtml + '</div>' +
        '<div class="ls-text"><div class="ls-city">' + c.city + '</div>' +
        '<div class="ls-date">' + c.date + '</div></div>';
      lsHost.appendChild(chip);
      var desired = c.at - 0.15;
      var enter = (lsNextStart === null) ? desired : Math.max(desired, lsNextStart);
      lsNextStart = enter + CHIP_TOTAL;
      tl.fromTo(chip, {opacity:0, x:1160, rotation:-2},
        {opacity:1, x:REST_X, rotation:0, duration:IN_DUR, ease:"back.out(1.5)"}, enter);
      tl.to(chip, {x:-620, duration:OUT_DUR, ease:"power1.in"}, enter + IN_DUR + HOLD_DUR);
      tl.to(chip, {opacity:0, duration:OUT_DUR}, enter + IN_DUR + HOLD_DUR);
    });
  }

  // Overlay card 2: CTA red pill (bottom placement, per spec text-only)
  var cc = document.getElementById("ctaCard");
  tl.set(cc,{visibility:"visible"}, __CTA_START__);
  tl.fromTo(cc, {opacity:0, y:30, scale:0.85}, {opacity:1, y:0, scale:1, duration:0.32, ease:"back.out(2)"}, __CTA_START__);
  tl.to(cc.querySelector(".pill"), {scale:1.04, duration:0.5, ease:"sine.inOut", repeat:3, yoyo:true}, __CTA_START__+0.4);
  tl.to(cc, {opacity:0, y:18, duration:0.2, ease:"power2.in"}, __CTA_END__-0.2);
  tl.set(cc, {visibility:"hidden"}, __CTA_END__);

  // Speaker intro lower-third: badge tile + name/role panel move as ONE unit,
  // sliding in from the left with the house back-ease, holding through the
  // opening beat, then slipping back out together.
  var ic = document.getElementById("introCard");
  var NS = __NAME_START__, NE = __NAME_END__;
  if (NE > NS) {
    tl.set(ic,{visibility:"visible"}, NS);
    tl.fromTo(ic, {opacity:0, x:-56}, {opacity:1, x:0, duration:0.34, ease:"back.out(1.8)"}, NS);
    tl.to(ic, {opacity:0, x:-36, duration:0.25, ease:"power2.in"}, Math.max(NS+0.4, NE-0.25));
    tl.set(ic,{visibility:"hidden"}, NE);
  }

  // Confetti burst: ~16 dots explode outward from the pill the instant it lands.
  var confettiHost = document.getElementById("confetti");
  var COLORS = ["#FFC500","#31EB7C","#00B3E3","#E84B37","#fff"];
  var N = 16;
  for (var i=0;i<N;i++){
    var p = document.createElement("div");
    p.className = "p";
    p.style.background = COLORS[i % COLORS.length];
    if (i % 3 === 0) p.style.borderRadius = "50%";
    confettiHost.appendChild(p);
    var angle = (Math.PI * 2 * i) / N + (i % 2 ? 0.15 : -0.15);
    var dist = 220 + (i % 4) * 40;
    var dx = Math.cos(angle) * dist, dy = Math.sin(angle) * dist * 0.7 - 60;
    tl.fromTo(p, {x:0, y:0, opacity:1, scale:0.4, rotation:0},
      {x:dx, y:dy, opacity:0, scale:1, rotation:(i%2?1:-1)*220, duration:0.85, ease:"power2.out"},
      __CTA_START__);
  }

  // Document highlights: redacted letters as "paper card + stamp" overlays,
  // placed wherever resolve_anchor() found the anchor_phrase in the transcript.
  // Alternating tilt so back-to-back documents don't read as identical.
  var DOCS = __DOCS__;
  var docHost = document.getElementById("docHost");
  var SEAL = '<svg viewBox="0 0 24 24" fill="none"><path d="M12 2l7 3v6c0 4.4-3 8-7 9-4-1-7-4.6-7-9V5l7-3z" fill="#fff"/><path d="M8.4 12.2l2.5 2.5 4.7-5" stroke="#100796" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  DOCS.forEach(function(d, idx){
    if (d.group) {
      // Fan-group: several documents tied to the ONE moment/anchor window,
      // revealed one at a time with a graceful stagger and a slight fanned
      // offset per card (like a hand of cards), all exiting together.
      var n = d.group.length;
      var span = Math.max(0.6, d.end - d.start);
      var stagger = Math.min(1.3, (span - 0.6) / n);
      d.group.forEach(function(g, gi){
        var fanX = gi * 22;
        var fanY = gi * 20;
        var fanRot = -9 + gi * (18 / Math.max(1, n - 1));
        var el = document.createElement("div");
        el.className = "doc-card fan";
        el.style.zIndex = 10 + gi;
        gsap.set(el, {x: fanX});
        el.innerHTML = '<div class="paper"><img src="' + g.img + '" alt="document"/>' +
          (g.label ? '<div class="label">' + g.label + '</div>' : '') +
          '<div class="stamp">' + SEAL + '</div></div>';
        docHost.appendChild(el);

        var enter = d.start + gi * stagger;
        tl.set(el, {visibility:"visible"}, enter);
        tl.fromTo(el,
          {opacity:0, y:fanY + 54, scale:0.8, rotation:fanRot - 11},
          {opacity:1, y:fanY, scale:1, rotation:fanRot, duration:0.4, ease:"back.out(1.7)"},
          enter);

        var stamp = el.querySelector(".stamp");
        tl.fromTo(stamp, {scale:0, rotation:-18},
          {scale:1, rotation:-8, duration:0.24, ease:"back.out(3)"}, enter + 0.28);

        tl.to(el, {opacity:0, y:fanY - 24, scale:0.94, duration:0.24, ease:"power2.in"}, d.end - 0.24);
        tl.set(el, {visibility:"hidden"}, d.end);
      });
      return;
    }

    // "poster" (landscape promo graphic): straight (no tilt), no stamp --
    // an authentication seal means nothing on a marketing flyer, only on a
    // document being verified. Everything else (entrance/exit motion, upper-
    // zone placement) stays identical so it still reads as the same family
    // of overlay.
    var tilt = d.poster ? 0 : (idx % 2 ? 2.2 : -2.2);
    var el = document.createElement("div");
    el.className = "doc-card" + (d.poster ? " poster" : "");
    el.style.width = d.width + "px";
    el.style.marginLeft = (-d.width / 2) + "px";
    el.style.top = d.top;
    el.style.transform = "rotate(" + tilt + "deg)";
    el.innerHTML = '<div class="paper"><img src="' + d.img + '" alt="document"/>' +
      (d.label ? '<div class="label">' + d.label + '</div>' : '') +
      (d.poster ? '' : '<div class="stamp">' + SEAL + '</div>') + '</div>';
    docHost.appendChild(el);

    tl.set(el, {visibility:"visible"}, d.start);
    tl.fromTo(el,
      {opacity:0, y:44, scale:0.84, rotation:tilt + (idx % 2 ? 9 : -9)},
      {opacity:1, y:0, scale:1, rotation:tilt, duration:0.34, ease:"back.out(1.8)"},
      d.start);

    if (!d.poster) {
      var stamp = el.querySelector(".stamp");
      tl.fromTo(stamp, {scale:0, rotation:-18}, {scale:1, rotation:-8, duration:0.26, ease:"back.out(3)"}, d.start + 0.3);
    }

    tl.to(el, {opacity:0, y:-26, scale:0.94, duration:0.22, ease:"power2.in"}, d.end - 0.22);
    tl.set(el, {visibility:"hidden"}, d.end);
  });

  // Animated checklist overlays: the panel scales in, then each row ticks in
  // (green check pops + label slides) at its own resolved moment, and the whole
  // panel slips out before the window ends.
  var LISTS = __LISTS__;
  var listHost = document.getElementById("listHost");
  var CHK = '<svg viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.4 4.4L19 7" stroke="#0a2e17" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  LISTS.forEach(function(L){
    var card = document.createElement("div");
    card.className = "list-card";
    var inner = L.title ? '<div class="lc-title">' + L.title + '</div>' : '';
    L.items.forEach(function(it){
      inner += '<div class="lc-row"><span class="lc-check">' + CHK + '</span>' +
               '<span class="lc-label">' + it + '</span></div>';
    });
    card.innerHTML = inner;
    listHost.appendChild(card);

    tl.set(card, {visibility:"visible"}, L.start);
    tl.fromTo(card, {opacity:0, y:28, scale:0.92},
      {opacity:1, y:0, scale:1, duration:0.34, ease:"back.out(1.7)"}, L.start);

    var rows = card.querySelectorAll(".lc-row");
    L.times.forEach(function(t, i){
      var row = rows[i]; if (!row) return;
      var chk = row.querySelector(".lc-check");
      tl.fromTo(row, {opacity:0, x:-28}, {opacity:1, x:0, duration:0.26, ease:"power2.out"}, t);
      tl.fromTo(chk, {scale:0, rotation:-30}, {scale:1, rotation:0, duration:0.3, ease:"back.out(2.6)"}, t + 0.04);
    });

    tl.to(card, {opacity:0, y:-18, scale:0.96, duration:0.26, ease:"power2.in"}, L.end - 0.26);
    tl.set(card, {visibility:"hidden"}, L.end);
  });

  // Quick emphasis badges: an icon+text pill pops in (back-ease), floats gently,
  // then leaves. The icon inherits the badge's text colour (COL placeholder).
  var BADGES = __BADGES__;
  var badgeHost = document.getElementById("badgeHost");
  var BICONS = {
    check: '<svg viewBox="0 0 24 24" fill="none"><path d="M5 12.6l4.4 4.4L19 7" stroke="COL" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    star:  '<svg viewBox="0 0 24 24" fill="COL"><path d="M12 2l1.9 7.1L21 11l-7.1 1.9L12 20l-1.9-7.1L3 11l7.1-1.9z"/></svg>',
    brief: '<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="8" width="18" height="12" rx="2.4" fill="COL"/><path d="M8.5 8V6.4A2 2 0 0110.5 4.4h3A2 2 0 0115.5 6.4V8" stroke="COL" stroke-width="2.2"/></svg>',
    people: '<svg viewBox="0 0 24 24" fill="none"><circle cx="8" cy="8" r="3" fill="COL"/><circle cx="16" cy="8" r="3" fill="COL"/><path d="M2 20c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="COL" stroke-width="2" stroke-linecap="round"/><path d="M12 20c0-2.6 1.9-4.8 4.4-5.5" stroke="COL" stroke-width="2" stroke-linecap="round"/></svg>',
    flag: '<svg viewBox="0 0 24 24" fill="none"><path d="M6 21V3" stroke="COL" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 4h12l-3.4 4L18 12H6Z" fill="COL"/></svg>',
    medical: '<svg viewBox="0 0 24 24" fill="none"><path d="M5 3v5a3.5 3.5 0 0 0 7 0V3" stroke="COL" stroke-width="2" stroke-linecap="round"/><path d="M8.5 9.5v2.5a5.5 5.5 0 0 0 11 0v-2" stroke="COL" stroke-width="2" stroke-linecap="round"/><circle cx="19.5" cy="9.5" r="2.3" fill="COL"/><circle cx="5" cy="3" r="1.2" fill="COL"/><circle cx="12" cy="3" r="1.2" fill="COL"/></svg>'
  };
  // Seeded PRNG (mulberry32, adapted from the catalog's caption-particle-burst
  // component) -- NOT Math.random(): HyperFrames re-seeks/re-renders frames,
  // so any randomness in the timeline must reproduce identically every time.
  function mulberry32(seed){
    return function(){
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  BADGES.forEach(function(b, bi){
    var el = document.createElement("div");
    el.className = "badge-pop";
    el.style.background = b.bg; el.style.color = b.fg;
    if (b.left != null) el.style.left = b.left + "px";
    if (b.right != null) el.style.right = b.right + "px";
    if (b.center) el.style.left = "50%";
    el.style.top = b.top + "px";
    var ico = (BICONS[b.icon] || BICONS.star).replace(/COL/g, b.fg);
    el.innerHTML = '<span class="bp-ico">' + ico + '</span><span class="bp-txt">' + b.text + '</span>';
    badgeHost.appendChild(el);
    if (b.center) gsap.set(el, {xPercent:-50});

    tl.set(el, {visibility:"visible"}, b.start);
    if (b.effect === "pixelate") {
      // The cell-grid reveal below IS the entrance -- keep the pill itself
      // a plain fade so the two don't fight for attention.
      tl.fromTo(el, {opacity:0}, {opacity:1, duration:0.1}, b.start);
    } else {
      tl.fromTo(el, {opacity:0, scale:0.6, y:-16},
        {opacity:1, scale:1, y:0, duration:0.34, ease:"back.out(2.4)"}, b.start);
    }
    tl.to(el, {y:8, duration:0.9, ease:"sine.inOut", repeat:1, yoyo:true}, b.start + 0.4);
    tl.to(el, {opacity:0, scale:0.9, y:-14, duration:0.24, ease:"power2.in"}, b.end - 0.24);
    tl.set(el, {visibility:"hidden"}, b.end);

    if (b.effect === "shimmer") {
      var mask = document.createElement("div");
      mask.className = "bp-shimmer";
      el.appendChild(mask);
      gsap.set(el, {"--shimmer-pos": "-20%"});
      tl.fromTo(el, {"--shimmer-pos": "-20%"}, {"--shimmer-pos": "120%",
        duration: 0.7, ease: "power2.inOut"}, b.start + 0.34);
    } else if (b.effect === "particles") {
      var rng = mulberry32(bi * 137 + 99);
      var N = 10;
      for (var p = 0; p < N; p++) {
        var angle = (p / N) * Math.PI * 2 + rng() * 0.6;
        var dist = 46 + rng() * 40;
        var sz = 4 + rng() * 5;
        var dx = Math.cos(angle) * dist, dy = -Math.sin(angle) * dist;
        var dot = document.createElement("div");
        dot.className = "bp-particle";
        dot.style.width = sz.toFixed(1) + "px"; dot.style.height = sz.toFixed(1) + "px";
        dot.style.background = (p % 2 === 0) ? b.fg : "#fff";
        el.appendChild(dot);
        tl.set(dot, {x:0, y:0, opacity:0}, b.start);
        tl.to(dot, {x:dx, y:dy, opacity:1, duration:0.16, ease:"power3.out"}, b.start + 0.30 + p*0.012);
        tl.to(dot, {opacity:0, duration:0.35, ease:"power1.in"}, b.start + 0.46 + p*0.012);
      }
    } else if (b.effect === "pixelate") {
      var cols = 8, rows2 = 3;
      var overlay = document.createElement("div");
      overlay.className = "bp-pixel-overlay";
      overlay.style.gridTemplateColumns = "repeat(" + cols + ",1fr)";
      overlay.style.gridTemplateRows = "repeat(" + rows2 + ",1fr)";
      var cells = [];
      for (var c = 0; c < cols * rows2; c++) {
        var cell = document.createElement("div");
        cell.className = "bp-cell";
        cell.style.background = b.bg;
        overlay.appendChild(cell);
        cells.push(cell);
      }
      el.appendChild(overlay);
      tl.set(cells, {scale:1}, b.start);
      tl.to(cells, {scale:0, duration:0.36, stagger:{amount:0.3, from:"center"}, ease:"power2.in"}, b.start + 0.06);
      tl.set(cells, {display:"none"}, b.start + 0.42);
    }
  });

  // Full-screen hero-word slams: one giant centered word/phrase, punch-scale
  // entrance, brief hold, quick exit. The matching 2-word caption card was
  // already suppressed for this window (see _in_hero_window in Python).
  var HERO = __HERO_WORDS__;
  var heroHost = document.getElementById("heroHost");
  HERO.forEach(function(h){
    var el = document.createElement("div");
    el.className = "hero-slam";
    el.innerHTML = "<span>" + h.text + "</span>";
    heroHost.appendChild(el);
    tl.set(el, {visibility:"visible"}, h.start);
    tl.fromTo(el, {opacity:0, scale:0.5},
      {opacity:1, scale:1, duration:0.26, ease:"back.out(2.6)"}, h.start);
    tl.to(el, {opacity:0, scale:1.15, duration:0.2, ease:"power2.in"}, h.end - 0.2);
    tl.set(el, {visibility:"hidden"}, h.end);
  });

  // Tiny hook banner: on screen only for the first beat.
  var HB = __HOOK_BANNER__;
  if (HB && HB.text && HB.end > HB.start) {
    var hbEl = document.getElementById("hookBanner");
    hbEl.querySelector("span").textContent = HB.text;
    tl.set(hbEl, {visibility:"visible"}, HB.start);
    tl.fromTo(hbEl, {opacity:0, y:-16}, {opacity:1, y:0, duration:0.24, ease:"power2.out"}, HB.start);
    tl.to(hbEl, {opacity:0, y:-12, duration:0.2, ease:"power2.in"}, HB.end - 0.2);
    tl.set(hbEl, {visibility:"hidden"}, HB.end);
  }

  // Save/share prompt: a closing engagement beat.
  var SP = __SAVE_PROMPT__;
  if (SP && SP.text && SP.end > SP.start) {
    var spEl = document.getElementById("savePrompt");
    spEl.querySelector("span").textContent = SP.text;
    tl.set(spEl, {visibility:"visible"}, SP.start);
    tl.fromTo(spEl, {opacity:0, scale:0.85, y:16},
      {opacity:1, scale:1, y:0, duration:0.3, ease:"back.out(2)"}, SP.start);
    tl.to(spEl, {scale:1.05, duration:0.5, ease:"sine.inOut", repeat:1, yoyo:true}, SP.start + 0.4);
    tl.to(spEl, {opacity:0, y:-12, duration:0.2, ease:"power2.in"}, SP.end - 0.2);
    tl.set(spEl, {visibility:"hidden"}, SP.end);
  }

  __DECOR_JS__

  tl.seek(0);
  window.__timelines["main"]=tl;
})();
</script></body></html>
"""

if __name__ == "__main__":
    build(no_cache="--no-cache" in sys.argv, clear_cache="--clear-cache" in sys.argv)
