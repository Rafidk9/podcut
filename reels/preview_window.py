"""Fast iteration tool #2: render a SHORT WINDOW of the reel at DRAFT quality,
instead of the full ~50s composition at standard quality. Use this whenever an
actual video (not just a live-preview screenshot) is needed to confirm
something like footage compositing, B-roll/wipe timing, or audio -- anything
`preview_window` in hyperframes Studio (see workflow note below) can't show
because it's a pure visual/layout check, not a final-encode check.

Usage:
    python preview_window.py START END [--out preview.mp4]

Example: python preview_window.py 39.5 44.0   (checks the date-card sequence)

This reuses the exact same card-building logic as build_captions.py (imported,
not duplicated) so the preview is guaranteed to match what the full render
will produce -- just faster and shorter.
"""
import sys, os, json, shutil, subprocess
import build_captions as bc

from reel_paths import WORK, hyperframes_cli  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def clip_cards(cards, start, end):
    """Keep cards overlapping [start,end), shift into window-local time, clip
    to window bounds."""
    out = []
    for c in cards:
        if c["end"] <= start or c["start"] >= end:
            continue
        out.append({**c, "start": max(0.0, c["start"] - start),
                    "end": min(end - start, c["end"] - start)})
    return out


def build_window_project(start: float, end: float, proj_dir: str) -> float:
    """Build a trimmed overlay-only composition covering just [start, end),
    reading per-reel content via build_captions.load_content()."""
    content = bc.load_content()
    gold = set(g.upper() for g in content["gold"])
    words = bc.load_words(content)
    chunks = bc.chunk_2word(words)
    cards = []
    for k, g in enumerate(chunks):
        cstart = g[0]["start"]
        cend = chunks[k + 1][0]["start"] if k + 1 < len(chunks) else g[-1]["end"] + 0.4
        cards.append({"start": cstart, "end": max(cstart + 0.2, cend), "words": [
            {"text": w["text"].strip().upper(), "gold": bc.norm(w["text"]).upper() in gold}
            for w in g]})
    cards = clip_cards(cards, start, end)

    nm, info, cta, mara = content["name"], content["info"], content["cta"], content["mara"]
    win_dur = end - start

    def sh(t):      # shift an absolute time into the window, clamped
        return max(0.0, min(win_dur, t - start))

    if os.path.exists(proj_dir):
        shutil.rmtree(proj_dir)
    os.makedirs(proj_dir)
    if mara["mode"] == "image":
        bc.crop_mara_badge(proj_dir, mara["src"])
        mara_class, mara_inner = "", (
            '<div class="plate"><img src="mara_badge.png" alt="MARA registration"/>'
            '<div class="shine"></div></div>')
    else:
        mara_class = "styled"
        mara_inner = ('<div class="plate"><div class="seal">' + bc._SEAL_SVG + '</div>'
                      '<div class="txt"><div class="kick">MARA Registered</div>'
                      '<div class="marn">MARN&nbsp;<b>' + mara["marn"] + '</b></div></div>'
                      '<div class="shine"></div></div>')
    html = (bc._CAP_BLOCK
            .replace("__DUR__", f"{win_dur:.3f}")
            .replace("__CARDS__", json.dumps(cards))
            .replace("__DATE_START__", str(sh(info["start"])))
            .replace("__DATE_END__", str(sh(info["end"])))
            .replace("__INFO_KICKER__", info["kicker"])
            .replace("__INFO_LINE1__", info["line1"])
            .replace("__INFO_L1_SIZE__", str(info.get("line1_size", 80)))
            .replace("__INFO_LINE2__", info["line2"])
            .replace("__CTA_START__", str(sh(cta["start"])))
            .replace("__CTA_END__", str(sh(cta["end"])))
            .replace("__CTA_TEXT__", cta["text"])
            .replace("__NAME_START__", str(sh(nm["start"])))
            .replace("__NAME_END__", str(sh(nm["end"])))
            .replace("__NAME_TEXT__", nm["text"])
            .replace("__NAME_ROLE__", nm["role"])
            .replace("__MARA_START__", str(sh(mara["start"])))
            .replace("__MARA_SETTLE__", str(sh(mara["settle"])))
            .replace("__MARA_END__", str(sh(mara["end"])))
            .replace("__MARA_CLASS__", mara_class)
            .replace("__MARA_INNER__", mara_inner))
    open(os.path.join(proj_dir, "index.html"), "w", encoding="utf-8").write(html)
    json.dump({"id": "preview", "name": "window preview"}, open(os.path.join(proj_dir, "meta.json"), "w"))
    return win_dur


def main():
    start, end = float(sys.argv[1]), float(sys.argv[2])
    out = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--out" else os.path.join(WORK, "preview.mp4")
    assert end > start, "end must be after start"

    proj = os.path.join(WORK, "preview_proj")
    win_dur = build_window_project(start, end, proj)

    # draft-quality transparent overlay render (fast)
    overlay = os.path.join(WORK, "preview_overlay.webm")
    cli = hyperframes_cli()
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(FF) + os.pathsep + env.get("PATH", "")
    subprocess.run(["node", cli, "render", ".", "-o", os.path.abspath(overlay),
                    "-f", "30", "--format", "webm", "-q", "draft", "--quiet"],
                   cwd=proj, check=True, env=env)

    # trim the corresponding slice of the real footage (with B-roll/wipes baked in)
    base = os.path.join(WORK, "base_broll.mp4")
    src = base if os.path.exists(base) else os.path.join(WORK, "base.mp4")
    slice_ = os.path.join(WORK, "preview_slice.mp4")
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{start:.3f}", "-i", src, "-t", f"{win_dur:.3f}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                    "-c:a", "aac", slice_], check=True)

    # composite (same libvpx-vp9 alpha-decode fix as the real pipeline)
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", slice_,
                    "-c:v", "libvpx-vp9", "-i", overlay,
                    "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
                    "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "ultrafast",
                    "-crf", "23", "-c:a", "copy", out], check=True)
    print(f"preview ready: {out}  ({win_dur:.2f}s, draft quality)")


if __name__ == "__main__":
    main()
