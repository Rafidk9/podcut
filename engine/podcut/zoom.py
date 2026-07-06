"""Annotation-driven zoom: the SAME conversational-structure annotations that
drive camera switching also drive punch-in/out zoom effects — a punch-in on a
punchline, a slow zoom through a monologue, and (the direct answer to "can it
detect anticipations to zoom") a tension-building zoom through a question that
peaks exactly at the anticipation cut.

Same design as switching.py: the AI (or heuristic) annotates conversational
structure once; this module deterministically turns those annotations into zoom
keyframes on the EDITED (rendered) timeline. No extra AI call.
"""
from __future__ import annotations

from typing import List

from .config import ZoomConfig
from .models import Annotation, EDL, ZoomEvent, KIND_PUNCHLINE, KIND_MONOLOGUE, KIND_QUESTION


def remap_time_to_edit(t: float, edl: EDL) -> float:
    """Map a time on the ORIGINAL footage timeline to the EDITED (rendered)
    timeline defined by the EDL. If `t` falls inside a cut region (filler /
    dead-air / a camera segment that got dropped), snap forward to when the
    video resumes rather than returning an invalid time."""
    running = 0.0
    for seg in edl.segments:
        if seg.src_start <= t < seg.src_end:
            return running + (t - seg.src_start)
        if t < seg.src_start:
            return running
        running += seg.duration
    return running


def _candidates(annotations: List[Annotation], cfg: ZoomConfig):
    """Yield (priority, ZoomEvent) on the ORIGINAL timeline. Higher priority wins
    when two effects would overlap after remapping."""
    for a in annotations:
        if a.kind == KIND_PUNCHLINE:
            start = a.start
            peak = start + cfg.punchline_ramp
            release = max(peak, a.end)
            end = release + cfg.punchline_release
            yield 2, ZoomEvent(start, peak, release, end, cfg.punchline_scale, "punchline")
        elif a.kind == KIND_QUESTION and a.subject_speaker:
            start, peak = a.start, a.end
            release = peak + cfg.anticipation_hold
            end = release + cfg.anticipation_release
            yield 1, ZoomEvent(start, peak, release, end, cfg.anticipation_scale, "anticipation")
        elif a.kind == KIND_MONOLOGUE:
            start, peak = a.start, a.end
            release = peak
            end = release + cfg.monologue_release
            yield 0, ZoomEvent(start, peak, release, end, cfg.monologue_scale, "monologue")


def compute_zoom_events(annotations: List[Annotation], edl: EDL,
                        cfg: ZoomConfig) -> List[ZoomEvent]:
    """Turn annotations into zoom keyframes on the edited timeline, remapped
    through the EDL, with overlaps resolved by priority (punchline >
    anticipation > monologue) and a minimum gap enforced between events."""
    if not cfg.enabled or not annotations:
        return []

    remapped = []
    for priority, ev in _candidates(annotations, cfg):
        s = remap_time_to_edit(ev.start, edl)
        p = remap_time_to_edit(ev.peak, edl)
        r = remap_time_to_edit(ev.release, edl)
        e = remap_time_to_edit(ev.end, edl)
        if p <= s + 0.02 or e <= r + 0.02:
            continue  # collapsed after remap (e.g. the whole span got cut)
        r = max(r, p)
        e = max(e, r + 0.05)
        remapped.append((priority, ZoomEvent(s, p, r, e, ev.scale, ev.reason)))

    # Greedy interval scheduling: highest priority first, earliest start breaks
    # ties; skip anything that would overlap (within min_gap of) an accepted event.
    remapped.sort(key=lambda pe: (-pe[0], pe[1].start))
    accepted: List[ZoomEvent] = []
    for _, ev in remapped:
        conflict = any(not (ev.end + cfg.min_gap <= a.start or ev.start >= a.end + cfg.min_gap)
                      for a in accepted)
        if not conflict:
            accepted.append(ev)
    accepted.sort(key=lambda e: e.start)
    return accepted
