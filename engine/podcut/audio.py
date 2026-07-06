"""Audio loading and energy-envelope helpers (numpy + stdlib wave only)."""
from __future__ import annotations

import wave
from dataclasses import dataclass

import numpy as np


def load_wav_mono(path: str) -> tuple[np.ndarray, int]:
    """Load a PCM WAV as float32 mono in [-1, 1]."""
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(n)

    if sw == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sw == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sw} bytes")

    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data, sr


@dataclass
class Envelope:
    """Short-time RMS energy envelope sampled at `hop` seconds."""
    energy: np.ndarray      # RMS per frame
    hop: float              # seconds per frame
    sr: int

    def time_at(self, i: int) -> float:
        return i * self.hop

    def index_at(self, t: float) -> int:
        return int(round(t / self.hop))


def rms_envelope(data: np.ndarray, sr: int, frame: float = 0.03, hop: float = 0.01) -> Envelope:
    """Compute an RMS energy envelope. frame/hop in seconds."""
    fl = max(1, int(frame * sr))
    hl = max(1, int(hop * sr))
    if len(data) < fl:
        data = np.pad(data, (0, fl - len(data)))
    n_frames = 1 + (len(data) - fl) // hl
    idx = np.arange(fl)[None, :] + hl * np.arange(n_frames)[:, None]
    frames = data[idx]
    energy = np.sqrt(np.mean(frames.astype(np.float32) ** 2, axis=1) + 1e-12)
    return Envelope(energy=energy, hop=hop, sr=sr)
