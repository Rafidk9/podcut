"""Render a longtake composition to MP4, frame-exact, with real motion blur.

Motion blur is a shutter: each output frame is the average of `samples`
captures spread across the time the shutter is open (180 deg = half the frame
interval, the film default). Frames where nothing moves (first and last
capture identical) cost one capture. A declared hard cut (beat with cut:true)
is never blurred across -- samples on the far side of the cut are dropped.

Frames are split across `workers` browser processes (frame i goes to worker
i % n). Default 4: on this machine more parallel browsers stalls rather than
speeds up.

Output matches podcut's reel pipeline: H.264 yuv420p, bt709/tv tags, 30 fps,
48 kHz stereo AAC (the comp's SFX cues mixed in, or silence) -- so it can go
straight in as work/opener.mp4, work/sting.mp4 or a B-roll clip.

    python render.py comp.html --out draft.mp4 --draft          # fast look
    python render.py comp.html --out film.mp4                   # full quality
    python render.py comp.html --out still-test.mp4 --dur 2 --shutter 0
"""
import argparse
import concurrent.futures
import json
import multiprocessing
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lt_page  # noqa: E402

sys.path.insert(0, os.path.join(lt_page.PODCUT_ROOT, "reels"))
from ffmpeg_util import COLOR_TAGS, run  # noqa: E402
from render_progress import Progress  # noqa: E402


def sample_times(t, fps, shutter, samples, cuts):
    """Capture times for the frame at t: `samples` points evenly across the
    open shutter, centred on t, minus any on the far side of a hard cut."""
    if shutter <= 0 or samples <= 1:
        return [t]
    span = (shutter / 360.0) / fps
    ts = [t - span / 2 + span * (i + 0.5) / samples for i in range(samples)]
    for c in cuts:
        if abs(c - t) < span:
            ts = [s for s in ts if (s >= c) == (t >= c)] or [t]
    return ts


def work(job):
    """One worker: its own browser, frames job['k'], k+n, k+2n, ..."""
    import numpy as np
    from playwright.sync_api import sync_playwright
    out_dir, fps, n = job["frames_dir"], job["fps"], job["n"]
    stats = {"frames": 0, "captures": 0, "still": 0}
    with sync_playwright() as pw:
        br, pg, info = lt_page.open_comp(pw, job["comp"], job["scale"])
        cuts = [b["t"] for b in info["beats"] if b.get("cut")]
        for i in range(job["k"], job["N"], n):
            path = os.path.join(out_dir, f"{i:05d}.png")
            if job["resume"] and os.path.exists(path):
                continue
            t = i / fps
            ts = sample_times(t, fps, job["shutter"], job["samples"], cuts)
            lt_page.seek(pg, ts[0])
            first = pg.screenshot(type="png")
            stats["captures"] += 1
            if len(ts) > 1:
                lt_page.seek(pg, ts[-1])
                last = pg.screenshot(type="png")
                stats["captures"] += 1
            if len(ts) == 1 or first == last:
                open(path, "wb").write(first)
                stats["still"] += len(ts) > 1
            else:
                from PIL import Image
                import io
                a0 = Image.open(io.BytesIO(first)).convert("RGB")
                a1 = Image.open(io.BytesIO(last)).convert("RGB")
                # Adaptive: the further things travel while the shutter is
                # open, the more captures it takes before the smear stops
                # showing as discrete steps. Measured on small thumbnails.
                th = lambda im: np.asarray(im.convert("L").resize((90, 160)), dtype=np.float32)
                travel = float(np.abs(th(a0) - th(a1)).mean() / 255.0)
                n_s = min(job["max_samples"], max(len(ts), round(len(ts) * (1 + travel * 40))))
                if n_s > len(ts):
                    ts = sample_times(t, fps, job["shutter"], n_s, cuts)
                acc = np.asarray(a0, dtype=np.float32) + np.asarray(a1, dtype=np.float32)
                for s in ts[1:-1]:
                    lt_page.seek(pg, s)
                    acc += np.asarray(lt_page.grab(pg), dtype=np.float32)
                    stats["captures"] += 1
                Image.fromarray(np.clip(acc / len(ts) + 0.5, 0, 255).astype(np.uint8)).save(path, compress_level=1)
            stats["frames"] += 1
        br.close()
    return stats


def resolve_sfx(comp, f):
    for base in (os.path.dirname(os.path.abspath(comp)), lt_page.SFX_LIB):
        p = os.path.join(base, f)
        if os.path.isfile(p):
            return p
    raise SystemExit(f"SFX cue {f!r} not found next to the comp or in {lt_page.SFX_LIB}")


def audio_args(comp, cues, dur):
    """ffmpeg input + filter args for the SFX bed (silence if no cues)."""
    base = ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    if not cues:
        return base, "[1:a]anull[a]"
    args, chains, labels = list(base), [], ["[1:a]"]
    for j, c in enumerate(cues):
        args += ["-i", resolve_sfx(comp, c["file"])]
        idx = j + 2
        ms = max(0, round(c["t"] * 1000))
        chains.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                      f"volume={c.get('vol', 0.8)},adelay={ms}|{ms}[c{j}]")
        labels.append(f"[c{j}]")
    mix = "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,atrim=0:{dur:.3f}[a]"
    return args, ";".join(chains + [mix])


def loudnorm_tail(filter_graph):
    """Rename the mix output [a] -> loudnorm'd [a]."""
    return filter_graph[:-3] + "[pre];[pre]loudnorm=I=-14:TP=-1.5:LRA=11[a]"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("comp")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--dur", type=float, help="render only the first DUR seconds")
    ap.add_argument("--shutter", type=float, default=180, help="degrees; 0 = no motion blur")
    ap.add_argument("--samples", type=int, default=6, help="captures per moving frame (minimum)")
    ap.add_argument("--max-samples", type=int, default=16, help="cap for fast-moving frames (adaptive)")
    ap.add_argument("--draft", action="store_true", help="3 samples, fast x264 preset")
    ap.add_argument("--scale", type=float, default=1.0, help="device scale (2 = 2160x3840 from a 1080x1920 comp)")
    ap.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 3) - 2)))
    ap.add_argument("--no-sfx", action="store_true", help="silent track, ignore the comp's cues")
    ap.add_argument("--loudnorm", action="store_true",
                    help="normalise to -14 LUFS / -1.5 dBTP for a standalone post (skip when the clip feeds the reel pipeline, which normalises the whole reel)")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--keep-frames", action="store_true")
    ap.add_argument("--resume", action="store_true", help="reuse frames already in the frames dir")
    a = ap.parse_args(argv)
    if a.draft:
        a.samples, a.max_samples = min(a.samples, 3), min(a.max_samples, 6)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br, _, info = lt_page.open_comp(pw, a.comp)
        br.close()
    dur = min(a.dur or info["dur"], info["dur"])
    N = int(round(dur * a.fps))
    out = os.path.abspath(a.out)
    frames_dir = out + ".frames"
    if os.path.isdir(frames_dir) and not a.resume:
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir, exist_ok=True)
    nw = max(1, min(a.workers, N))
    print(f"[longtake] {N} frames ({dur:g}s @ {a.fps}fps) on {nw} workers, "
          f"shutter {a.shutter:g} deg x {a.samples} samples", flush=True)

    t0 = time.time()
    job = dict(comp=os.path.abspath(a.comp), frames_dir=frames_dir, fps=a.fps, N=N, n=nw,
               shutter=a.shutter, samples=a.samples, max_samples=a.max_samples, scale=a.scale, resume=a.resume)
    with concurrent.futures.ProcessPoolExecutor(max_workers=nw, mp_context=multiprocessing.get_context("spawn")) as ex:
        futs = [ex.submit(work, dict(job, k=k)) for k in range(nw)]
        # Workers are separate processes, so count the frames they've written
        # rather than wiring a queue through them.
        bar = Progress("[longtake] capture", N)
        running = set(futs)
        while running:
            _, running = concurrent.futures.wait(running, timeout=1)
            n = sum(e.name.endswith(".png") for e in os.scandir(frames_dir))
            bar.update(n, f"frame {n}/{N}")
        bar.finish(ok=not any(f.exception() for f in futs))
        stats = [f.result() for f in futs]
    tot = {k: sum(s[k] for s in stats) for k in stats[0]}
    print(f"[longtake] captured {tot['frames']} frames / {tot['captures']} captures "
          f"({tot['still']} still) in {time.time() - t0:.0f}s", flush=True)
    missing = [i for i in range(N) if not os.path.exists(os.path.join(frames_dir, f"{i:05d}.png"))]
    if missing:
        raise SystemExit(f"{len(missing)} frames missing (first: {missing[0]}) -- re-run with --resume")

    cues = [] if a.no_sfx else [c for c in info["cues"] if c["t"] < dur]
    aargs, afilter = audio_args(a.comp, cues, N / a.fps)
    if a.loudnorm and cues:
        afilter = loudnorm_tail(afilter)
    cmd = ["-framerate", str(a.fps),
           "-i", os.path.join(frames_dir, "%05d.png"), *aargs,
           "-filter_complex", f"[0:v]scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v];{afilter}",
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "fast" if a.draft else "medium",
           "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-r", str(a.fps), *COLOR_TAGS,
           "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-movflags", "+faststart", out]
    run(cmd, label="[longtake] encode")
    if not a.keep_frames:
        shutil.rmtree(frames_dir)
    meta = dict(comp=os.path.abspath(a.comp), fps=a.fps, dur=N / a.fps, shutter=a.shutter,
                samples=a.samples, workers=nw, scale=a.scale, cues=len(cues), seconds=round(time.time() - t0, 1), **tot)
    json.dump(meta, open(out + ".render.json", "w"), indent=1)
    print(f"[longtake] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
