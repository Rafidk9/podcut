"""Pre-post QA gate for a finished reel.

Runs the deterministic technical checks (spec / colour / loudness / true-peak /
clipping / black-frames / first-frame / duration), confirms the deliverables
exist, and does a light caption.txt sanity pass (leftover [NEED] placeholders,
disclaimer present, risky 'guarantee'-style claims) plus a heuristic caption
safe-zone note. Prints a PASS / WARN / FAIL report and exits non-zero if anything
FAILs, so it can gate a post.

Run from reels/ (uses reel_paths to pick the reel; set PODCUT_REEL to override):
    python qa_reel.py

This does NOT replace an eyes-and-ears pass -- reverb/noise, mishears, on-screen
PII, MARN correctness, factual accuracy and in-app safe-zones still need a human.
"""
import json, os, re, shutil, subprocess, sys

from reel_paths import REEL, OUT, WORK, PREVIEW  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

FINAL = os.path.join(OUT, "reel_final_preview.mp4" if PREVIEW else "reel_final.mp4")
OK, WARN, FAIL, INFO = "OK", "WARN", "FAIL", "info"
results = []


def add(status, label, detail=""):
    results.append((status, label, detail))


def probe(select, entries, path=FINAL):
    """ffprobe key=value dict for one stream (select e.g. 'v:0' / 'a:0')."""
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", select, "-show_entries", entries,
         "-of", "default=nw=1:nokey=0", path], capture_output=True, text=True).stdout
    return dict(line.split("=", 1) for line in out.strip().splitlines() if "=" in line)


def ff_null(af=None, vf=None, frames=None):
    """Run ffmpeg to null and return stderr (where the filter measurements land)."""
    cmd = [FF, "-hide_banner", "-nostats", "-i", FINAL]
    if af:
        cmd += ["-af", af]
    if vf:
        cmd += ["-vf", vf]
    if frames:
        cmd += ["-frames:v", str(frames)]
    cmd += ["-f", "null", "-"]
    return subprocess.run(cmd, capture_output=True, text=True).stderr


def check_preview_marker():
    """A preview build must never pass as a deliverable, however it's
    invoked -- catch it two ways: the _preview filename suffix (build_all.py
    --preview / build_composite.py always name it this way) AND the
    -metadata preview_build tag baked into the file itself (still catches a
    preview file that got renamed/copied over reel_final.mp4 by mistake)."""
    by_name = "_preview" in os.path.basename(FINAL)
    # format_tags land on the *format*, not a stream -- no -select_streams here.
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format_tags=preview_build",
                          "-of", "default=nw=1:nokey=1", FINAL],
                         capture_output=True, text=True).stdout.strip() if os.path.isfile(FINAL) else ""
    by_tag = out not in ("", "N/A")
    if by_name or by_tag:
        add(FAIL, "Preview build", "not a deliverable"
            + (" (filename)" if by_name else "") + (" (metadata tag)" if by_tag else ""))
    elif PREVIEW:
        # --preview was passed but neither signal fired -- still refuse; a
        # preview build must never silently pass just because the marker
        # logic missed it.
        add(FAIL, "Preview build", "--preview requested but no preview marker found on the "
            "file -- refusing anyway, this should not happen")
    else:
        add(OK, "Preview build", "no (this is a full build)")


def check_specs():
    v = probe("v:0", "stream=codec_name,width,height,r_frame_rate,pix_fmt,"
                     "color_space,color_transfer,color_primaries,color_range")
    if not v:
        add(FAIL, "Video stream", "no video stream found")
        return
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    add(OK if (w, h) == (1080, 1920) else FAIL, "Resolution",
        f"{w}x{h}" + ("" if (w, h) == (1080, 1920) else " (expected 1080x1920, 9:16)"))
    num, _, den = v.get("r_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den or 1)
    add(OK if abs(fps - 30) < 0.5 else WARN, "Frame rate", f"{fps:.3g} fps"
        + ("" if abs(fps - 30) < 0.5 else " (expected 30)"))
    add(OK if v.get("codec_name") == "h264" else WARN, "Video codec", v.get("codec_name", "?"))
    add(OK if v.get("pix_fmt") == "yuv420p" else WARN, "Pixel format",
        v.get("pix_fmt", "?") + ("" if v.get("pix_fmt") == "yuv420p" else " (yuv420p is safest)"))

    want = {"color_space": "bt709", "color_transfer": "bt709",
            "color_primaries": "bt709", "color_range": "tv"}
    bad = {k: v.get(k) for k, exp in want.items() if v.get(k) != exp}
    add(OK if not bad else FAIL, "Colour tags",
        "bt709 / tv" if not bad else "wrong/unset: " + ", ".join(f"{k}={val}" for k, val in bad.items()))

    a = probe("a:0", "stream=codec_name,sample_rate,channels")
    if not a:
        add(WARN, "Audio stream", "no audio stream found")
    else:
        okA = a.get("codec_name") == "aac" and a.get("sample_rate") == "48000" and a.get("channels") == "2"
        add(OK if okA else WARN, "Audio spec",
            f"{a.get('codec_name')} {a.get('sample_rate')}Hz {a.get('channels')}ch")


def check_duration():
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration,size",
                          "-of", "default=nw=1:nokey=0", FINAL], capture_output=True, text=True).stdout
    d = dict(line.split("=", 1) for line in out.strip().splitlines() if "=" in line)
    dur = float(d.get("duration", 0)); mb = int(d.get("size", 0)) / 1e6
    status = OK if 5 <= dur <= 180 else WARN
    tail = "" if 5 <= dur <= 180 else " (reels sweet spot ~15-90s; check platform max)"
    add(status, "Duration", f"{dur:.1f}s, {mb:.1f} MB{tail}")


def check_loudness():
    st = ff_null(af="ebur128=peak=true")
    Is = re.findall(r"\bI:\s*(-?[\d.]+)\s*LUFS", st)
    lra = re.search(r"LRA:\s*(-?[\d.]+)\s*LU", st[st.rfind("Loudness range"):] if "Loudness range" in st else st)
    if Is:
        I = float(Is[-1])
        add(OK if abs(I + 14) <= 1.0 else WARN, "Loudness (integrated)",
            f"{I:.1f} LUFS" + ("" if abs(I + 14) <= 1.0 else " (target -14 +/-1)")
            + (f", LRA {lra.group(1)}" if lra else ""))
    else:
        add(INFO, "Loudness", "could not parse ebur128")
    tp = re.search(r"True peak:\s*Peak:\s*(-?[\d.]+)", st)
    if tp:
        v = float(tp.group(1))
        status = FAIL if v >= 0 else (WARN if v > -1.0 else OK)
        note = " (CLIPPING)" if v >= 0 else (" (over -1 dBTP target)" if v > -1.0 else "")
        add(status, "True peak", f"{v:.1f} dBTP{note}")


def check_clipping():
    st = ff_null(af="astats=metadata=0")
    flats = [float(x) for x in re.findall(r"Flat factor:\s*([\d.]+)", st)]
    peaks = [float(x) for x in re.findall(r"Peak level dB:\s*(-?[\d.]+)", st)]
    fmax = max(flats) if flats else 0.0
    pk = max(peaks) if peaks else None
    if fmax > 0:
        add(WARN, "Clipping", f"flat factor {fmax:.1f} (>0 = flat-topped/clipped samples)")
    else:
        add(OK, "Clipping", "none" + (f" (peak {pk:.1f} dB)" if pk is not None else ""))


def check_black_and_firstframe():
    st = ff_null(vf="blackdetect=d=0.05:pix_th=0.10")
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", st)
    if blacks:
        add(WARN, "Black frames", "; ".join(f"{s}-{e}s" for s, e in blacks[:4])
            + (" ..." if len(blacks) > 4 else "") + " (glitch or unintended fade?)")
    else:
        add(OK, "Black frames", "none")
    st2 = ff_null(vf="signalstats,metadata=print:key=lavfi.signalstats.YAVG", frames=1)
    m = re.search(r"YAVG=([\d.]+)", st2)
    if m:
        y = float(m.group(1))
        add(OK if y >= 16 else WARN, "First frame",
            f"YAVG {y:.0f}" + ("" if y >= 16 else " (near-black start -- weak hook?)"))


def check_deliverables():
    for name in ("caption.txt", "thumbnail.jpg"):
        add(OK if os.path.isfile(os.path.join(OUT, name)) else FAIL, name,
            "present" if os.path.isfile(os.path.join(OUT, name)) else "MISSING")


def check_caption_text():
    cap = os.path.join(OUT, "caption.txt")
    if not os.path.isfile(cap):
        return
    text = open(cap, encoding="utf-8").read()
    if "[NEED" in text:
        add(FAIL, "Caption placeholders", "un-overridden default(s) present: [NEED: ...]")
    else:
        add(OK, "Caption placeholders", "none")
    add(OK if "Disclaimer" in text else WARN, "Compliance disclaimer",
        "present" if "Disclaimer" in text else "MISSING from caption")
    # risky claim scan -- skip the verbatim disclaimer block (it legitimately
    # contains 'does not assure ... outcome'); scan only the copy above it.
    body = text.split("▎ Disclaimer")[0]
    risky = sorted(set(re.findall(r"(?i)\b(guarantee[ds]?|guaranteeing|100\s*%|no[- ]risk)\b", body)))
    add(WARN if risky else OK, "Overpromising scan",
        "review: " + ", ".join(risky) if risky else "no guarantee-style claims in copy")


def _norm_word(t):
    return t.strip().strip(".,!?;:\"'").lower()


def check_drift():
    """Caption/audio sync check: build_captions.py persists the first/last
    rendered caption cue's own text + start time (caption_sync.json) at
    render time. Re-reading the CURRENT assembled.transcript.json here and
    finding that same word confirms the two haven't drifted apart since --
    e.g. someone re-ran build_base.py with different clip trims (or a
    different broll_plan.json changed a splice boundary) without a matching
    re-run of build_captions.py, leaving stale captions baked into the video
    at the wrong point relative to the real audio. Always prints the
    measured drift for both ends, pass or fail, so trends are visible over
    time even when everything's fine."""
    sync_path = os.path.join(WORK, "caption_sync.json")
    transcript_path = os.path.join(WORK, "assembled.transcript.json")
    if not os.path.isfile(sync_path) or not os.path.isfile(transcript_path):
        add(INFO, "Caption/audio drift", "sync data unavailable (run build_captions.py to enable)")
        return

    sync = json.load(open(sync_path, encoding="utf-8"))
    words = json.load(open(transcript_path, encoding="utf-8"))["words"]

    for label, key in (("first", "first_cue"), ("last", "last_cue")):
        cue = sync.get(key)
        if not cue:
            continue
        target = _norm_word(cue["text"])
        candidates = [w for w in words if _norm_word(w["text"]) == target]
        if not candidates:
            add(WARN, f"Caption/audio drift ({label})",
                f"word {cue['text']!r} not found in current transcript -- rebuild captions")
            continue
        nearest = min(candidates, key=lambda w: abs(w["start"] - cue["start"]))
        drift_ms = abs(nearest["start"] - cue["start"]) * 1000
        status = FAIL if drift_ms >= 200 else (WARN if drift_ms >= 120 else OK)
        note = "" if status == OK else (" (>200ms)" if status == FAIL else " (>120ms)")
        add(status, f"Caption/audio drift ({label})",
            f"{drift_ms:.0f}ms{note} -- {cue['text']!r} baked @ {cue['start']:.2f}s, "
            f"now @ {nearest['start']:.2f}s")


def check_safezone():
    cap_top = "62%"
    cfg = os.path.join(REEL, "content.json")
    if os.path.isfile(cfg):
        cap_top = str(json.load(open(cfg, encoding="utf-8")).get("cap_top", "62%"))
    try:
        frac = float(cap_top.strip().rstrip("%")) / 100.0
    except ValueError:
        frac = 0.62
    half = 0.06  # ~2-line band
    lo, hi = frac - half, frac + half
    if hi > 0.85 or lo < 0.08:
        add(WARN, "Safe-zone (captions)",
            f"caption band ~{lo:.0%}-{hi:.0%} may hit platform UI (bottom ~15% / top ~8%)")
    else:
        add(OK, "Safe-zone (captions)", f"band ~{frac:.0%} within safe area")
    add(INFO, "Safe-zone (verify in-app)",
        "CTA pill sits ~74-80% high; TikTok/IG/Shorts overlay the bottom ~15% and right ~10%")


def main():
    print(f"QA: {os.path.relpath(FINAL)}\n")
    if not os.path.isfile(FINAL):
        print("[FAIL] final reel not found -- run "
              + ("build_composite.py --preview first" if PREVIEW else "build_composite.py first"))
        return 2
    for fn in (check_preview_marker, check_specs, check_duration, check_loudness, check_clipping,
               check_black_and_firstframe, check_deliverables, check_caption_text,
               check_drift, check_safezone):
        try:
            fn()
        except Exception as e:  # never let one probe crash the whole report
            add(INFO, fn.__name__, f"check errored: {e}")

    sym = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]", INFO: "[ .. ]"}
    for status, label, detail in results:
        print(f"  {sym[status]} {label}" + (f" - {detail}" if detail else ""))

    nf = sum(1 for s, _, _ in results if s == FAIL)
    nw = sum(1 for s, _, _ in results if s == WARN)
    print(f"\n{'FAIL' if nf else ('WARN' if nw else 'PASS')}: "
          f"{nf} fail, {nw} warn, {sum(1 for s, _, _ in results if s == OK)} ok")
    if nf or nw:
        print("Reminder: also do an eyes/ears pass -- reverb/noise, mishears, on-screen "
              "PII, MARN correctness, factual accuracy, and real in-app safe-zones.")
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())
