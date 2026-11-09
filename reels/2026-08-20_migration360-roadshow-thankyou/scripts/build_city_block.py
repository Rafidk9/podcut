"""Reusable per-city block generator for the Migration 360 Roadshow thank-you
reel. Grew out of work/build_style_frame.py (the approved Perth style
checkpoint) -- same 3-zone 1080x1920 composition (logo+passport-stamp top,
blur-extend media zone middle, progress-dot row bottom), now parameterized so
Perth/Adelaide/Brisbane/Melbourne/Hobart+Launceston can all be built by
calling one function instead of 5 people hand-copying the HTML.

Public interface:

    build_city_block(
        city_name,           # str, or [str, str] when is_double_stamp=True
        stamp_color,          # "#RRGGBB" ink colour for this block's stamp
        media_items,          # list of item dicts, see MEDIA ITEM SCHEMA below
        stamp_index,           # 1-based position of this block, e.g. 1 for Perth
        total_stamps=5,        # total blocks in the series (5: Perth, Adelaide,
                                # Brisbane, Melbourne, Hobart&Launceston-combined)
        is_double_stamp=False, # True for the combined Hobart+Launceston block
        output_path=None,      # defaults to work/segment_<slug>.mp4
        fps=30,
        quality="standard",
    ) -> str                   # absolute path to the rendered mp4

MEDIA ITEM SCHEMA (each dict in media_items, shown in sequence, ~2-3s each):

    {
      "type": "video" | "photo",
      "path": "input/perth/IMG_7233.MOV",   # relative to the reel root, or absolute
      "duration": 2.6,                        # seconds shown ON SCREEN in the
                                               # final composite (see "speed" below)
      "trim_start": 1.0,                      # video only: seconds into the source to start
      "speed": 3.5,                            # video only, optional: fast-forward
                                               # factor. When present, ffmpeg speeds
                                               # the clip up by this factor
                                               # (setpts=PTS/speed) so `duration`
                                               # seconds of screen time visually
                                               # covers `duration * speed` seconds of
                                               # real source footage (read from
                                               # trim_start onward -- make sure the
                                               # source has that much runway left).
                                               # Video audio is always dropped
                                               # regardless of speed (B-roll under
                                               # the music bed -- see _prepare_video_asset),
                                               # so there is nothing extra to mute.
                                               # Omit for normal real-time playback
                                               # (unchanged, backward-compatible
                                               # behaviour). Use a factor that reads
                                               # clearly as an intentional "fast
                                               # forward" beat -- 3-4x is a good
                                               # starting point; much less just looks
                                               # like a slightly fast pan.
      "orientation": "portrait" | "landscape",# optional; auto-looked-up from
                                               # work/media_inventory.json by path,
                                               # falls back to probing the file directly
      "badge": "ATTENDEE FEEDBACK",            # optional: small brand-coloured
                                               # pill/tag overlaid low in the
                                               # zone for this item's own
                                               # window only (fades with the
                                               # item) -- use to mark a clip
                                               # as testimonial/review content
                                               # so it doesn't read as plain
                                               # generic footage. Not
                                               # supported on "polaroid"
                                               # treatment items. See _emit_badge.
      "treatment": "blur_extend" | "polaroid",# optional, photos only; default
                                               # "blur_extend" (existing behaviour,
                                               # below). "polaroid" is for source
                                               # photos too compressed/soft to sell
                                               # as full-bleed hero footage (e.g.
                                               # WhatsApp-compressed originals) --
                                               # renders a white-bordered, drop-
                                               # shadowed snapshot card sized to
                                               # ~78% of the zone width with a
                                               # warm-tint + grain grade, so the
                                               # softness reads as a deliberate
                                               # "snapshot" aesthetic instead of a
                                               # mistake. See _emit_polaroid_item.
    }

Landscape sources (photo or video) get the blur-extend treatment: an
overscanned+blurred cover background, a tint pass, and a fully-visible
letterboxed ("object-fit: contain") sharp layer on top -- matches the
approved Perth style checkpoint. Portrait sources fill the zone edge-to-edge
with object-fit: cover. Photos get a slow Ken Burns push (scale 1.0 -> ~1.08
over their duration); video plays straight (no added zoom) off a short trim
of the source. All media items are hard-cut back to back (no cross-fade
overlap -- keeps clip timing non-overlapping and deterministic); each item
fades its own layers' opacity in/out at the very start/end of ITS OWN window
for a soft edge on the cut without needing overlapping tracks.

Every layer of a media item is emitted as its own flat, untitled DIRECT CHILD
of the composition root (never nested inside a wrapper div) -- both because
HyperFrames only honors class="clip" timing on direct children of the root,
and because <video> must never be nested inside a timed wrapper. A
landscape blur layer instead self-contains its filter bleed with
`clip-path: inset(...)` sized to the zone bounds, so no clipping ancestor is
needed.
"""
import base64
import json
import os
import shutil
import subprocess
import sys

_THIS = os.path.abspath(__file__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(_THIS))))  # reels/
from reel_paths import WORK, REEL, ASSETS_ROOT, hyperframes_cli  # noqa: E402

LOGO_SVG = os.path.join(ASSETS_ROOT, "logo", "pfec-logo-white.svg")
FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

ZONE_TOP = 380
ZONE_H = 1100
ZONE_W = 1080
OVERSCAN = 80  # px of blur-layer overscan on each side, for the blur-extend treatment

_INVENTORY_CACHE = None


def _load_inventory():
    global _INVENTORY_CACHE
    if _INVENTORY_CACHE is None:
        inv_path = os.path.join(WORK, "media_inventory.json")
        _INVENTORY_CACHE = {}
        if os.path.isfile(inv_path):
            data = json.load(open(inv_path, encoding="utf-8"))
            for entry in data.get("photos", []) + data.get("videos", []):
                key = entry["path"].replace("\\", "/")
                _INVENTORY_CACHE[key] = entry
    return _INVENTORY_CACHE


def _resolve_path(p):
    return p if os.path.isabs(p) else os.path.join(REEL, p)


def _orientation_for(rel_or_abs_path, explicit=None):
    if explicit:
        return explicit
    key = rel_or_abs_path.replace("\\", "/")
    reel_key = REEL.replace("\\", "/")
    if key.startswith(reel_key + "/"):
        key = key[len(reel_key) + 1:]
    inv = _load_inventory()
    entry = inv.get(key)
    if entry:
        return entry.get("effective_orientation") or entry.get("orientation")
    # Fallback: probe the file directly (no inventory entry).
    abs_path = _resolve_path(rel_or_abs_path)
    ext = os.path.splitext(abs_path)[1].lower()
    if ext in (".mp4", ".mov", ".m4v"):
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0", abs_path],
            capture_output=True, text=True)
        w, h = (int(x) for x in out.stdout.strip().rstrip(",").split(",")[:2])
        print(f"[build_city_block] WARNING: {rel_or_abs_path!r} not in "
              f"media_inventory.json -- probed raw {w}x{h} (rotation metadata "
              f"not accounted for; pass orientation= explicitly if this is wrong)")
        return "portrait" if h > w else "landscape"
    from PIL import Image
    w, h = Image.open(abs_path).size
    return "portrait" if h > w else "landscape"


def _data_uri(path, mime):
    with open(path, "rb") as f:
        b = f.read()
    return f"data:{mime};base64,{base64.b64encode(b).decode()}"


def _photo_mime(path):
    ext = os.path.splitext(path)[1].lower()
    return "image/png" if ext == ".png" else "image/jpeg"


_GRAIN_URI_CACHE = None


def _grain_uri():
    """A small tileable monochrome-noise PNG, embedded once and reused (via
    background-image + mix-blend-mode:overlay) to give the polaroid
    treatment a light film-grain texture. Fixed seed -> deterministic
    output, safe to cache module-wide across every polaroid item/render."""
    global _GRAIN_URI_CACHE
    if _GRAIN_URI_CACHE is None:
        import io
        import random
        from PIL import Image as _Image
        rng = random.Random(1337)
        size = 200
        im = _Image.new("L", (size, size))
        im.putdata([rng.randint(90, 170) for _ in range(size * size)])
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        _GRAIN_URI_CACHE = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    return _GRAIN_URI_CACHE


def _prepare_video_asset(src_abs, trim_start, duration, media_dir, item_id, speed=None):
    """Cuts+encodes the on-disk clip an <video> element will point at. With no
    `speed`, behaviour is unchanged: read exactly `duration` seconds of source
    from trim_start, real-time. With `speed`, this is a fast-forward/time-lapse
    beat: read `duration * speed` seconds of source (so the source needs that
    much runway past trim_start) and compress it into `duration` seconds of
    output via setpts=PTS/speed -- the emitted <video> still just plays this
    file straight through at its native rate, so no other timing code needs to
    know a speed-up happened. Audio is always dropped (-an) either way -- these
    are B-roll clips under the music bed, never dialogue."""
    os.makedirs(media_dir, exist_ok=True)
    out = os.path.join(media_dir, f"{item_id}.mp4")
    if speed and speed != 1:
        source_span = duration * speed
        vf = f"scale=1080:-2:flags=lanczos,setpts=PTS/{speed}"
    else:
        source_span = duration
        vf = "scale=1080:-2:flags=lanczos"
    subprocess.run(
        [FF, "-y", "-ss", str(trim_start), "-i", src_abs, "-t", str(source_span),
         "-vf", vf, "-an",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
        check=True, capture_output=True, text=True)
    return f"media/{item_id}.mp4"


FADE = 0.15  # seconds, opacity fade at the start/end of each item's own window

# "badge" pill overlay (see MEDIA ITEM SCHEMA "badge" key below) -- small
# lower-third caption tag that reads as e.g. "ATTENDEE FEEDBACK" over a
# testimonial clip. Positioned low in the zone (well clear of a seated/
# standing speaker's face in the reviewed footage) and above the zone's
# bottom edge, so it never collides with the progress-dot row that starts
# well below the zone (see #progressRow in build_city_block()).
BADGE_TOP = 1300
BADGE_FONT_SIZE = 24  # matches #progressLabel's scale for a consistent small-caption look


def _emit_badge(cls, start, dur, text, color):
    """Small pill/tag overlay: dark translucent pill, brand-colour border,
    white uppercase text -- reuses the same fade-in/out envelope as the
    media item it rides on. Emitted as its own flat top-level clip (never
    nested), per this module's timing contract."""
    badge_cls = f"{cls}-badge"
    html = (
        f'<div class="clip {badge_cls}" data-start="{start:.3f}" data-duration="{dur:.3f}" '
        f'data-track-index="9" style="position:absolute;left:50%;top:{BADGE_TOP}px;'
        f'transform:translateX(-50%);padding:13px 28px;border-radius:999px;'
        f'background:rgba(5,3,24,.7);border:2px solid {color};'
        f'box-shadow:0 10px 26px rgba(0,0,0,.4);white-space:nowrap;">'
        f'<span style="font-family:\'Poppins\',sans-serif;font-weight:800;'
        f'font-size:{BADGE_FONT_SIZE}px;letter-spacing:.16em;color:#FFFFFF;">{text}</span>'
        f'</div>'
    )
    js = [
        f'tl.fromTo(".{badge_cls}",{{opacity:0,y:12}},{{opacity:1,y:0,duration:{FADE}}},{start:.3f});',
        f'tl.to(".{badge_cls}",{{opacity:0,duration:{FADE}}},{max(start + dur - FADE, start):.3f});',
    ]
    return html, js


_POLAROID_ROTATIONS = [-3, 2.4, -2, 3, -2.6]  # cycled by idx, organic scrapbook-style tilt

CARD_WIDTH_FRAC = 0.78  # of ZONE_W -- reads as a deliberate snapshot, not full-bleed


def _emit_polaroid_item(item, idx, start, rotate_deg=None):
    """Photo-only treatment for source images too soft/compressed to sell as
    full-bleed hero footage: a white-card, drop-shadowed polaroid sized to
    CARD_WIDTH_FRAC of the zone width, warm-tint + grain graded, gently
    tilted. Single flat clip div (direct child of root, per the module's
    timing contract) with only plain nested children -- no <video>, so
    nesting is safe here (see module docstring)."""
    from PIL import Image as _Image
    cls = f"item{idx}"
    dur = item["duration"]
    photo_abs = _resolve_path(item["path"])
    uri = _data_uri(photo_abs, _photo_mime(photo_abs))
    with _Image.open(photo_abs) as im:
        sw, sh = im.size

    if rotate_deg is None:
        rotate_deg = _POLAROID_ROTATIONS[idx % len(_POLAROID_ROTATIONS)]

    border_side = 26
    border_bottom = 108
    card_w = int(ZONE_W * CARD_WIDTH_FRAC)
    photo_w = card_w - 2 * border_side
    photo_h = int(photo_w * sh / sw)
    card_h = photo_h + border_side + border_bottom
    card_left = (ZONE_W - card_w) // 2
    card_top = ZONE_TOP + (ZONE_H - card_h) // 2

    html = (
        f'<div id="{cls}-card" class="clip {cls}" data-start="{start:.3f}" data-duration="{dur:.3f}" '
        f'data-track-index="1" style="position:absolute;left:{card_left}px;top:{card_top}px;'
        f'width:{card_w}px;height:{card_h}px;transform:rotate({rotate_deg}deg);'
        f'filter:drop-shadow(0 26px 46px rgba(0,0,0,.5)) drop-shadow(0 4px 12px rgba(0,0,0,.4));">'
        f'<div style="position:absolute;inset:0;background:#F7F3E9;border-radius:3px;"></div>'
        f'<div style="position:absolute;left:{border_side}px;top:{border_side}px;'
        f'width:{photo_w}px;height:{photo_h}px;overflow:hidden;box-shadow:inset 0 0 0 1px rgba(0,0,0,.08)">'
        f'<img id="{cls}-img" class="kb-{cls}" src="{uri}" style="width:100%;height:100%;'
        f'object-fit:cover;filter:sepia(.18) saturate(1.14) contrast(1.04) brightness(1.03)"/>'
        f'<div style="position:absolute;inset:0;background-image:url(\'{_grain_uri()}\');'
        f'background-size:170px 170px;mix-blend-mode:overlay;opacity:.17;pointer-events:none"></div>'
        f'<div style="position:absolute;inset:0;box-shadow:inset 0 0 46px rgba(0,0,0,.14);pointer-events:none"></div>'
        f'</div></div>'
    )
    js = [
        f'tl.fromTo(".{cls}",{{opacity:0}},{{opacity:1,duration:{FADE}}},{start:.3f});',
        f'tl.to(".{cls}",{{opacity:0,duration:{FADE}}},{max(start + dur - FADE, start):.3f});',
        f'tl.fromTo(".kb-{cls}",{{scale:1.0}},{{scale:1.06,duration:{dur:.3f},ease:"none"}},{start:.3f});',
    ]
    return html, js


def _emit_media_item(item, idx, start, media_dir, badge_color=None):
    """Returns (html_str, js_lines) for one media item at global time `start`.
    Every element emitted here is a flat, top-level sibling -- never nested
    inside another timed wrapper. Every clip/video/img carries its own
    unique id (required: duplicate video/img ids render blank -- the
    producer injects frames via getElementById)."""
    if item.get("treatment") == "polaroid":
        assert item["type"] == "photo", "polaroid treatment is photo-only"
        return _emit_polaroid_item(item, idx, start)

    dur = item["duration"]
    orientation = _orientation_for(item["path"], item.get("orientation"))
    cls = f"item{idx}"
    els = []
    js = [f'tl.fromTo(".{cls}",{{opacity:0}},{{opacity:1,duration:{FADE}}},{start:.3f});',
          f'tl.to(".{cls}",{{opacity:0,duration:{FADE}}},{max(start + dur - FADE, start):.3f});']

    def clip_div(id_suffix, inner_html, track, extra_style=""):
        # overflow:hidden guards against a Ken Burns scale (or any transform)
        # on inner content bleeding past this layer's own zone-box bounds
        # into the stamp/progress zones above/below.
        els.append(
            f'<div id="{cls}-{id_suffix}" class="clip {cls}" data-start="{start:.3f}" data-duration="{dur:.3f}" '
            f'data-track-index="{track}" style="position:absolute;left:0;top:{ZONE_TOP}px;'
            f'width:{ZONE_W}px;height:{ZONE_H}px;overflow:hidden;{extra_style}">{inner_html}</div>')

    def video_el(id_suffix, rel_src, track, style):
        els.append(
            f'<video id="{cls}-{id_suffix}" class="{cls}" src="{rel_src}" muted playsinline '
            f'data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="{track}" '
            f'style="{style}"></video>')

    if item["type"] == "video":
        src_abs = _resolve_path(item["path"])
        trim_start = item.get("trim_start", 0)
        speed = item.get("speed")
        rel_src = _prepare_video_asset(src_abs, trim_start, dur, media_dir, cls, speed=speed)
        if orientation == "landscape":
            # Blur bg: overscanned box, self-clipped to the zone via clip-path
            # (a filter's blur bleed is not contained by the element's own
            # box, and there is no clipping ancestor here -- see module docstring).
            video_el("blur", rel_src, 1,
                     f"position:absolute;left:{-OVERSCAN}px;top:{ZONE_TOP-OVERSCAN}px;"
                     f"width:{ZONE_W+2*OVERSCAN}px;height:{ZONE_H+2*OVERSCAN}px;object-fit:cover;"
                     f"filter:blur(34px) saturate(1.25) brightness(1.02);"
                     f"clip-path:inset({OVERSCAN}px)")
            clip_div("tint", '', 2, "background:linear-gradient(180deg,rgba(10,7,48,.18),"
                                     "rgba(5,3,24,.05) 22%,rgba(5,3,24,.05) 78%,rgba(10,7,48,.22))")
            video_el("sharp", rel_src, 3,
                     f"position:absolute;left:0px;top:{ZONE_TOP}px;width:{ZONE_W}px;"
                     f"height:{ZONE_H}px;object-fit:contain;box-shadow:0 30px 90px rgba(0,0,0,.55)")
            clip_div("edgeTop", '', 4, "height:36px;background:linear-gradient(180deg,#050318,transparent)")
            clip_div("edgeBot", '', 5, f"top:{ZONE_TOP+ZONE_H-36}px;height:36px;"
                                        f"background:linear-gradient(0deg,#050318,transparent)")
        else:
            video_el("v", rel_src, 1,
                     f"position:absolute;left:0px;top:{ZONE_TOP}px;width:{ZONE_W}px;"
                     f"height:{ZONE_H}px;object-fit:cover")
    else:  # photo
        photo_abs = _resolve_path(item["path"])
        uri = _data_uri(photo_abs, _photo_mime(photo_abs))
        if orientation == "landscape":
            clip_div("blur", '', 1, f"left:{-OVERSCAN}px;top:{ZONE_TOP-OVERSCAN}px;"
                                     f"width:{ZONE_W+2*OVERSCAN}px;height:{ZONE_H+2*OVERSCAN}px;"
                                     f"background-image:url('{uri}');background-size:cover;background-position:center;"
                                     f"filter:blur(34px) saturate(1.25) brightness(1.02);"
                                     f"clip-path:inset({OVERSCAN}px)")
            clip_div("tint", '', 2, "background:linear-gradient(180deg,rgba(10,7,48,.18),"
                                     "rgba(5,3,24,.05) 22%,rgba(5,3,24,.05) 78%,rgba(10,7,48,.22))")
            clip_div("sharp", f'<img id="{cls}-img" class="kb-{cls}" src="{uri}" '
                              f'style="width:100%;height:100%;object-fit:contain;'
                              f'box-shadow:0 30px 90px rgba(0,0,0,.55)"/>', 3)
            clip_div("edgeTop", '', 4, "height:36px;background:linear-gradient(180deg,#050318,transparent)")
            clip_div("edgeBot", '', 5, f"top:{ZONE_TOP+ZONE_H-36}px;height:36px;"
                                        f"background:linear-gradient(0deg,#050318,transparent)")
            js.append(f'tl.fromTo(".kb-{cls}",{{scale:1.0}},{{scale:1.08,duration:{dur:.3f},ease:"none"}},{start:.3f});')
        else:
            clip_div("sharp", f'<img id="{cls}-img" class="kb-{cls}" src="{uri}" '
                              f'style="width:100%;height:100%;object-fit:cover"/>', 1)
            js.append(f'tl.fromTo(".kb-{cls}",{{scale:1.0}},{{scale:1.08,duration:{dur:.3f},ease:"none"}},{start:.3f});')

    if item.get("badge"):
        b_html, b_js = _emit_badge(cls, start, dur, item["badge"], badge_color or "#FFFFFF")
        els.append(b_html)
        js.extend(b_js)

    return "\n".join(els), js


def _stamp_block(name, color, cx, size, rotate_deg, landing_delay, stamp_uid):
    """One passport-stamp circle (ring + arc city text + plane glyph + footer)
    centered at horizontal offset cx, given size (px, square), with its own
    landing-overshoot animation starting at landing_delay (seconds)."""
    half = size / 2
    arc_r = size * 0.36
    arc_font = max(18, int(size * 0.117))
    plane_size = size * 0.247
    footer_font = max(11, int(size * 0.05))
    html = f'''
  <div id="{stamp_uid}" style="position:absolute;left:{cx}px;top:215px;width:{size}px;height:{size}px;
       transform:translate(-50%,-50%) rotate({rotate_deg}deg) scale(0.001);">
    <div style="position:absolute;inset:0;border-radius:50%;filter:url(#inkbleed-{stamp_uid});">
      <div style="position:absolute;inset:0;border-radius:50%;border:{max(4,int(size*0.023))}px solid {color};box-shadow:inset 0 0 0 {max(2,int(size*0.01))}px {color};opacity:.92"></div>
      <div style="position:absolute;inset:{int(size*0.073)}px;border-radius:50%;border:{max(2,int(size*0.01))}px solid {color};opacity:.55"></div>
    </div>
    <svg width="0" height="0"><filter id="inkbleed-{stamp_uid}" x="-60%" y="-60%" width="220%" height="220%">
      <feTurbulence type="fractalNoise" baseFrequency="0.018 0.03" numOctaves="3" seed="7" result="noise"/>
      <feDisplacementMap in="SourceGraphic" in2="noise" scale="{size*0.047}" xChannelSelector="R" yChannelSelector="G"/>
    </filter></svg>
    <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="position:absolute;inset:0">
      <path id="arcPath-{stamp_uid}" d="M {half-arc_r} {half+0.55*arc_r} A {arc_r} {arc_r} 0 0 1 {half+arc_r} {half+0.55*arc_r}" fill="none"/>
      <text style="font-family:'Poppins',sans-serif;font-weight:900;font-size:{arc_font}px;letter-spacing:.14em;fill:{color}">
        <textPath href="#arcPath-{stamp_uid}" startOffset="50%" text-anchor="middle">{name}</textPath>
      </text>
    </svg>
    <svg viewBox="0 0 24 24" fill="{color}" style="position:absolute;left:50%;top:50%;width:{plane_size}px;height:{plane_size}px;transform:translate(-50%,-50%) rotate(45deg)">
      <path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2.5 1.5V22l4-1 4 1v-1.5L13.5 19v-5.5z"/>
    </svg>
    <div style="position:absolute;left:50%;bottom:{int(size*0.127)}px;transform:translateX(-50%);
         font-family:'Poppins',sans-serif;font-weight:800;font-size:{footer_font}px;letter-spacing:.22em;color:{color};opacity:.92;white-space:nowrap">PFEC GLOBAL</div>
  </div>'''
    js = [
        f'tl.to("#{stamp_uid}",{{scale:1.10,duration:0.24,ease:"power2.out"}},{landing_delay+0.06:.3f});',
        f'tl.to("#{stamp_uid}",{{scale:1.0,duration:0.18,ease:"power2.out"}},{landing_delay+0.30:.3f});',
    ]
    return html, js


def build_city_block(city_name, stamp_color, media_items, stamp_index,
                      total_stamps=5, is_double_stamp=False,
                      output_path=None, fps=30, quality="standard"):
    if is_double_stamp:
        assert isinstance(city_name, (list, tuple)) and len(city_name) == 2, \
            "is_double_stamp=True needs city_name=[name1, name2]"
        names = list(city_name)
        colors = list(stamp_color) if isinstance(stamp_color, (list, tuple)) else [stamp_color, stamp_color]
        slug = "-".join(n.lower() for n in names)
    else:
        names = [city_name]
        colors = [stamp_color]
        slug = city_name.lower().replace(" ", "-")

    if not media_items:
        raise ValueError("media_items must have at least one item")

    proj = os.path.join(WORK, "city_blocks", f"{slug}_proj")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)
    media_dir = os.path.join(proj, "media")

    # --- lay out media items back-to-back ---
    media_html = []
    media_js = []
    cursor = 0.0
    for i, item in enumerate(media_items):
        h, js = _emit_media_item(item, i, cursor, media_dir, badge_color=colors[0])
        media_html.append(h)
        media_js.extend(js)
        cursor += item["duration"]
    total_dur = cursor

    # --- stamp(s) ---
    stamp_html = []
    stamp_js = []
    if is_double_stamp:
        size = 230
        positions = [1080 * 0.30, 1080 * 0.70]
        rotations = [-6, 5]
        delays = [0.0, 0.16]
        for i in range(2):
            h, js = _stamp_block(names[i], colors[i], positions[i], size, rotations[i], delays[i], f"stamp{i}")
            stamp_html.append(h)
            stamp_js.extend(js)
    else:
        h, js = _stamp_block(names[0], colors[0], 540, 300, -6, 0.0, "stamp0")
        stamp_html.append(h)
        stamp_js.extend(js)

    # --- progress dots (only stamp_index's own dot filled) ---
    dots_html = []
    for i in range(1, total_stamps + 1):
        if i == stamp_index:
            dots_html.append(
                f'<div class="pdot filled" style="background:{colors[0]};'
                f'border-color:{colors[0]};box-shadow:0 0 18px {colors[0]}99;"></div>')
        else:
            dots_html.append('<div class="pdot"></div>')

    logo_uri = _data_uri(LOGO_SVG, "image/svg+xml")

    html = f"""<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800;900&family=Playfair+Display:wght@700;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:1080px;height:1920px;overflow:hidden;background:#0A0730}}
  .stage{{position:absolute;inset:0}}
  #bg{{position:absolute;inset:0;
      background:
        radial-gradient(ellipse 900px 700px at 50% 8%, rgba(255,255,255,.08), transparent 60%),
        linear-gradient(160deg,#140B5C 0%,#0A0730 46%,#050318 100%);}}
  #bg svg{{position:absolute;left:-60px;top:120px;opacity:.16}}
  #logoWrap{{position:absolute;left:50%;top:16px;transform:translateX(-50%) scale(0.001);opacity:0}}
  #logoWrap img{{display:block;height:34px;width:auto}}
  #progressRow{{position:absolute;left:50%;top:{1480+96}px;transform:translateX(-50%);display:flex;gap:22px}}
  .pdot{{width:28px;height:28px;border-radius:50%;border:3px solid rgba(255,255,255,.4);box-sizing:border-box}}
  #progressLabel{{position:absolute;left:50%;top:{1480+150}px;transform:translateX(-50%);
             font-family:"Poppins",sans-serif;font-weight:700;font-size:24px;
             letter-spacing:.12em;color:rgba(255,255,255,.72)}}
</style></head><body>
<div id="root" data-composition-id="main" data-timeline-locked
     data-start="0" data-duration="{total_dur:.3f}" data-fps="{fps}" data-width="1080" data-height="1920">

  <div class="stage" id="bg">
    <svg width="1200" height="1600" viewBox="0 0 300 400">
      <path d="M 90 30 C 140 20 190 40 210 90 C 230 140 220 200 240 250
               C 255 290 230 330 190 340 C 150 350 120 330 100 300
               C 70 280 40 260 40 220 C 40 180 60 160 55 120
               C 50 80 60 45 90 30 Z"
            fill="none" stroke="{colors[0]}" stroke-width="2.5"/>
    </svg>
  </div>

{"".join(media_html)}

  <div id="logoWrap"><img src="{logo_uri}"/></div>
{"".join(stamp_html)}

  <div id="progressRow">
    {"".join(dots_html)}
  </div>
  <div id="progressLabel">{stamp_index} / {total_stamps} CITIES</div>

</div>
<script>
(function(){{
  window.__timelines=window.__timelines||{{}};
  var tl=gsap.timeline({{paused:true}});

{chr(10).join("  " + line for line in stamp_js)}
{chr(10).join("  " + line for line in media_js)}

  tl.fromTo(".pdot",{{opacity:0,y:14}},{{opacity:1,y:0,duration:0.3,ease:"power2.out",stagger:0.04}},0.55);
  tl.fromTo("#progressLabel",{{opacity:0}},{{opacity:1,duration:0.3}},0.7);
  tl.to("#logoWrap",{{opacity:1,scale:1.0,duration:0.32,ease:"back.out(2.2)"}},0.85);

  tl.seek(0);
  window.__timelines["main"]=tl;
}})();
</script></body></html>
"""

    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(proj, "meta.json"), "w") as f:
        json.dump({"id": f"city_block_{slug}", "name": f"Migration 360 city block: {'/'.join(names)}"}, f)

    if output_path is None:
        output_path = os.path.join(WORK, f"segment_{slug}.mp4")
    cli = hyperframes_cli()
    # --sdr: this pipeline's other stages (ffmpeg compositing, captions,
    # wipes) all expect yuv420p 8-bit H.264 SDR. Phone footage often carries
    # HDR side-data that would otherwise make HyperFrames auto-detect HDR and
    # emit 10-bit HEVC/HLG for the whole segment -- force SDR to stay
    # consistent with every other reel asset.
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(output_path),
                     "-f", str(fps), "-q", quality, "--sdr", "--quiet"],
                    cwd=proj, check=True)
    print(f"[build_city_block] rendered {output_path} ({total_dur:.2f}s)")
    return output_path


if __name__ == "__main__":
    print(__doc__)
