"""Render one of the 20 vendored motion styles (assets/motion-styles/, from the
"20 Claude Motion Styles" pack) to a pipeline-ready clip, PFEC-branded.

Each style is a self-contained canvas template exposing window.renderFrame(t)
that draws deterministically, so frames are captured exactly (no real-time
playback). Branding happens on a temp copy of the template -- the vendored
files stay byte-identical to upstream:
  * the template's sans stack is swapped to Poppins (the reels' house font,
    loaded from assets/motion-styles/fonts/ -- no Google Fonts round trip).
    Styles that deliberately use a serif/mono face (art-deco, ascii-art,
    wireframe-3d, retro-vhs labels) keep it.
  * the template script is held back until the fonts are loaded -- some
    styles (particles) rasterize their text once at init, so a late font
    would bake the fallback face into every frame.
  * colours default to assets/motion-styles/pfec_presets.json; --set and the
    caller's own colours override per slot.

Output matches the rest of the pipeline: 30fps, bt709/tv tags (COLOR_TAGS),
libx264 crf 18 yuv420p, plus a silent 48k stereo track on opaque .mp4 output
so build_composite.py's norm_segment()/concat never meets a video-only clip.
Transparent output (--alpha) goes to .webm (VP9) or .mov (ProRes 4444).

CLI (no reel needed):
    python motion_style.py --list
    python motion_style.py split-flap out.mp4 --text "NOW|BOARDING|SYD" --dur 5
    python motion_style.py particles check.png --still 3.0 --text "ASK|PFEC"
    python motion_style.py neon-glow overlay.webm --alpha --text LIVE

Per-reel use goes through build_motion.py (content.json "motion" list)."""
import argparse
import base64
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.parse

from ffmpeg_util import FF, COLOR_TAGS
from render_progress import Progress

STYLES_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "assets", "motion-styles")
FONTS = os.path.join(STYLES_ROOT, "fonts")
PRESETS = os.path.join(STYLES_ROOT, "pfec_presets.json")
POPPINS = {300: "Light", 400: "Regular", 500: "Medium", 600: "SemiBold",
           700: "Bold", 800: "ExtraBold", 900: "Black"}
UPSTREAM_SANS = """const SANS = '"Inter","Helvetica Neue",Arial,sans-serif';"""
BRAND_SANS = """const SANS = '"Poppins","Inter","Helvetica Neue",Arial,sans-serif';"""


def style_dir(style):
    """Accept 'split-flap' or 'motion-split-flap'."""
    name = style if style.startswith("motion-") else f"motion-{style}"
    d = os.path.join(STYLES_ROOT, name)
    if not os.path.isfile(os.path.join(d, "template.html")):
        raise SystemExit(f"unknown motion style {style!r} -- run with --list")
    return name, d


def list_styles():
    return sorted(n for n in os.listdir(STYLES_ROOT)
                  if n.startswith("motion-") and os.path.isfile(os.path.join(STYLES_ROOT, n, "template.html")))


def presets():
    return json.load(open(PRESETS, encoding="utf-8"))


def branded_html(template_path, brand=True, replace=None):
    """Template source with Poppins swapped in and the script deferred until
    fonts load. brand=False skips that (upstream look). `replace` is
    {literal source: replacement} -- how upstream demo content baked into a
    template (glassmorphism's "Dubai" weather card, retro-vhs's date stamp)
    gets swapped; a key that no longer matches is an error, never a no-op."""
    src = open(template_path, encoding="utf-8").read()
    for old, new in (replace or {}).items():
        if old not in src:
            raise SystemExit(f"{template_path}: replace key {old!r} not found in template")
        src = src.replace(old, new)
    if not brand:
        return src
    if UPSTREAM_SANS not in src or src.count("<script>") != 1:
        raise SystemExit(f"{template_path}: template harness changed upstream -- "
                         "update motion_style.branded_html() to match")
    faces = "".join(
        f"@font-face{{font-family:'Poppins';font-weight:{w};"
        f"src:url('{pathlib.Path(FONTS, f'Poppins-{n}.ttf').as_uri()}') format('truetype')}}"
        for w, n in POPPINS.items())
    loads = ",".join(f"document.fonts.load('{w} 64px Poppins')" for w in POPPINS)
    src = src.replace(UPSTREAM_SANS, BRAND_SANS)
    src = src.replace("</head>", f"<style>{faces}</style></head>", 1)
    body_start, rest = src.split("<script>", 1)
    script, tail = rest.split("</script>", 1)
    # Hold the template back until every Poppins weight is ready, then run it
    # as a normal classic script (its top-level consts stay global as before).
    loader = ("<script type=\"text/plain\" id=\"tpl\">" + script + "</script>"
              "<script>Promise.all([" + loads + "]).then(()=>{const s=document.createElement('script');"
              "s.textContent=document.getElementById('tpl').textContent;document.body.appendChild(s);});</script>")
    return body_start + loader + tail


def render(style, out, *, text=None, sub=None, dur=None, colors=None, w=1080, h=1920,
           fps=30, alpha=False, still=None, brand=True, crf=18, preset="medium", audio=True,
           replace=None):
    """Render `style` to `out` (.mp4 / .webm / .mov, or .png with still=t).
    Returns the output path. colors: {slot: hex} and replace: {old: new} are
    each merged over the PFEC preset's own."""
    from playwright.sync_api import sync_playwright

    name, d = style_dir(style)
    pre = presets().get(name, {}) if brand else {}
    cols = dict(pre.get("colors", {}))
    cols.update({k: v.lstrip("#") for k, v in (colors or {}).items()})
    swaps = dict(pre.get("replace", {}))
    swaps.update(replace or {})

    q = {"render": "1", "w": w, "h": h, **cols}
    if dur:
        q["dur"] = dur
    if text is not None:
        q["text"] = text
    if sub is not None:
        q["sub"] = sub
    if alpha:
        q["alpha"] = "1"

    # Temp copy sits next to the template so any relative path still resolves.
    fd, tmp = tempfile.mkstemp(suffix=".html", prefix=".render_", dir=d)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(branded_html(os.path.join(d, "template.html"), brand, swaps))
    url = pathlib.Path(tmp).as_uri() + "?" + urllib.parse.urlencode(q)
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--disable-gpu-vsync", "--allow-file-access-from-files"])
            pg = br.new_page(viewport={"width": min(w, 1920), "height": min(h, 1920)})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(url)
            pg.wait_for_function('typeof window.renderFrame === "function"', timeout=20000)
            if errs:
                raise SystemExit(f"{name} template error: {errs[0]}")
            if brand and not pg.evaluate("document.fonts.check('700 64px Poppins')"):
                raise SystemExit(f"{name}: Poppins failed to load from {FONTS}")
            total = pg.evaluate("window.__dur")
            grab = "([t,f])=>{renderFrame(t);return document.getElementById('c').toDataURL(f)}"

            if still is not None:
                data = pg.evaluate(grab, [still, "image/png"])
                pathlib.Path(out).write_bytes(base64.b64decode(data.split(",", 1)[1]))
                br.close()
                return out

            n = int(round(total * fps))
            ext = os.path.splitext(out)[1].lower()
            cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
                   "-f", "image2pipe", "-c:v", "png", "-framerate", str(fps), "-i", "-"]
            if alpha and ext == ".webm":
                cmd += ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24"]
            elif alpha:
                cmd += ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
            else:
                if audio:
                    cmd += ["-f", "lavfi", "-t", f"{n / fps:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                            "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-ar", "48000", "-ac", "2"]
                # Canvas frames are full-range RGB: convert explicitly to
                # bt709 limited range so the pixels match the tags we stamp.
                cmd += ["-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
                        "-r", str(fps), *COLOR_TAGS, "-movflags", "+faststart"]
            ff = subprocess.Popen(cmd + [out], stdin=subprocess.PIPE)
            bar = Progress(f"[motion] {name}", n)
            for i in range(n):
                data = pg.evaluate(grab, [i / fps, "image/png"])
                ff.stdin.write(base64.b64decode(data.split(",", 1)[1]))
                bar.update(i + 1, f"frame {i + 1}/{n}")
            ff.stdin.close()
            ret = ff.wait()
            bar.finish(ok=ret == 0)
            if ret != 0:
                raise SystemExit(f"{name}: ffmpeg encode failed for {out}")
            br.close()
            print(f"[motion] {name}: wrote {out} ({n} frames, {total}s @ {fps}fps, {w}x{h})")
            return out
    finally:
        os.remove(tmp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("style", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--list", action="store_true", help="list styles with their PFEC preset notes")
    ap.add_argument("--text")
    ap.add_argument("--sub")
    ap.add_argument("--example", action="store_true", help="use the preset's sample text/sub")
    ap.add_argument("--dur", type=float)
    ap.add_argument("--w", type=int, default=1080)
    ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--set", action="append", default=[], help="colour slot override, e.g. c1=FFC500")
    ap.add_argument("--alpha", action="store_true")
    ap.add_argument("--still", type=float)
    ap.add_argument("--no-brand", action="store_true", help="upstream colours/fonts, untouched")
    a = ap.parse_args(argv)

    if a.list:
        pre = presets()
        for n in list_styles():
            print(f"{n[len('motion-'):]:<16} {pre.get(n, {}).get('notes', '')}")
        return 0
    if not (a.style and a.out):
        ap.error("style and out are required (or --list)")
    text, sub = a.text, a.sub
    if a.example:
        ex = presets().get(style_dir(a.style)[0], {}).get("example", {})
        text = ex.get("text") if text is None else text
        sub = ex.get("sub") if sub is None else sub
    render(a.style, a.out, text=text, sub=sub, dur=a.dur, w=a.w, h=a.h, fps=a.fps,
           colors=dict(kv.split("=", 1) for kv in a.set), alpha=a.alpha,
           still=a.still, brand=not a.no_brand)
    if a.still is not None:
        print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
