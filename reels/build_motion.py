"""Render this reel's motion-style clips (assets/motion-styles/, via
motion_style.py) into the slots the rest of the pipeline already picks up --
no other stage needs to know a clip came from a motion style:

    role "opener"  -> WORK/opener.mp4   (build_composite.py prepends it)
    role "sting"   -> WORK/sting.mp4    (build_composite.py appends it before
                                         the disclaimer/consultation cards)
    role "broll"   -> WORK/<name>.mp4   (name it in broll_plan.json's "plan";
                                         insert_broll.py splices it like any
                                         HyperFrames stinger)
    role "overlay" -> WORK/<name>.webm  (transparent VP9, for hand compositing)

Opt-in per reel via content.json -- no "motion" key, nothing happens:

    { "motion": [
        { "role": "opener", "style": "split-flap", "text": "NOW|BOARDING|SYD",
          "sub": "PFEC GLOBAL · ON TIME", "dur": 3.5 },
        { "role": "broll", "name": "flap_offices", "style": "isometric",
          "text": "7 OFFICES", "sub": "ACROSS AUSTRALIA", "dur": 1.6,
          "colors": { "c1": "00B3E3" } }
    ] }

A longtake composition (tools/longtake/ -- continuous-take films) plugs into
the same slots: give "take": "<folder in this reel>" instead of "style", e.g.
{ "role": "opener", "take": "opener_take" } renders <reel>/opener_take/comp.html
(scaffold one with `python ../tools/longtake/new.py <reel>/opener_take`).
Takes are opaque, so not for role "overlay".

Optional per entry: "colors" (slot -> hex, over the PFEC preset), "replace"
(template source swaps, over the preset's), "brand": false (upstream look),
"still": [t, ...] (also writes WORK/motion_check/<slot>_<t>.png frames to
eyeball before the full build). Same words-as-spoken rule as everywhere else:
the text must come from THIS reel's content, never a preset's example.

Each output gets a <out>.motion.json sidecar holding the spec it was rendered
from; an unchanged spec with its output present is skipped, so build_all.py
re-runs stay cheap. Delete the output (or the sidecar) to force a re-render."""
import json
import os
import subprocess
import sys

from reel_paths import WORK, REEL, PREVIEW, X264_PRESET  # noqa: E402 -- per-reel folders
import motion_style

ROLES = ("opener", "sting", "broll", "overlay")
LONGTAKE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "longtake")


def load_entries():
    cfg = os.path.join(REEL, "content.json")
    if not os.path.isfile(cfg):
        return []
    entries = json.load(open(cfg, encoding="utf-8")).get("motion", [])
    for i, e in enumerate(entries):
        if e.get("role") not in ROLES:
            raise SystemExit(f"content.json motion[{i}]: role must be one of {ROLES}, got {e.get('role')!r}")
        if not e.get("style") and not e.get("take"):
            raise SystemExit(f"content.json motion[{i}]: needs \"style\" (see python motion_style.py --list) "
                             "or \"take\" (a longtake folder)")
        if e.get("take") and e["role"] == "overlay":
            raise SystemExit(f"content.json motion[{i}]: a longtake is opaque -- use opener/sting/broll")
        if e.get("take") and not os.path.isfile(take_comp(e)):
            raise SystemExit(f"content.json motion[{i}]: {take_comp(e)} not found")
        if e["role"] in ("broll", "overlay") and not e.get("name"):
            raise SystemExit(f"content.json motion[{i}]: role {e['role']!r} needs a \"name\"")
    if sum(e["role"] == "opener" for e in entries) > 1 or sum(e["role"] == "sting" for e in entries) > 1:
        raise SystemExit("content.json motion: at most one opener and one sting per reel")
    return entries


def take_comp(e):
    return os.path.join(REEL, e["take"], "comp.html")


def take_fingerprint(e):
    """mtimes of everything a take renders from, so editing the comp re-renders."""
    d = os.path.join(REEL, e["take"])
    return {f: os.path.getmtime(os.path.join(d, f)) for f in sorted(os.listdir(d))
            if f.endswith((".html", ".js", ".json", ".svg", ".png", ".jpg", ".mp3", ".wav"))}


def render_take(e, out):
    cmd = [sys.executable, os.path.join(LONGTAKE, "render.py"), take_comp(e), "--out", out]
    if PREVIEW:
        cmd.append("--draft")
    subprocess.run(cmd, check=True)


def broll_names():
    """Names this reel's motion entries render as B-roll -- build_broll.py
    uses this so a plan made only of motion clips doesn't demand a broll.py."""
    return {e["name"] for e in load_entries() if e["role"] == "broll"}


def out_path(e):
    if e["role"] in ("opener", "sting"):
        return os.path.join(WORK, f"{e['role']}.mp4")
    return os.path.join(WORK, e["name"] + (".webm" if e["role"] == "overlay" else ".mp4"))


def main():
    entries = load_entries()
    if not entries:
        return
    print(f"[build_motion] {len(entries)} motion clip(s)")
    for e in entries:
        out = out_path(e)
        sidecar = out + ".motion.json"
        spec = {k: v for k, v in e.items() if k != "still"}
        spec["_preview"] = PREVIEW
        if e.get("take"):
            spec["_take_files"] = take_fingerprint(e)
        if os.path.exists(out) and os.path.isfile(sidecar) \
                and json.load(open(sidecar, encoding="utf-8")) == spec:
            print(f"[build_motion] {os.path.basename(out)}: unchanged, skipped")
        elif e.get("take"):
            render_take(e, out)
            json.dump(spec, open(sidecar, "w", encoding="utf-8"), indent=1)
        else:
            motion_style.render(
                e["style"], out, text=e.get("text"), sub=e.get("sub"), dur=e.get("dur"),
                colors=e.get("colors"), replace=e.get("replace"), brand=e.get("brand", True),
                alpha=e["role"] == "overlay", preset=X264_PRESET)
            json.dump(spec, open(sidecar, "w", encoding="utf-8"), indent=1)
        slot = os.path.splitext(os.path.basename(out))[0]
        for t in ([] if e.get("take") else e.get("still", [])):
            png = os.path.join(WORK, "motion_check", f"{slot}_{t:g}.png")
            motion_style.render(e["style"], png, text=e.get("text"), sub=e.get("sub"),
                                dur=e.get("dur"), colors=e.get("colors"), replace=e.get("replace"),
                                brand=e.get("brand", True), alpha=e["role"] == "overlay", still=t)
            print(f"[build_motion] check frame {png}")


if __name__ == "__main__":
    sys.exit(main())
