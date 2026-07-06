"""Two-phase pipeline: analyze → plan.json → (human review) → render.

The plan is the review checkpoint: every decision the AI made — camera
switches, removed cuts, zoom events — is written out BEFORE any ffmpeg encode,
so a human (or the web UI) can tweak it. `render_from_plan` then applies the
edits and finishes the job.

Determinism contract: `render_from_plan` REBUILDS the EDL from the plan's
turns + annotations + (possibly user-modified) keep intervals using the same
switching code — so an untouched plan renders the identical result to the
one-shot pipeline, and a restored cut re-flows the edit exactly as if the
filler pass had never removed it.

Supported edits to plan.json before rendering:
  - cuts[i].restore = true            → put a removed filler/pause back in
  - camera_overrides: [{start,end,camera}]   (source-timeline range → camera)
  - zoom_disabled_reasons: ["punchline"|"anticipation"|"monologue", ...]
  - options.do_hyperframes / options.behind_subject_captions toggles
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Callable, List, Optional

from . import ffutil, sync, transcribe, diarize, annotate, fillers, switching, render, integrations, zoom
from .config import Config, SwitchConfig, ZoomConfig
from .models import EDL, Annotation, Interval, Segment, Transcript, Turn

PLAN_VERSION = 1


def _log(cb: Optional[Callable[[str], None]], msg: str) -> None:
    print(msg)
    if cb:
        cb(msg)


def _dump_transcript(t: Transcript, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"provider": t.provider,
                   "words": [asdict(w) for w in t.words]}, f, indent=2)


def _words_in(transcript: Transcript, start: float, end: float) -> List:
    return [w for w in transcript.words if w.end > start and w.start < end]


def _preview_text(transcript: Transcript, start: float, end: float,
                  max_chars: int = 60) -> str:
    text = " ".join(w.text for w in _words_in(transcript, start, end))
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def _cuts_from_keep(keep: List[Interval], duration: float,
                    transcript: Transcript) -> List[dict]:
    """The complement of the keep intervals, classified for review: what got
    cut, why, and (for fillers) the exact words that were dropped."""
    cuts: List[dict] = []

    def add(start: float, end: float, edge: Optional[str]) -> None:
        if end - start < 0.05:
            return
        words = _words_in(transcript, start, end)
        text = " ".join(w.text for w in words)
        kind = edge or ("filler" if text else "pause")
        cuts.append({"start": round(start, 3), "end": round(end, 3),
                     "kind": kind, "text": text, "restore": False})

    add(0.0, keep[0].start, "lead")
    for a, b in zip(keep, keep[1:]):
        add(a.end, b.start, None)
    add(keep[-1].end, duration, "tail")
    return cuts


def _plan_segments(edl: EDL, transcript: Transcript) -> List[dict]:
    return [{"src_start": round(s.src_start, 3), "src_end": round(s.src_end, 3),
             "camera": s.camera, "reason": s.reason,
             "preview": _preview_text(transcript, s.src_start, s.src_end)}
            for s in edl.segments]


def compute_lower_thirds(edl: EDL, turns: List[Turn], speaker_names: dict,
                         mode: str) -> List[dict]:
    """Name-plate events on the EDITED timeline: one per speaker, at the first
    moment their camera is shown. speaker_names maps transcript labels to
    display names ({"A": "Alice", "B": "Bob"}); speakers without a name get no
    plate. Single mode shows the one name near the start."""
    names = {k: v.strip() for k, v in (speaker_names or {}).items() if v and v.strip()}
    if not names:
        return []
    if mode == "single":
        return [{"time": 0.4, "name": next(iter(names.values()))}]
    speakers: List[str] = []
    for t in turns:
        if t.speaker not in speakers:
            speakers.append(t.speaker)
    cam_of = switching._default_map(speakers)  # noqa: SLF001 — same map build_edl uses
    name_of_cam = {cam_of[s]: names[s] for s in speakers if s in names}
    events, seen, out_t = [], set(), 0.0
    for seg in edl.segments:
        nm = name_of_cam.get(seg.camera)
        if nm and seg.camera not in seen:
            seen.add(seg.camera)
            events.append({"time": round(out_t + 0.2, 3), "name": nm})
        out_t += seg.duration
    return events


def plan_path(workdir: str) -> str:
    return os.path.join(workdir, "plan.json")


def save_plan(plan: dict, workdir: str) -> str:
    p = plan_path(workdir)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
    return p


def load_plan(workdir: str) -> dict:
    with open(plan_path(workdir), "r", encoding="utf-8") as f:
        return json.load(f)


def build_plan_podcast(cam1: str, cam2: str, out_path: str, cfg: Config,
                       progress: Optional[Callable[[str], None]] = None,
                       transcript_path: Optional[str] = None,
                       do_video_use: bool = True, do_hyperframes: bool = True,
                       behind_subject_captions: bool = False,
                       speaker_names: Optional[dict] = None) -> dict:
    """Analysis half of podcast mode: sync → transcribe → diarize → annotate →
    fillers → EDL → zoom preview. No ffmpeg encode. Writes plan.json."""
    work = cfg.workdir
    os.makedirs(work, exist_ok=True)
    if not ffutil.have_ffmpeg():
        raise RuntimeError("ffmpeg/ffprobe not found on PATH.")

    _log(progress, "1/6 syncing cameras (audio cross-correlation)…")
    sr = sync.find_offset(cam1, cam2, work)
    _log(progress, f"    offset = {sr.offset:+.3f}s (confidence {sr.confidence:.2f})")

    dur1 = ffutil.probe_duration(cam1)
    fps = cfg.fps or ffutil.probe_fps(cam1)

    _log(progress, "2/6 transcribing (word timestamps)…")
    if transcript_path:
        transcript = transcribe.from_file(transcript_path)
        _log(progress, f"    loaded transcript ({transcript.provider})")
    else:
        transcript = transcribe.transcribe(cam1, cfg.providers, work)
    _log(progress, f"    provider={transcript.provider}, {len(transcript.words)} words")

    _log(progress, "3/6 diarizing (who speaks when)…")
    if len(transcript.speakers()) >= 2:
        turns = diarize.from_transcript(transcript)
        _log(progress, f"    from transcript labels: {len(turns)} turns")
    else:
        turns = diarize.per_mic(cam1, cam2, work, offset=sr.offset)
        _log(progress, f"    per-mic energy: {len(turns)} turns")

    _log(progress, "4/6 annotating conversational structure…")
    anns = annotate.annotate(transcript, cfg.providers)
    n_q = sum(1 for a in anns if a.kind == "question")
    _log(progress, f"    {len(anns)} spans ({n_q} questions)")

    _log(progress, "5/6 removing fillers / dead air…")
    keep = fillers.keep_intervals(transcript, cfg.filler, dur1)
    report = fillers.removed_report(keep, dur1)
    _log(progress, f"    removed {report['removed_seconds']}s ({report['removed_pct']}%)")

    _log(progress, "6/6 building switching EDL (plan — nothing rendered yet)…")
    edl = switching.build_edl(turns, anns, keep, dur1, cfg.switch, fps=fps)
    edl.to_json(os.path.join(work, "edl.json"))
    _dump_transcript(transcript, os.path.join(work, "transcript.json"))
    _log(progress, f"    {len(edl.segments)} segments; notes: {edl.notes}")

    zoom_events = zoom.compute_zoom_events(anns, edl, cfg.zoom) if cfg.zoom.enabled else []

    plan = {
        "version": PLAN_VERSION,
        "mode": "podcast",
        "inputs": {"cam1": os.path.abspath(cam1), "cam2": os.path.abspath(cam2),
                   "out": os.path.abspath(out_path)},
        "fps": fps, "duration": dur1,
        "sync": {"offset": sr.offset, "confidence": sr.confidence},
        "switch_cfg": asdict(cfg.switch), "zoom_cfg": asdict(cfg.zoom),
        "turns": [asdict(t) for t in turns],
        "annotations": [asdict(a) for a in anns],
        "keep": [{"start": iv.start, "end": iv.end} for iv in keep],
        "cuts": _cuts_from_keep(keep, dur1, transcript),
        "segments": _plan_segments(edl, transcript),
        "zoom_events": [asdict(e) for e in zoom_events],
        "camera_overrides": [],
        "zoom_disabled_reasons": [],
        "filler_report": report,
        "transcript_provider": transcript.provider,
        "options": {"do_video_use": do_video_use, "do_hyperframes": do_hyperframes,
                    "behind_subject_captions": behind_subject_captions,
                    "speaker_names": speaker_names or {}},
    }
    save_plan(plan, work)
    _log(progress, f"plan written: {plan_path(work)} — review, then render.")
    return plan


def build_plan_single(video: str, out_path: str, cfg: Config,
                      progress: Optional[Callable[[str], None]] = None,
                      transcript_path: Optional[str] = None,
                      do_video_use: bool = True, do_hyperframes: bool = True,
                      behind_subject_captions: bool = False,
                      speaker_names: Optional[dict] = None) -> dict:
    """Analysis half of single-speaker mode. No ffmpeg encode. Writes plan.json."""
    work = cfg.workdir
    os.makedirs(work, exist_ok=True)
    if not ffutil.have_ffmpeg():
        raise RuntimeError("ffmpeg/ffprobe not found on PATH.")

    dur = ffutil.probe_duration(video)
    fps = cfg.fps or ffutil.probe_fps(video)

    _log(progress, "1/3 transcribing…")
    transcript = (transcribe.from_file(transcript_path) if transcript_path
                  else transcribe.transcribe(video, cfg.providers, work))
    _dump_transcript(transcript, os.path.join(work, "transcript.json"))

    _log(progress, "2/3 annotating conversational structure (for zoom cues)…")
    anns = annotate.annotate(transcript, cfg.providers) if cfg.zoom.enabled else []

    _log(progress, "3/3 removing fillers / dead air (plan — nothing rendered yet)…")
    keep = fillers.keep_intervals(transcript, cfg.filler, dur)
    report = fillers.removed_report(keep, dur)
    _log(progress, f"    removed {report['removed_seconds']}s ({report['removed_pct']}%)")

    keep_edl = EDL(segments=[Segment(iv.start, iv.end, "v") for iv in keep], fps=fps)
    zoom_events = zoom.compute_zoom_events(anns, keep_edl, cfg.zoom) if cfg.zoom.enabled else []

    plan = {
        "version": PLAN_VERSION,
        "mode": "single",
        "inputs": {"video": os.path.abspath(video), "out": os.path.abspath(out_path)},
        "fps": fps, "duration": dur,
        "switch_cfg": asdict(cfg.switch), "zoom_cfg": asdict(cfg.zoom),
        "turns": [], "annotations": [asdict(a) for a in anns],
        "keep": [{"start": iv.start, "end": iv.end} for iv in keep],
        "cuts": _cuts_from_keep(keep, dur, transcript),
        "segments": _plan_segments(keep_edl, transcript),
        "zoom_events": [asdict(e) for e in zoom_events],
        "camera_overrides": [],
        "zoom_disabled_reasons": [],
        "filler_report": report,
        "transcript_provider": transcript.provider,
        "options": {"do_video_use": do_video_use, "do_hyperframes": do_hyperframes,
                    "behind_subject_captions": behind_subject_captions,
                    "speaker_names": speaker_names or {}},
    }
    save_plan(plan, work)
    _log(progress, f"plan written: {plan_path(work)} — review, then render.")
    return plan


def _merged_keep(plan: dict) -> List[Interval]:
    """Keep intervals with any user-restored cuts merged back in."""
    keep = [Interval(iv["start"], iv["end"]) for iv in plan["keep"]]
    keep += [Interval(c["start"], c["end"]) for c in plan.get("cuts", [])
             if c.get("restore")]
    keep.sort(key=lambda iv: iv.start)
    merged = [keep[0]]
    for iv in keep[1:]:
        if iv.start <= merged[-1].end + 0.001:
            merged[-1].end = max(merged[-1].end, iv.end)
        else:
            merged.append(iv)
    return merged


def _apply_camera_overrides(edl: EDL, overrides: List[dict]) -> EDL:
    """Force the camera on every segment overlapping an override's source-time
    range, splitting segments at the override edges so untouched parts of a
    long shot keep their original camera."""
    for ov in overrides:
        out: List[Segment] = []
        for s in edl.segments:
            lo, hi = max(s.src_start, ov["start"]), min(s.src_end, ov["end"])
            if hi - lo <= 0.01:                       # no overlap
                out.append(s)
                continue
            if lo - s.src_start > 0.01:
                out.append(Segment(s.src_start, lo, s.camera, s.reason))
            out.append(Segment(lo, hi, ov["camera"], "user_override"))
            if s.src_end - hi > 0.01:
                out.append(Segment(hi, s.src_end, s.camera, s.reason))
        edl.segments = out
    # Merge same-camera neighbours, but ONLY when time-contiguous: this EDL
    # already has the keep cuts applied, so switching._coalesce would bridge a
    # removed gap and put cut material back into the output.
    merged: List[Segment] = []
    for s in edl.segments:
        if (merged and merged[-1].camera == s.camera
                and abs(merged[-1].src_end - s.src_start) < 0.01):
            merged[-1].src_end = s.src_end
        else:
            merged.append(s)
    edl.segments = merged
    return edl


def render_from_plan(workdir: str, cfg: Optional[Config] = None,
                     progress: Optional[Callable[[str], None]] = None) -> dict:
    """Render half: load plan.json (with any user edits), rebuild the edit
    deterministically, then encode + captions. Mirrors the one-shot pipeline's
    output and report exactly when the plan is untouched."""
    plan = load_plan(workdir)
    cfg = cfg or Config(workdir=workdir)
    cfg.workdir = workdir
    switch_cfg = SwitchConfig(**plan["switch_cfg"])
    zoom_cfg = ZoomConfig(**plan["zoom_cfg"])
    opts = plan.get("options", {})
    out_path = plan["inputs"]["out"]
    fps = plan["fps"]
    dur = plan["duration"]

    transcript = transcribe.from_file(os.path.join(workdir, "transcript.json"))
    turns = [Turn(**t) for t in plan["turns"]]
    anns = [Annotation(**a) for a in plan["annotations"]]
    keep = _merged_keep(plan)
    n_restored = sum(1 for c in plan.get("cuts", []) if c.get("restore"))
    if n_restored:
        _log(progress, f"    review: {n_restored} cut(s) restored")

    if plan["mode"] == "podcast":
        edl = switching.build_edl(turns, anns, keep, dur, switch_cfg, fps=fps)
    else:
        edl = EDL(segments=[Segment(iv.start, iv.end, "v") for iv in keep], fps=fps)
    if plan.get("camera_overrides"):
        _log(progress, f"    review: {len(plan['camera_overrides'])} camera override(s)")
        edl = _apply_camera_overrides(edl, plan["camera_overrides"])
    edl.to_json(os.path.join(workdir, "edl.json"))

    _log(progress, "rendering…")
    if plan["mode"] == "podcast":
        cams = {"cam1": plan["inputs"]["cam1"], "cam2": plan["inputs"]["cam2"]}
        offsets = {"cam1": 0.0, "cam2": plan["sync"]["offset"]}
        render.render(edl, cams, workdir, out_path, camera_offsets=offsets,
                      master_audio=plan["inputs"]["cam1"], master_offset=0.0, fps=fps)
    else:
        render.render_single([Interval(s.src_start, s.src_end) for s in edl.segments],
                             plan["inputs"]["video"], workdir, out_path, fps=fps)

    final = out_path
    staging = None
    if opts.get("do_video_use", True):
        _log(progress, "+  staging edit for video-use (interactive)…")
        staging = integrations.stage_for_video_use(final, cfg.providers,
                                                   os.path.join(workdir, "video_use"))

    disabled = set(plan.get("zoom_disabled_reasons", []))
    zoom_events = (zoom.compute_zoom_events(anns, edl, zoom_cfg)
                   if zoom_cfg.enabled else [])
    zoom_events = [e for e in zoom_events if e.reason not in disabled]
    if zoom_cfg.enabled:
        _log(progress, f"    {len(zoom_events)} zoom events "
                       f"({', '.join(e.reason for e in zoom_events) or 'none'})")

    matte_path = None
    do_hyperframes = opts.get("do_hyperframes", True)
    if do_hyperframes and opts.get("behind_subject_captions"):
        _log(progress, "+  removing background for behind-subject captions "
                       "(slow, CPU, needs a real person in frame)…")
        try:
            matte_path = integrations.remove_background(
                final, os.path.join(workdir, "matte.webm"), cfg.providers)
        except Exception as e:                      # noqa: BLE001
            print(f"[matte] failed ({e}); captions will render on top instead of behind subject.")

    lower_thirds = compute_lower_thirds(edl, turns,
                                        opts.get("speaker_names") or {}, plan["mode"])
    if lower_thirds:
        _log(progress, f"    {len(lower_thirds)} lower-third(s): "
                       f"{', '.join(e['name'] for e in lower_thirds)}")

    if do_hyperframes:
        _log(progress, "+  adding captions (HyperFrames / ffmpeg)…")
        # captions must use timings on the EDITED timeline, not the original
        cap_transcript = switching.remap_transcript_to_edit(transcript, edl)
        final = integrations.add_captions(final, out_path.replace(".mp4", ".captioned.mp4"),
                                          cap_transcript, cfg.providers, workdir,
                                          zoom_events=zoom_events, matte=matte_path,
                                          lower_thirds=lower_thirds)

    result = {
        "mode": plan["mode"], "output": final, "edl": os.path.join(workdir, "edl.json"),
        "segments": len(edl.segments),
        "anticipation_cuts": sum(1 for s in edl.segments if s.reason == "anticipation"),
        "zoom_events": len(zoom_events), "behind_subject_captions": bool(matte_path),
        "filler_report": plan["filler_report"], "transcript_provider": plan["transcript_provider"],
        "captioned": bool(do_hyperframes), "video_use_staging": staging,
        "notes": edl.notes, "restored_cuts": n_restored,
        "camera_overrides": len(plan.get("camera_overrides", [])),
    }
    if plan["mode"] == "podcast":
        result["sync_offset"] = plan["sync"]["offset"]
        result["sync_confidence"] = plan["sync"]["confidence"]
    with open(os.path.join(workdir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    _log(progress, "done.")
    return result
