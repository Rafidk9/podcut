"""Render this reel's B-roll stingers via HyperFrames -- each one should tie
to the specific moment it cuts away from/into (see load_stingers()), never a
generic wordmark reused across reels. No claims, no real scenery photography
-- pure on-brand motion graphics, safe for any connecting phrase. Opaque
render (full-frame replacement, no alpha needed)."""
import os, shutil, subprocess, json, importlib.util

from reel_paths import WORK, REEL, hyperframes_cli  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"


def load_stingers():
    """Per-reel B-roll content: <reel>/broll.py defining STINGERS =
    [(name, duration, body_html), ...].

    Required per reel -- deliberately NO cross-reel fallback. An earlier
    version silently reused 4 previous-reel stingers (Lakemba's) whenever
    this file was missing, which is generic off-topic content with no error,
    not a safe default -- see the "Must do" section in reels/README.md. If
    this reel genuinely has no B-roll, give it a broll_plan.json with an
    empty "plan" (see insert_broll.py) and skip writing a broll.py at all --
    that's read here as the explicit opt-out, not an oversight."""
    override = os.path.join(REEL, "broll.py")
    if os.path.isfile(override):
        spec = importlib.util.spec_from_file_location("reel_broll", override)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.STINGERS

    plan_cfg = os.path.join(REEL, "broll_plan.json")
    if os.path.isfile(plan_cfg):
        plan = json.load(open(plan_cfg, encoding="utf-8")).get("plan", {})
        if not plan:
            return []  # explicit opt-out: this reel has no B-roll

    raise SystemExit(
        f"No {override} found for this reel, and broll_plan.json doesn't "
        "declare an empty plan either. Write a <reel>/broll.py with "
        "STINGERS = [(name, duration, body_html), ...] derived from THIS "
        "reel's own transcript, or -- if it genuinely has no connecting/"
        'filler phrases worth covering -- give it a broll_plan.json with '
        '"plan": {} and "boundaries": {}. There is no cross-reel default.')


def render(name, dur, body_html, extra_css=""):
    proj = os.path.join(WORK, f"broll_proj_{name}")
    if os.path.exists(proj):
        shutil.rmtree(proj)
    os.makedirs(proj)
    html = f"""<!doctype html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800;900&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ width:1080px; height:1920px; overflow:hidden; }}
  {extra_css}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{dur}"
     data-width="1080" data-height="1920" style="position:relative;width:1080px;height:1920px">
{body_html}
</div>
</body></html>
"""
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(html)
    json.dump({"id": name, "name": name}, open(os.path.join(proj, "meta.json"), "w"))

    out = os.path.join(WORK, f"{name}.mp4")
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(out),
                    "-f", "30", "-q", "standard", "--quiet"],
                   cwd=proj, check=True, env=env)
    print("rendered", out)


if __name__ == "__main__":
    for name, dur, html in load_stingers():
        render(name, dur, html)
