"""Generate a synthetic two-camera clip for end-to-end testing without real
footage.

We fabricate a back-and-forth "conversation": speaker A is a 240 Hz tone, B a
440 Hz tone. cam1's audio is dominated by A, cam2's by B (as if each camera were
close-mic'd to one person), so per-mic diarization can separate them. cam2 is
delayed by a known offset so we can confirm sync recovers it.

Audio is synthesised in numpy and written to WAV, then muxed onto a solid-color
video — this avoids ffmpeg filter-expression escaping pitfalls on Windows.
"""
from __future__ import annotations

import os
import wave

import numpy as np

from . import ffutil

SR = 16000


def _tone(intervals, freq, n):
    """A `freq` Hz sine active only during the given (start,end) second ranges."""
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float32)
    wave_full = np.sin(2 * np.pi * freq * t).astype(np.float32)
    for s, e in intervals:
        i0, i1 = int(s * SR), int(e * SR)
        # small fades so edges aren't clicky
        seg = wave_full[i0:i1].copy()
        f = min(200, len(seg) // 4) or 1
        ramp = np.linspace(0, 1, f, dtype=np.float32)
        seg[:f] *= ramp
        seg[-f:] *= ramp[::-1]
        sig[i0:i1] += seg
    return sig


def _write_wav(path, data):
    data = np.clip(data, -1, 1)
    pcm = (data * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def make_pair(outdir: str, offset: float = 1.3) -> tuple[str, str]:
    os.makedirs(outdir, exist_ok=True)
    cam1 = os.path.join(outdir, "cam1.mp4")
    cam2 = os.path.join(outdir, "cam2.mp4")
    total = 20

    # A speaks 0.5-4 and 9.5-11 (a question ending ~11); B answers 12-18.
    # brief overlap 8-9; B backchannel-ish blip 8.5-9.2.
    a_int = [(0.5, 4.0), (8.0, 9.0), (9.5, 11.0)]
    b_int = [(4.5, 7.5), (8.5, 9.2), (12.0, 18.0)]

    n = total * SR
    a = _tone(a_int, 240, n)
    b = _tone(b_int, 440, n)

    # Both cameras hear the whole room (strong shared signal for sync), with a
    # per-camera bias toward the near speaker (enough for per-mic diarization).
    cam1_audio = 1.0 * a + 0.6 * b
    cam2_audio_body = 1.0 * b + 0.6 * a
    # delay cam2 by `offset` (pad the front with silence)
    pad = np.zeros(int(offset * SR), dtype=np.float32)
    cam2_audio = np.concatenate([pad, cam2_audio_body])

    w1 = os.path.join(outdir, "_a1.wav")
    w2 = os.path.join(outdir, "_a2.wav")
    _write_wav(w1, cam1_audio)
    _write_wav(w2, cam2_audio)

    ffutil.run([
        "-f", "lavfi", "-i", f"color=c=navy:s=640x360:d={total}:r=30",
        "-i", w1, "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", cam1,
    ])
    ffutil.run([
        "-f", "lavfi", "-i", f"color=c=maroon:s=640x360:d={total + offset}:r=30",
        "-i", w2, "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", cam2,
    ])
    os.remove(w1); os.remove(w2)
    return cam1, cam2


def make_transcript(outdir: str) -> str:
    """Emit a transcript.json aligned to make_pair()'s audio, so the full smart
    pipeline (fillers + question annotation + anticipation + backchannel
    suppression) can be demonstrated offline, with no API key.

    Story: A greets (with an 'um' filler) → B replies → A asks a QUESTION ending
    ~11s → B ANSWERS at 12s (so the anticipation cut should fire) → B drops a
    'yeah' backchannel that must NOT trigger a switch.
    """
    import json

    def w(s, e, text, spk):
        return {"start": round(s, 2), "end": round(e, 2), "text": text,
                "speaker": spk, "confidence": 1.0}

    words = [
        # A greeting (0.5–4.0), contains filler "um"
        w(0.6, 0.9, "So", "A"), w(0.9, 1.1, "um", "A"), w(1.2, 1.5, "I", "A"),
        w(1.5, 1.9, "wanted", "A"), w(1.9, 2.2, "to", "A"), w(2.2, 2.6, "chat", "A"),
        w(2.6, 3.0, "today.", "A"),
        # B reply (4.5–7.5)
        w(4.6, 4.9, "Yeah", "B"), w(4.9, 5.2, "sounds", "B"), w(5.2, 5.6, "great", "B"),
        w(5.6, 6.0, "to", "B"), w(6.0, 6.4, "me.", "B"),
        # B backchannel during A's next bit (8.5–8.9) — must be suppressed
        w(8.5, 8.8, "yeah", "B"),
        # A QUESTION (9.5–11.0), ends with '?'
        w(9.6, 9.9, "What", "A"), w(9.9, 10.2, "do", "A"), w(10.2, 10.4, "you", "A"),
        w(10.4, 10.8, "think", "A"), w(10.8, 11.0, "happens?", "A"),
        # B ANSWER (12.0–18.0), contains filler "uh"
        w(12.1, 12.4, "I", "B"), w(12.4, 12.6, "think", "B"), w(12.6, 12.8, "uh", "B"),
        w(12.8, 13.2, "it", "B"), w(13.2, 13.6, "gets", "B"), w(13.6, 14.1, "better", "B"),
        w(14.1, 14.6, "honestly.", "B"),
    ]
    path = os.path.join(outdir, "transcript.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"provider": "synthetic", "words": words}, f, indent=2)
    return path


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "sample"
    c1, c2 = make_pair(out)
    tpath = make_transcript(out)
    print("wrote", c1, c2, tpath)
