"""Who is speaking, when.

Two strategies, in order of reliability:

1. `per_mic` — each camera is close to one person, so its scratch audio is
   dominated by that person. We compare the two energy envelopes frame-by-frame
   and assign the active speaker. This needs no ML and, with decent mic
   separation, is very reliable. THIS IS THE RECOMMENDED CAPTURE SETUP.

2. `from_transcript` — use speaker labels already produced by a diarizing
   transcription provider (ElevenLabs Scribe / pyannote).

Both return a list of `Turn` on the reference (cam1) timeline.
"""
from __future__ import annotations

import os
from typing import List, Optional

import numpy as np

from . import ffutil
from .audio import load_wav_mono, rms_envelope
from .models import Turn, Transcript


def _clean_turns(active: np.ndarray, hop: float, speakers: List[str],
                 min_dur: float = 0.25) -> List[Turn]:
    """Convert a per-frame speaker index array (-1 = silence) into Turns,
    dropping runs shorter than `min_dur`."""
    turns: List[Turn] = []
    i = 0
    n = len(active)
    while i < n:
        spk = active[i]
        j = i
        while j < n and active[j] == spk:
            j += 1
        if spk >= 0:
            start, end = i * hop, j * hop
            if end - start >= min_dur:
                turns.append(Turn(start=start, end=end, speaker=speakers[spk]))
        i = j
    # Merge adjacent same-speaker turns separated by a tiny gap.
    merged: List[Turn] = []
    for t in turns:
        if merged and merged[-1].speaker == t.speaker and t.start - merged[-1].end < 0.35:
            merged[-1].end = t.end
        else:
            merged.append(t)
    return merged


def per_mic(cam1: str, cam2: str, workdir: str, offset: float,
            hop: float = 0.05, rel_margin: float = 1.4,
            floor_percentile: float = 55.0) -> List[Turn]:
    """Assign speakers by comparing the two cameras' close-mic energy.

    `offset` aligns cam2 onto cam1's timeline (from sync). `rel_margin`: one
    mic must exceed the other by this factor to 'win' a frame; otherwise it is
    overlap (encoded as speaker "AB"). Frames below the noise floor are silence.
    """
    os.makedirs(workdir, exist_ok=True)
    sr = 16000
    w1 = ffutil.extract_audio_wav(cam1, os.path.join(workdir, "_dia1.wav"), sr=sr)
    w2 = ffutil.extract_audio_wav(cam2, os.path.join(workdir, "_dia2.wav"), sr=sr)
    d1, _ = load_wav_mono(w1)
    d2, _ = load_wav_mono(w2)

    # Align cam2 to cam1 timeline by padding/trimming the front by `offset`.
    shift = int(round(offset * sr))
    if shift > 0:
        d2 = d2[shift:] if shift < len(d2) else np.zeros(0, np.float32)
    elif shift < 0:
        d2 = np.concatenate([np.zeros(-shift, np.float32), d2])

    e1 = rms_envelope(d1, sr, hop=hop).energy
    e2 = rms_envelope(d2, sr, hop=hop).energy
    n = min(len(e1), len(e2))
    e1, e2 = e1[:n], e2[:n]

    # Per-mic noise floor.
    f1 = np.percentile(e1, floor_percentile)
    f2 = np.percentile(e2, floor_percentile)
    a1 = e1 > f1
    a2 = e2 > f2

    active = np.full(n, -1, dtype=int)   # -1 silence, 0=A, 1=B, 2=AB(overlap)
    speakers = ["A", "B", "AB"]
    for i in range(n):
        if not a1[i] and not a2[i]:
            continue
        if a1[i] and not a2[i]:
            active[i] = 0
        elif a2[i] and not a1[i]:
            active[i] = 1
        else:
            # both above floor: decide by ratio, else overlap
            if e1[i] >= e2[i] * rel_margin:
                active[i] = 0
            elif e2[i] >= e1[i] * rel_margin:
                active[i] = 1
            else:
                active[i] = 2
    return _clean_turns(active, hop, speakers)


def from_transcript(t: Transcript) -> List[Turn]:
    """Build turns from speaker-labeled transcript words."""
    turns: List[Turn] = []
    for w in t.words:
        spk = w.speaker or "A"
        if turns and turns[-1].speaker == spk and w.start - turns[-1].end < 0.5:
            turns[-1].end = w.end
        else:
            turns.append(Turn(start=w.start, end=w.end, speaker=spk))
    return turns


def speaker_at(turns: List[Turn], t: float) -> Optional[str]:
    for tn in turns:
        if tn.start <= t < tn.end:
            return tn.speaker
    return None
