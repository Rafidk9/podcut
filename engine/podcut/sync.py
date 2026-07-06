"""Two-camera synchronisation via audio cross-correlation.

Both cameras record scratch audio of the same room. We find the time offset
that best aligns their audio by FFT cross-correlation. This is deterministic,
needs no keys, and is accurate to well under one frame.

Result convention: `offset` is how far cam2 is *behind* cam1, in seconds.
    reference (cam1) time  t   corresponds to   cam2 time  t + offset
i.e. to align cam2 to cam1 you seek `offset` into cam2. `offset` may be
negative (cam2 started first).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

from . import ffutil
from .audio import load_wav_mono


@dataclass
class SyncResult:
    offset: float           # seconds; cam2_time = cam1_time + offset
    confidence: float       # normalized peak height in [0, 1]
    sample_rate: int


def _analysis_signal(path: str, workdir: str, tag: str, sr: int) -> np.ndarray:
    wav = os.path.join(workdir, f"_sync_{tag}.wav")
    ffutil.extract_audio_wav(path, wav, sr=sr, mono=True)
    data, _ = load_wav_mono(wav)
    # Use the energy envelope rather than raw samples: robust to level/EQ
    # differences between the two mics while preserving timing.
    data = np.abs(data)
    if len(data) > sr:  # light smoothing at ~50 Hz envelope
        k = max(1, sr // 100)
        data = np.convolve(data, np.ones(k) / k, mode="same")
    data = data - data.mean()
    return data.astype(np.float32)


def find_offset(cam1: str, cam2: str, workdir: str, sr: int = 4000,
                max_offset: float = 600.0) -> SyncResult:
    """Find the offset aligning cam2 to cam1.

    sr is intentionally low (4 kHz) — envelope timing survives and correlation
    is fast even for long recordings. `max_offset` caps the plausible shift.
    """
    os.makedirs(workdir, exist_ok=True)
    a = _analysis_signal(cam1, workdir, "1", sr)
    b = _analysis_signal(cam2, workdir, "2", sr)

    n = len(a) + len(b)
    N = 1 << (int(np.ceil(np.log2(n))))
    fa = np.fft.rfft(a, N)
    fb = np.fft.rfft(b, N)
    corr = np.fft.irfft(fa * np.conj(fb), N)
    # Lags: index 0..len(a)-1 => positive lag; wrap-around => negative lag.
    corr = np.concatenate((corr[-(len(b) - 1):], corr[:len(a)]))
    lags = np.arange(-(len(b) - 1), len(a))

    # Restrict to plausible offsets.
    max_lag = int(max_offset * sr)
    mask = np.abs(lags) <= max_lag
    corr_m = corr[mask]
    lags_m = lags[mask]

    peak = int(np.argmax(corr_m))
    best_lag = lags_m[peak]
    # Convention: cam2_time = cam1_time + offset. If cam2 is delayed relative to
    # cam1 (an event appears later on cam2), offset is positive. The correlation
    # lag sign is inverted w.r.t. this convention, hence the negation.
    offset = -best_lag / sr

    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    confidence = float(np.clip(corr_m[peak] / denom, 0.0, 1.0))
    return SyncResult(offset=offset, confidence=confidence, sample_rate=sr)
