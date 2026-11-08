"""Shared plumbing for longtake tools: open a composition in headless Chromium,
wait until it's ready, seek it, grab frames, and read what's on screen."""
import io
import os
import pathlib

PODCUT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SFX_LIB = os.path.join(PODCUT_ROOT, "assets", "sfx")

# Every [data-lt] element that is actually visible right now: effective
# opacity (product up the tree) above a floor, not display/visibility hidden,
# and a non-trivial on-screen area inside the stage. Returns
# {id: {"a": opacity, "box": [x, y, w, h], "text": bool}}.
VISIBLE_JS = """() => {
  const stage = document.getElementById('stage').getBoundingClientRect();
  const out = {};
  for (const el of document.querySelectorAll('[data-lt]')) {
    let a = 1, n = el, hidden = false;
    while (n && n.nodeType === 1) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') { hidden = true; break; }
      a *= parseFloat(cs.opacity);
      n = n.parentElement;
    }
    if (hidden || a < 0.06) continue;
    const r = el.getBoundingClientRect();
    const x0 = Math.max(r.left, stage.left), y0 = Math.max(r.top, stage.top);
    const x1 = Math.min(r.right, stage.right), y1 = Math.min(r.bottom, stage.bottom);
    if (x1 - x0 < 2 || y1 - y0 < 2) continue;
    out[el.dataset.lt] = { a: +a.toFixed(3), box: [x0 - stage.left, y0 - stage.top, x1 - x0, y1 - y0],
                           text: el.dataset.ltText !== undefined || (el.children.length === 0 && el.textContent.trim().length > 0) };
  }
  return out;
}"""


def comp_url(comp):
    return pathlib.Path(comp).resolve().as_uri() + "?render=1"


def open_comp(pw, comp, scale=1.0):
    """Launch a browser on `comp`; returns (browser, page, info) with info =
    {dur, size, beats, cues}. Raises on page errors during load."""
    br = pw.chromium.launch(args=["--allow-file-access-from-files", "--disable-gpu-vsync"])
    pg = br.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=scale)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(comp_url(comp))
    try:
        pg.wait_for_function("window.__ready === true", timeout=30000)
    except Exception:
        raise SystemExit(f"{comp}: composition never became ready "
                         f"(page errors: {errs[:3] or 'none'}) -- does it call LT.comp()?")
    if errs:
        raise SystemExit(f"{comp}: page error: {errs[0]}")
    w, h = pg.evaluate("window.__size")
    if (w, h) != (1080, 1920):
        pg.set_viewport_size({"width": w, "height": h})
    info = pg.evaluate("({dur: window.__dur, size: window.__size, beats: window.__beats, cues: window.__cues})")
    info["errors"] = errs
    return br, pg, info


def seek(pg, t):
    pg.evaluate("t => window.__seek(t)", t)


def grab(pg):
    """Current frame as an RGB PIL image. In render mode the viewport is the
    stage size and the stage sits at 0,0 (the template's body has no margin),
    so a plain viewport screenshot is the frame -- much faster than a locator
    screenshot, which re-measures the element every call."""
    from PIL import Image
    png = pg.screenshot(type="png")
    return Image.open(io.BytesIO(png)).convert("RGB")


def visible(pg):
    return pg.evaluate(VISIBLE_JS)
