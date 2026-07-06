"""PFEC reel captions + overlay cards: 2-word UPPERCASE Poppins Bold chunks with
real kinetic motion (back-ease overshoot entrance, gold-keyword pulse), plus
overlay cards (top kicker for the seminar date, bottom red-pill CTA, and
optional document-highlight "paper card + stamp" cards -- e.g. a redacted
visa grant letter -- placed wherever the transcript's anchor_phrase resolves).

Architecture: render ONLY the graphics as a TRANSPARENT layer via HyperFrames
(fast -- Chrome never touches the footage), then ffmpeg-composite that overlay
onto base_broll.mp4 (one clean encode, footage/B-roll quality preserved)."""
import os, json, shutil, subprocess

from reel_paths import WORK, REEL, ASSETS_ROOT, hyperframes_cli  # noqa: E402 -- per-reel folders
from anchor_phrase import resolve_anchor  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

FILLERS = {"um", "uh", "erm", "er", "ah", "hmm", "mm", "mm-hmm", "mmhmm", "uh-huh"}
SENTENCE_END = (".", "?", "!")
MARA_BADGE_CROP = "1030:920:112:165"   # ffmpeg crop=w:h:x:y -> just the badge

# Per-reel content. DEFAULT_CONTENT reproduces the Lakemba reel exactly; any reel
# can override any key via <reel>/content.json (see load_content()). Card times
# are on the OUTPUT timeline (unaffected by B-roll splicing). The "info" card
# reuses a 3-beat top card (kicker / big line1 / smaller line2). MARA badge
# "mode": "image" = official mark PNG on the navy plate; "styled" = navy plate
# with "MARA REGISTERED" + "MARN <n>" text (used when there's no official mark).
DEFAULT_CONTENT = {
    "asr_fix": {"pfc": "PFEC", "pfpc": "PFEC", "ils": "IELTS"},
    "gold": ["VISA", "EOI", "IELTS", "PTE", "NAATI", "189", "POINTS", "PR",
             "RESIDENCY", "PERMANENT", "PATHWAY", "PATHWAYS", "MIGRATION",
             "SEMINAR", "PFEC", "ASSESSMENT", "INVITATION", "ROUND"],
    "name": {"text": "Niyama Tabassum", "role": "Education Counsellor",
             "start": 0.6, "end": 4.8},
    "mara": {"mode": "image",
             "src": os.path.join(ASSETS_ROOT, "marn designs", "Ali's MARN.png"),
             "marn": "2117037", "start": 0.5, "settle": 1.7, "end": 6.6},
    "info": {"kicker": "FREE MIGRATION SEMINAR", "line1": "13 JULY", "line1_size": 80,
             "line2": "Lakemba Senior Citizens' Centre", "start": 40.2, "end": 43.5},
    "cta": {"text": "REGISTER NOW!", "start": 48.75, "end": 50.75},
    # Document highlights (e.g. redacted visa grant letters): each entry names
    # an anchor_phrase (words as spoken, NOT a timecode) -- resolve_anchor()
    # locates it in the transcript. "image" is a filename under <reel>/documents/
    # (put the letter-redactor's REDACTED output there, never the raw original).
    "documents": [],   # e.g. [{"image": "grant1.png", "anchor_phrase": "his 189 grant came through", "label": "189 VISA GRANT"}]
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
    return c


def norm(t):
    return t.strip().strip(".,!?;:'\"").lower()


def crop_mara_badge(dest_dir, src):
    """Tight-crop the official MARA mark into <dest>/mara_badge.png (removes the
    white margin so it mounts cleanly on the navy plate)."""
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", src, "-vf", f"crop={MARA_BADGE_CROP}",
                    os.path.join(dest_dir, "mara_badge.png")], check=True)


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


_SEAL_SVG = ('<svg viewBox="0 0 24 24" fill="none"><path d="M12 2l7 3v6c0 4.4-3 8-7 9'
             '-4-1-7-4.6-7-9V5l7-3z" fill="#100796"/><path d="M8.4 12.2l2.5 2.5 4.7-5" '
             'stroke="#FFC500" stroke-width="2.5" stroke-linecap="round" '
             'stroke-linejoin="round"/></svg>')


def make_proj(base):
    """Generate the transparent captions/overlay HyperFrames project (cap_proj)
    for the given base video (used for its duration). No render — returns
    (proj_dir, n_cards). Split out so the layout can be live-previewed fast."""
    content = load_content()
    gold = set(g.upper() for g in content["gold"])
    words = load_words(content)
    chunks = chunk_2word(words)
    cards = []
    for k, g in enumerate(chunks):
        start = g[0]["start"]
        end = chunks[k + 1][0]["start"] if k + 1 < len(chunks) else g[-1]["end"] + 0.4
        spans = []
        for w in g:
            is_gold = norm(w["text"]).upper() in gold
            spans.append({"text": w["text"].strip().upper(), "gold": is_gold})
        cards.append({"start": round(start, 3), "end": round(max(start + 0.2, end), 3),
                      "words": spans})

    dur = float(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nokey=1", base], capture_output=True, text=True).stdout.strip())

    proj = os.path.join(WORK, "cap_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)

    mara = content["mara"]
    if mara["mode"] == "image":
        crop_mara_badge(proj, mara["src"])
        mara_class, mara_inner = "", (
            '<div class="plate"><img src="mara_badge.png" alt="MARA registration"/>'
            '<div class="shine"></div></div>')
    else:   # "styled": navy plate + MARA REGISTERED + MARN <n>, no name/artwork
        mara_class = "styled"
        mara_inner = (f'<div class="plate"><div class="seal">{_SEAL_SVG}</div>'
                      f'<div class="txt"><div class="kick">MARA Registered</div>'
                      f'<div class="marn">MARN&nbsp;<b>{mara["marn"]}</b></div></div>'
                      f'<div class="shine"></div></div>')

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
        start, end, score = resolve_anchor(words, spec["anchor_phrase"])
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
        docs.append({"img": dest_name, "label": spec.get("label", ""),
                     "start": start, "end": end})
        print(f"  [documents] '{spec['image']}' -> {start:.2f}s-{end:.2f}s "
              f"(anchor match {score:.2f})")

    nm, info, cta = content["name"], content["info"], content["cta"]
    html = (_CAP_BLOCK.replace("__DUR__", f"{dur:.3f}")
            .replace("__CARDS__", json.dumps(cards))
            .replace("__DOCS__", json.dumps(docs))
            .replace("__DATE_START__", str(info["start"]))
            .replace("__DATE_END__", str(info["end"]))
            .replace("__INFO_KICKER__", info["kicker"])
            .replace("__INFO_LINE1__", info["line1"])
            .replace("__INFO_L1_SIZE__", str(info.get("line1_size", 80)))
            .replace("__INFO_LINE2__", info["line2"])
            .replace("__CTA_START__", str(cta["start"]))
            .replace("__CTA_END__", str(cta["end"]))
            .replace("__CTA_TEXT__", cta["text"])
            .replace("__NAME_START__", str(nm["start"]))
            .replace("__NAME_END__", str(nm["end"]))
            .replace("__NAME_TEXT__", nm["text"])
            .replace("__NAME_ROLE__", nm["role"])
            .replace("__MARA_START__", str(mara["start"]))
            .replace("__MARA_SETTLE__", str(mara["settle"]))
            .replace("__MARA_END__", str(mara["end"]))
            .replace("__MARA_CLASS__", mara_class)
            .replace("__MARA_INNER__", mara_inner))
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(html)
    json.dump({"id": "pfec-captions", "name": "PFEC captions + overlays"},
              open(os.path.join(proj, "meta.json"), "w"))
    return proj, len(cards)


def build():
    base = os.path.join(WORK, "base_broll.mp4")
    proj, n_cards = make_proj(base)

    overlay = os.path.join(WORK, "captions_overlay.webm")
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    print(f"rendering {n_cards} caption cards + overlay cards (transparent)...")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(overlay),
                    "-f", "30", "--format", "webm", "-q", "standard", "--quiet"],
                   cwd=proj, check=True, env=env)

    # CRITICAL: force libvpx-vp9 decode -- ffmpeg's default vp9 decoder drops the
    # alpha plane (reports yuv420p) and would paint opaque black over the footage.
    out = os.path.join(WORK, "captioned.mp4")
    color_tags = ["-color_primaries", "bt709", "-color_trc", "bt709",
                 "-colorspace", "bt709", "-color_range", "tv"]
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", base,
                    "-c:v", "libvpx-vp9", "-i", overlay,
                    "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
                    "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "18", *color_tags, "-c:a", "copy",
                    "-video_track_timescale", "90000", out],
                   check=True)
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
  #cap{position:absolute;left:0;right:0;top:62%;transform:translateY(-50%);text-align:center}
  .card{position:absolute;left:0;right:0;top:0;padding:0 70px;opacity:0;visibility:hidden}
  .w{font-family:"Poppins",sans-serif;font-weight:800;font-size:96px;line-height:1.05;color:#fff;
     letter-spacing:.01em;text-shadow:0 6px 22px rgba(0,0,0,.75),0 2px 4px rgba(0,0,0,.95);
     display:inline-block;margin:0 26px}
  .w.gold{color:#FFC500}

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

  /* Overlay card: CTA red pill (bottom, y ~1420 per spec) */
  #ctaCard{position:absolute;left:0;right:0;top:1420px;text-align:center;opacity:0;visibility:hidden}
  #ctaCard .pill{display:inline-block;background:#E84B37;color:#fff;font-family:"Poppins",sans-serif;
     font-weight:800;font-size:42px;letter-spacing:.03em;padding:26px 56px;border-radius:999px;
     box-shadow:0 14px 34px rgba(0,0,0,.4)}

  /* Confetti burst: fires once when the CTA lands, for a "fun" celebratory beat */
  #confetti{position:absolute;left:50%;top:1462px;width:0;height:0}
  #confetti .p{position:absolute;left:0;top:0;width:16px;height:16px;border-radius:3px;opacity:0}

  /* Speaker intro lower-third: navy plate + gold accent bar (brand colours),
     bottom-left, on screen only for the opening seconds (never overlaps the
     bottom CTA slot -- that card runs much later) */
  #nameCard{position:absolute;left:60px;top:1555px;opacity:0;visibility:hidden;text-align:left}
  #nameCard .plate{display:inline-block;background:#100796;border-left:12px solid #FFC500;
     border-radius:14px;padding:20px 36px 18px 28px;box-shadow:0 14px 34px rgba(0,0,0,.45)}
  #nameCard .nm{font-family:"Poppins",sans-serif;font-weight:800;font-size:44px;color:#fff;
     letter-spacing:.01em;line-height:1.1}
  #nameCard .role{font-family:"Poppins",sans-serif;font-weight:700;font-size:25px;color:#FFC500;
     letter-spacing:.09em;text-transform:uppercase;margin-top:6px}

  /* MARA credential badge: the OFFICIAL MARA registration mark mounted on a
     brand-navy plate (blue kept per user; the mark carries the MARN + govt
     branding, no personal name). Base position = resting spot under the logo;
     the hero entrance animates it up FROM screen-centre via GSAP so it's
     noticed before it docks. */
  #maraCard{position:absolute;left:50%;top:250px;opacity:0;visibility:hidden}
  #maraCard .plate{position:relative;overflow:hidden;border-radius:22px;
     background:linear-gradient(135deg,#100796,#1A10C0);border:3px solid #FFC500;
     padding:16px;box-shadow:0 16px 42px rgba(0,0,0,.55)}
  #maraCard img{display:block;width:320px;height:auto;border-radius:10px}
  #maraCard .shine{position:absolute;top:-40%;left:-60%;width:36%;height:180%;pointer-events:none;
     background:linear-gradient(75deg,transparent,rgba(255,255,255,.42),transparent);transform:skewX(-20deg)}
  /* styled MARA badge (navy plate + MARA REGISTERED + MARN text, no artwork) */
  #maraCard.styled .plate{display:flex;align-items:center;gap:20px;padding:18px 32px 18px 20px}
  #maraCard .seal{flex:none;width:84px;height:84px;border-radius:50%;
     background:radial-gradient(circle at 38% 32%,#FFE985,#FFC500 58%,#E0A400);
     display:flex;align-items:center;justify-content:center;box-shadow:0 5px 16px rgba(0,0,0,.45)}
  #maraCard .seal svg{width:46px;height:46px}
  #maraCard .txt{text-align:left;line-height:1}
  #maraCard .kick{font-family:"Poppins",sans-serif;font-weight:800;font-size:24px;letter-spacing:.16em;
     color:#FFC500;text-transform:uppercase;margin-bottom:8px}
  #maraCard .marn{font-family:"Poppins",sans-serif;font-weight:800;font-size:52px;color:#fff;letter-spacing:.02em}
  #maraCard .marn b{color:#FFC500}

  /* Document highlight: redacted letter shown as a "paper card + stamp" --
     never a raw full-bleed photo -- landing in the upper zone so it never
     collides with the caption band (top 62%) or the bottom CTA slot (1420px). */
  .doc-card{position:absolute;left:50%;top:300px;width:640px;margin-left:-320px;
     opacity:0;visibility:hidden}
  /* fan-group variant: smaller, docked top-left so it never covers the
     speaker's face -- x/y offsets are applied per-card via GSAP (see script). */
  .doc-card.fan{left:36px;top:250px;width:340px;margin-left:0}
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
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="__DUR__" data-fps="30" data-width="1080" data-height="1920">
  <div id="cap"></div>
  <div id="dateCard">
    <div class="kickerWrap"><div class="kicker">__INFO_KICKER__<div class="shine"></div></div></div>
    <br>
    <div class="dateWrap"><div class="dateBlock"></div><div class="date">__INFO_LINE1__</div></div>
    <br>
    <div class="venueWrap"><div class="venueBlock"></div><div class="venue">__INFO_LINE2__</div></div>
  </div>
  <div id="ctaCard"><div class="pill">__CTA_TEXT__</div></div>
  <div id="nameCard"><div class="plate"><div class="nm">__NAME_TEXT__</div><div class="role">__NAME_ROLE__</div></div></div>
  <div id="maraCard" class="__MARA_CLASS__">__MARA_INNER__</div>
  <div id="confetti"></div>
  <div id="docHost"></div>
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

  // Overlay card 2: CTA red pill (bottom placement, per spec text-only)
  var cc = document.getElementById("ctaCard");
  tl.set(cc,{visibility:"visible"}, __CTA_START__);
  tl.fromTo(cc, {opacity:0, y:30, scale:0.85}, {opacity:1, y:0, scale:1, duration:0.32, ease:"back.out(2)"}, __CTA_START__);
  tl.to(cc.querySelector(".pill"), {scale:1.04, duration:0.5, ease:"sine.inOut", repeat:3, yoyo:true}, __CTA_START__+0.4);
  tl.to(cc, {opacity:0, y:18, duration:0.2, ease:"power2.in"}, __CTA_END__-0.2);
  tl.set(cc, {visibility:"hidden"}, __CTA_END__);

  // Speaker intro lower-third: slides in from the left with the house back-ease,
  // holds through the opening beat, slips back out.
  var nc = document.getElementById("nameCard");
  var NS = __NAME_START__, NE = __NAME_END__;
  if (NE > NS) {
    tl.set(nc,{visibility:"visible"}, NS);
    tl.fromTo(nc, {opacity:0, x:-46}, {opacity:1, x:0, duration:0.32, ease:"back.out(1.8)"}, NS);
    tl.to(nc, {opacity:0, x:-30, duration:0.25, ease:"power2.in"}, Math.max(NS+0.4, NE-0.25));
    tl.set(nc,{visibility:"hidden"}, NE);
  }

  // MARA credential badge: hero entrance -- pops in at screen-centre (large),
  // holds with a gold shimmer sweep to draw the eye, then flies up and docks
  // under the logo. xPercent keeps it horizontally centred through the scale.
  var mc = document.getElementById("maraCard");
  var MS = __MARA_START__, MSET = __MARA_SETTLE__, ME = __MARA_END__;
  gsap.set(mc, {xPercent:-50});
  tl.set(mc, {visibility:"visible"}, MS);
  tl.fromTo(mc, {opacity:0, y:470, scale:1.32, rotation:-5},
                {opacity:1, y:470, scale:1.32, rotation:0, duration:0.4, ease:"back.out(1.9)"}, MS);
  tl.fromTo(mc.querySelector(".shine"), {xPercent:-140}, {xPercent:320, duration:0.6, ease:"power1.inOut"}, MS+0.5);
  tl.to(mc, {y:0, scale:1, duration:0.5, ease:"power3.inOut"}, MSET);
  tl.to(mc, {opacity:0, y:-30, duration:0.28, ease:"power2.in"}, ME-0.28);
  tl.set(mc, {visibility:"hidden"}, ME);

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

    var tilt = idx % 2 ? 2.2 : -2.2;
    var el = document.createElement("div");
    el.className = "doc-card";
    el.style.transform = "rotate(" + tilt + "deg)";
    el.innerHTML = '<div class="paper"><img src="' + d.img + '" alt="document"/>' +
      (d.label ? '<div class="label">' + d.label + '</div>' : '') +
      '<div class="stamp">' + SEAL + '</div></div>';
    docHost.appendChild(el);

    tl.set(el, {visibility:"visible"}, d.start);
    tl.fromTo(el,
      {opacity:0, y:44, scale:0.84, rotation:tilt + (idx % 2 ? 9 : -9)},
      {opacity:1, y:0, scale:1, rotation:tilt, duration:0.34, ease:"back.out(1.8)"},
      d.start);

    var stamp = el.querySelector(".stamp");
    tl.fromTo(stamp, {scale:0, rotation:-18}, {scale:1, rotation:-8, duration:0.26, ease:"back.out(3)"}, d.start + 0.3);

    tl.to(el, {opacity:0, y:-26, scale:0.94, duration:0.22, ease:"power2.in"}, d.end - 0.22);
    tl.set(el, {visibility:"hidden"}, d.end);
  });

  tl.seek(0);
  window.__timelines["main"]=tl;
})();
</script></body></html>
"""

if __name__ == "__main__":
    build()
