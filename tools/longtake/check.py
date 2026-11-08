"""Continuity + rhythm check for a longtake composition -- run it before
anyone watches a render. Exits non-zero on any FAIL.

What it measures (no blur, ~10 samples/sec):
  * handoffs -- at each declared beat boundary, which [data-lt] elements are
    on screen just before AND just after. Nothing in common = the next beat
    replaced the last one (a slideshow). FAIL. The beat's declared `handoff`
    element must be one of the survivors. FAIL if not.
  * undeclared replacement -- anywhere in the film, two neighbouring samples
    whose visible sets share nothing. FAIL unless a beat with cut:true sits
    there.
  * rhythm -- beat intervals all about the same length reads as a metronome
    (WARN); no rests (>= 0.3 s where almost nothing moves) means the moves
    never land (WARN); mostly still means it's a poster, not a film (WARN).
  * safe zone (9:16) -- text elements inside the top 8% / bottom 15% /
    right 10% that TikTok/IG/Shorts cover with UI. WARN.

    python check.py comp.html
    python check.py comp.html --json report.json --sheet boundaries.png
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lt_page  # noqa: E402

STEP = 0.1          # seconds between samples
SIDE = 0.3          # look this far either side of a boundary
REST_MOTION = 0.002  # fraction of pixels changed below which a step counts as "still"
PIX_DELTA = 6        # grey levels a thumbnail pixel must move to count as changed
REST_MIN = 0.3      # seconds of stillness that count as a rest
SAFE = {"top": 0.08, "bottom": 0.15, "right": 0.10}


def motion(a, b):
    """Fraction of thumbnail pixels that changed -- a small element moving
    still registers, unlike a whole-frame mean, which a 120px dot barely dents."""
    import numpy as np
    return float((np.abs(a.astype(np.int16) - b.astype(np.int16)) > PIX_DELTA).mean())


def small(img):
    import numpy as np
    return np.asarray(img.convert("L").resize((108, int(108 * img.height / img.width))))


def analyse(comp, sheet=None):
    from playwright.sync_api import sync_playwright
    res = {"comp": os.path.abspath(comp), "items": []}
    add = lambda lvl, what, msg: res["items"].append({"level": lvl, "check": what, "msg": msg})
    with sync_playwright() as pw:
        br, pg, info = lt_page.open_comp(pw, comp)
        dur, beats = info["dur"], info["beats"]
        W, H = info["size"]
        n = int(dur / STEP) + 1
        times = [round(min(dur, i * STEP), 4) for i in range(n)]
        vis, frames = [], []
        for t in times:
            lt_page.seek(pg, t)
            vis.append(lt_page.visible(pg))
            frames.append(small(lt_page.grab(pg)))

        def at(t):
            lt_page.seek(pg, max(0, min(dur, t)))
            return lt_page.visible(pg)

        # ---- handoffs at declared beats
        cut_times = [b["t"] for b in beats if b["cut"]]
        boundary_shots = []
        for b in beats:
            if b["t"] <= 0 or b["t"] >= dur:
                continue
            before, after = at(b["t"] - SIDE), at(b["t"] + SIDE)
            carried = sorted(set(before) & set(after))
            label = f"beat @{b['t']:.2f}s" + (f" '{b['name']}'" if b["name"] else "")
            if b["cut"]:
                add("OK", label, "declared hard cut")
            elif not before or not after:
                add("FAIL", label, f"empty frame on one side (before={sorted(before)}, after={sorted(after)})")
            elif not carried:
                add("FAIL", label, f"nothing survives -- {sorted(before)} replaced by {sorted(after)}")
            elif b["handoff"] and b["handoff"] not in carried:
                add("FAIL", label, f"handoff '{b['handoff']}' not on screen on both sides (survivors: {carried})")
            else:
                add("OK", label, f"carried by {carried}" + (f" (handoff '{b['handoff']}')" if b["handoff"] else ""))
            if sheet:
                for t in (b["t"] - SIDE, b["t"], b["t"] + SIDE):
                    lt_page.seek(pg, max(0, min(dur, t)))
                    boundary_shots.append((t, lt_page.grab(pg)))
        if not [b for b in beats if 0 < b["t"] < dur]:
            add("WARN", "beats", "no beats declared -- nothing to check handoffs against (LT.comp beats: [...])")

        # ---- undeclared replacement anywhere
        for i in range(1, n):
            a, b = set(vis[i - 1]), set(vis[i])
            if a and b and not (a & b) and not any(times[i - 1] - STEP <= c <= times[i] + STEP for c in cut_times):
                add("FAIL", f"replacement @{times[i]:.2f}s", f"{sorted(a)} -> {sorted(b)} with nothing carried and no cut:true beat")

        # ---- rhythm
        bt = sorted({0.0, dur, *[b["t"] for b in beats if 0 < b["t"] < dur]})
        gaps = [y - x for x, y in zip(bt, bt[1:])]
        if len(gaps) >= 4:
            mean = sum(gaps) / len(gaps)
            cv = (sum((g - mean) ** 2 for g in gaps) / len(gaps)) ** 0.5 / mean
            if cv < 0.18:
                add("WARN", "rhythm", f"beats are evenly spaced (~{mean:.2f}s each, variation {cv:.0%}) -- vary the lengths so it doesn't tick like a metronome")
            else:
                add("OK", "rhythm", f"{len(gaps)} beats, lengths vary {cv:.0%} (mean {mean:.2f}s)")
        m = [motion(frames[i - 1], frames[i]) for i in range(1, n)]
        # rests = runs of consecutive still steps lasting >= REST_MIN
        rests, start = [], None
        for i, v in enumerate(m + [1.0]):  # sentinel closes a trailing run
            if v < REST_MOTION:
                start = i if start is None else start
            elif start is not None:
                if (i - start) * STEP >= REST_MIN - 1e-9:
                    rests.append([times[start], times[i]])
                start = None
        still_frac = sum(v < REST_MOTION for v in m) / max(1, len(m))
        if not rests:
            add("WARN", "rests", "no rest anywhere (>= 0.3s nearly still) -- moves land harder after a hold")
        else:
            add("OK", "rests", f"{len(rests)} rest(s): " + ", ".join(f"{a:.1f}-{b:.1f}s" for a, b in rests[:6]))
        if still_frac > 0.6:
            add("WARN", "stillness", f"{still_frac:.0%} of the film is still -- this reads as a poster")
        res["motion"] = {"still_fraction": round(still_frac, 3), "peak": round(max(m) if m else 0, 4)}

        # ---- safe zone (portrait only)
        if H > W:
            hits = {}
            for t, v in zip(times, vis):
                for k, e in v.items():
                    if not e["text"] or e["a"] < 0.5:
                        continue
                    x, y, w, h = e["box"]
                    where = [z for z, bad in (("top", y < SAFE["top"] * H), ("bottom", y + h > (1 - SAFE["bottom"]) * H),
                                              ("right", x + w > (1 - SAFE["right"]) * W)) if bad]
                    if where:
                        hits.setdefault(k, (t, where))
            for k, (t, where) in hits.items():
                add("WARN", "safe zone", f"text '{k}' enters the {'/'.join(where)} UI zone (first at {t:.1f}s)")
            if not hits:
                add("OK", "safe zone", "all text clear of platform UI zones")
        br.close()

    if sheet and boundary_shots:
        from PIL import Image, ImageDraw
        tw, th = 216, int(216 * H / W)
        img = Image.new("RGB", (tw * 3 + 8, (th + 4) * (len(boundary_shots) // 3)), "white")
        for j, (t, shot) in enumerate(boundary_shots):
            x, y = (j % 3) * (tw + 4), (j // 3) * (th + 4)
            img.paste(shot.resize((tw, th)), (x, y))
            ImageDraw.Draw(img).text((x + 6, y + 6), f"{t:.2f}s", fill="white")
        img.save(sheet)
        res["sheet"] = os.path.abspath(sheet)
    res["fails"] = sum(i["level"] == "FAIL" for i in res["items"])
    res["warns"] = sum(i["level"] == "WARN" for i in res["items"])
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("comp")
    ap.add_argument("--json", help="write the report here")
    ap.add_argument("--sheet", help="PNG of each boundary: before / at / after")
    a = ap.parse_args(argv)
    res = analyse(a.comp, a.sheet)
    for i in res["items"]:
        print(f"{i['level']:<5} {i['check']:<28} {i['msg']}")
    print(f"\n{res['fails']} FAIL, {res['warns']} WARN" + (f"  (sheet: {res['sheet']})" if res.get("sheet") else ""))
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    return 1 if res["fails"] else 0


if __name__ == "__main__":
    sys.exit(main())
