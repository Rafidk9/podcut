"""The switching engine: annotations + speaker turns -> camera cut list (EDL).

Design (from the project's guiding idea):
  * A deterministic **timing layer** follows the active speaker.
  * A **semantic layer** (annotations) adds the moves audio-following cannot make
    — chiefly the *anticipation cut*: when a question is aimed at B, cut to B
    just before they answer to catch the reaction.
  * Editorial guards keep it human: minimum shot length, backchannel
    suppression, overlap -> two-shot.

The engine is pure Python (no ffmpeg / no keys) so it is unit-tested directly.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .config import SwitchConfig
from .models import (
    Turn, Annotation, Segment, EDL, Interval, Word, Transcript,
    KIND_QUESTION, KIND_BACKCHANNEL,
)


def remap_transcript_to_edit(transcript: Transcript, edl: EDL) -> Transcript:
    """Remap word timestamps from the ORIGINAL footage timeline onto the EDITED
    (output) timeline defined by the EDL.

    The rendered video concatenates the EDL segments in order, so a segment's
    original range [src_start, src_end] plays at output offset `out_start`. A word
    is placed at out_start + (word.start - src_start); words that fall in removed
    regions (fillers / dead air) are dropped. This is the SAME mapping render.py
    uses for the audio, so captions built from the result line up with the sound.
    """
    maps = []
    out = 0.0
    for s in edl.segments:
        maps.append((s.src_start, s.src_end, out))
        out += s.duration

    new_words = []
    for w in transcript.words:
        for src_s, src_e, out_s in maps:
            if src_s <= w.start < src_e:
                ns = out_s + (w.start - src_s)
                ne = out_s + (min(w.end, src_e) - src_s)
                new_words.append(Word(start=ns, end=max(ns + 0.05, ne), text=w.text,
                                      speaker=w.speaker, confidence=w.confidence))
                break
    return Transcript(words=new_words, provider=transcript.provider + "+edit-remap")

STEP = 0.05  # timeline resolution (seconds)


def _default_map(speakers: List[str]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    cams = ["cam1", "cam2", "cam3", "cam4"]
    for i, s in enumerate(speakers):
        m[s] = cams[min(i, len(cams) - 1)]
    return m


def _suppress_backchannels(turns: List[Turn], anns: List[Annotation],
                           cfg: SwitchConfig) -> List[Turn]:
    """Drop short interjections so we don't cut away for a 'yeah/mhm'."""
    bc_spans = [(a.start, a.end) for a in anns if a.kind == KIND_BACKCHANNEL]

    def is_bc(t: Turn) -> bool:
        if t.duration >= cfg.backchannel_max:
            return False
        for s, e in bc_spans:
            if not (t.end < s or t.start > e):
                return True
        # Heuristic: a short turn wedged between two turns of the other speaker.
        return True if t.duration < cfg.backchannel_max else False

    kept = [t for t in turns if not is_bc(t)]
    return kept or turns


def _active_speaker_at(turns: List[Turn], t: float) -> Optional[str]:
    for tn in turns:
        if tn.start <= t < tn.end:
            return tn.speaker
    return None


def _next_turn_of(turns: List[Turn], speaker: str, after: float,
                  within: float) -> Optional[Turn]:
    best = None
    for tn in turns:
        if tn.speaker == speaker and tn.start >= after - 0.05 and tn.start <= after + within:
            if best is None or tn.start < best.start:
                best = tn
    return best


def build_edl(turns: List[Turn], annotations: List[Annotation],
              keep: List[Interval], duration: float,
              cfg: SwitchConfig,
              speaker_camera: Optional[Dict[str, str]] = None,
              fps: float = 30.0) -> EDL:
    speakers = sorted({t.speaker for t in turns if t.speaker not in ("AB",)}) or ["A"]
    smap = speaker_camera or _default_map(speakers)

    turns_clean = _suppress_backchannels(turns, annotations, cfg)

    n = max(1, int(round(duration / STEP)))
    default_cam = smap.get(speakers[0], "cam1")
    cams: List[Optional[str]] = [None] * n
    reasons: List[str] = ["speaker"] * n

    def idx(t: float) -> int:
        return max(0, min(n, int(round(t / STEP))))

    # --- timing layer: fill each speaker turn with their camera ----------- #
    for tn in turns_clean:
        if tn.speaker == "AB":
            cam = "wide" if cfg.has_wide_camera else None   # None -> gap-split
            reason = "overlap-two-shot"
        else:
            cam = smap.get(tn.speaker)
            reason = "speaker"
        if cam is None:
            continue
        for i in range(idx(tn.start), idx(tn.end)):
            cams[i] = cam
            reasons[i] = reason

    # --- split silent gaps: hold the previous speaker, then pre-roll to the
    #     next one (this is the move that avoids 'islands' and drifts toward
    #     whoever is about to talk) --------------------------------------- #
    i = 0
    while i < n:
        if cams[i] is not None:
            i += 1
            continue
        j = i
        while j < n and cams[j] is None:
            j += 1
        prev_cam = cams[i - 1] if i > 0 else None
        next_cam = cams[j] if j < n else None
        if prev_cam and next_cam:
            mid = (i + j) // 2
            for k in range(i, mid):
                cams[k] = prev_cam; reasons[k] = "hold"
            for k in range(mid, j):
                cams[k] = next_cam; reasons[k] = "preroll"
        elif prev_cam:
            for k in range(i, j):
                cams[k] = prev_cam; reasons[k] = "hold"
        elif next_cam:
            for k in range(i, j):
                cams[k] = next_cam; reasons[k] = "preroll"
        else:
            for k in range(i, j):
                cams[k] = default_cam; reasons[k] = "hold"
        i = j
    cams = [c if c is not None else default_cam for c in cams]

    # --- semantic layer: anticipation cuts on questions ------------------- #
    for a in annotations:
        if a.kind != KIND_QUESTION or not a.subject_speaker:
            continue
        target = a.subject_speaker
        cam = smap.get(target)
        if not cam:
            continue
        answer = _next_turn_of(turns_clean, target, after=a.end,
                               within=cfg.anticipation_timeout)
        if answer is None:
            continue  # they didn't answer in time -> no dead reaction shot
        cut_from = max(a.start, a.end - cfg.anticipation_lead)
        i0 = int(round(cut_from / STEP))
        i1 = int(round(answer.start / STEP))
        for i in range(max(0, i0), min(n, i1)):
            cams[i] = cam
            reasons[i] = "anticipation"

    # --- frames -> raw segments ------------------------------------------ #
    raw = _frames_to_segments(cams, reasons)

    # --- enforce minimum shot length ------------------------------------- #
    raw = _enforce_min_shot(raw, cfg.min_shot)

    # --- confine to KEEP intervals (filler/silence removed) -------------- #
    segs = _apply_keep(raw, keep)

    edl = EDL(segments=segs, fps=fps)
    edl.notes.append(f"{len(speakers)} speakers, map={smap}")
    edl.notes.append(f"{sum(1 for s in segs if s.reason=='anticipation')} anticipation cuts")
    return edl


def _frames_to_segments(cams: List[str], reasons: List[str]) -> List[Segment]:
    segs: List[Segment] = []
    i, n = 0, len(cams)
    while i < n:
        j = i
        while j < n and cams[j] == cams[i]:
            j += 1
        # dominant reason in the run
        reason = "anticipation" if "anticipation" in reasons[i:j] else reasons[i]
        segs.append(Segment(src_start=i * STEP, src_end=j * STEP,
                            camera=cams[i], reason=reason))
        i = j
    return segs


def _enforce_min_shot(segs: List[Segment], min_shot: float) -> List[Segment]:
    if not segs:
        return segs
    segs = [Segment(s.src_start, s.src_end, s.camera, s.reason) for s in segs]
    changed = True
    while changed and len(segs) > 1:
        changed = False
        # Anticipation shots are intentionally brief and flow into the answer;
        # they are exempt from the min-shot merge.
        idx = min(
            (k for k in range(len(segs))
             if segs[k].duration < min_shot and segs[k].reason != "anticipation"),
            key=lambda k: segs[k].duration, default=None,
        )
        if idx is None:
            break
        left = segs[idx - 1] if idx > 0 else None
        right = segs[idx + 1] if idx + 1 < len(segs) else None
        # absorb the short shot into the longer neighbour's camera
        if left and (not right or left.duration >= right.duration):
            segs[idx].camera = left.camera
        elif right:
            segs[idx].camera = right.camera
        segs = _coalesce(segs)
        changed = True
    return segs


def _coalesce(segs: List[Segment]) -> List[Segment]:
    out: List[Segment] = []
    for s in segs:
        if out and out[-1].camera == s.camera:
            out[-1].src_end = s.src_end
            # keep the most meaningful reason for the merged run
            if out[-1].reason in ("hold", "preroll") or s.reason == "anticipation":
                out[-1].reason = s.reason if s.reason != "hold" else out[-1].reason
        else:
            out.append(Segment(s.src_start, s.src_end, s.camera, s.reason))
    return out


def _apply_keep(segs: List[Segment], keep: List[Interval]) -> List[Segment]:
    out: List[Segment] = []
    for s in segs:
        for iv in keep:
            a = max(s.src_start, iv.start)
            b = min(s.src_end, iv.end)
            if b - a > 0.02:
                out.append(Segment(a, b, s.camera, s.reason))
    out.sort(key=lambda s: s.src_start)
    return out
