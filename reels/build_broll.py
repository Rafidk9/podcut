"""Render this reel's B-roll stingers via HyperFrames -- each one should tie
to the specific moment it cuts away from/into (see load_stingers()), never a
generic wordmark reused across reels. No claims, no real scenery photography
-- pure on-brand motion graphics, safe for any connecting phrase. Opaque
render (full-frame replacement, no alpha needed).

Stingers render CONCURRENTLY (each is an independent HyperFrames project +
ffmpeg-free subprocess call -- no shared state): ThreadPoolExecutor, not
ProcessPoolExecutor, since the actual work happens in a spawned `node`
subprocess and subprocess.run() releases the GIL for the wait, same as any
blocking I/O -- there's no CPU-bound Python work here for a process pool to
usefully parallelize, just the overhead of pickling across it. Default
workers: min(4, cpu count); override with --workers N."""
import concurrent.futures, os, shutil, subprocess, sys, json, importlib.util

from reel_paths import WORK, REEL, HF_QUALITY, HF_FPS, hyperframes_cli  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"


def _workers_from_argv(default):
    if "--workers" in sys.argv:
        i = sys.argv.index("--workers")
        if i + 1 < len(sys.argv):
            return max(1, int(sys.argv[i + 1]))
    return default


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
    # Output captured (not inherited) -- with several of these running at
    # once, letting each subprocess write straight to the shared terminal
    # would interleave their output into an unreadable mess. Only printed
    # (in full, clearly attributed) if this stinger's render actually fails.
    result = subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(out),
                             "-f", str(HF_FPS), "-q", HF_QUALITY, "--quiet"],
                            cwd=proj, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"B-roll render failed for stinger {name!r} (exit {result.returncode})\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}")
    print("rendered", out)
    return out


def main():
    stingers = load_stingers()
    if not stingers:
        return

    n_workers = _workers_from_argv(min(4, os.cpu_count() or 1))
    print(f"[build_broll] rendering {len(stingers)} stinger(s), "
          f"up to {n_workers} concurrently")

    with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as ex:
        futures = {ex.submit(render, name, dur, html): name for name, dur, html in stingers}
        errors = []
        for fut in concurrent.futures.as_completed(futures):
            name = futures[fut]
            try:
                fut.result()
            except Exception as e:
                errors.append((name, e))

    if errors:
        # Fail the WHOLE stage on any single failure -- no silent partial
        # output (some stingers may have written a .mp4, others won't have).
        # Every failure gets its own clearly-attributed block, not just the
        # first one, since several could fail independently in one run.
        for name, e in errors:
            print(f"\n[build_broll] FAILED: stinger {name!r}\n{e}\n")
        raise SystemExit(
            f"{len(errors)} of {len(stingers)} B-roll stinger render(s) failed -- see above")


if __name__ == "__main__":
    main()
