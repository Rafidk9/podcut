"""Filler-word and dead-air removal.

Produces a list of KEEP intervals on the reference timeline. Everything not in a
keep interval (filler words, long pauses, leading/trailing silence) is dropped.
Works from the transcript; if the transcript is the energy fallback (no real
words) we only remove long pauses.
"""
from __future__ import annotations

from typing import List

from .config import FillerConfig
from .models import Transcript, Interval


def _is_filler(text: str, cfg: FillerConfig) -> bool:
    t = text.strip().strip(".,!?;:").lower()
    return t in cfg.filler_words


def keep_intervals(transcript: Transcript, cfg: FillerConfig,
                   total_duration: float) -> List[Interval]:
    """Return the list of intervals to KEEP (merged, padded)."""
    words = transcript.words
    if not words:
        return [Interval(0.0, total_duration)]

    kept: List[Interval] = []
    for w in words:
        if cfg.remove_fillers and _is_filler(w.text, cfg):
            continue
        kept.append(Interval(max(0.0, w.start - cfg.pad), w.end + cfg.pad))

    if not kept:
        return [Interval(0.0, total_duration)]

    # Merge intervals; a gap larger than max_pause is dead air and stays cut.
    kept.sort(key=lambda x: x.start)
    merged: List[Interval] = [kept[0]]
    for iv in kept[1:]:
        prev = merged[-1]
        gap = iv.start - prev.end
        if gap <= (cfg.max_pause if cfg.remove_silence else 1e9):
            prev.end = max(prev.end, iv.end)
        else:
            merged.append(iv)

    # Clamp to media.
    for iv in merged:
        iv.start = max(0.0, iv.start)
        iv.end = min(total_duration, iv.end)
    return [iv for iv in merged if iv.duration > 0.02]


def removed_report(kept: List[Interval], total: float) -> dict:
    kept_dur = sum(i.duration for i in kept)
    return {
        "total_seconds": round(total, 2),
        "kept_seconds": round(kept_dur, 2),
        "removed_seconds": round(total - kept_dur, 2),
        "removed_pct": round(100 * (total - kept_dur) / total, 1) if total else 0.0,
    }
