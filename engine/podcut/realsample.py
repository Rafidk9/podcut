"""Generate a REAL spoken two-camera sample using ElevenLabs TTS.

Unlike synthetic.py (tones), this produces actual speech so ElevenLabs Scribe
transcription + diarization can be exercised end-to-end. Two voices play a
question (A) then an answer (B); both "cameras" carry the same room audio, with
cam2 delayed by a known offset.

Usage: python -m podcut.realsample <outdir>
Requires ELEVENLABS_API_KEY (read from engine/.env).
"""
from __future__ import annotations

import os
import wave

import numpy as np
import requests

from . import ffutil
from .audio import load_wav_mono
from .config import Providers

SR = 16000
TTS_MODEL = os.environ.get("PODCUT_TTS_MODEL", "eleven_multilingual_v2")

# (voice_id, line). George = male, Sarah = female — easy to diarize.
LINES = [
    ("A", "JBFqnCBsd6RMkjVDRZzb",
     "So, I've actually got a question for you. Where do you think all of this is heading a year from now?"),
    ("B", "EXAVITQu4vr4xnSDxMaL",
     "Honestly, I think it gets a lot better. The tools are improving really fast, and people are just getting started."),
]


def _tts(voice_id: str, text: str, out_mp3: str, key: str) -> str:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
    r = requests.post(url, headers={"xi-api-key": key, "content-type": "application/json"},
                      json={"text": text, "model_id": TTS_MODEL}, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"TTS HTTP {r.status_code}: {r.text[:200]}")
    with open(out_mp3, "wb") as f:
        f.write(r.content)
    return out_mp3


def _to_wav(src: str, dst: str) -> np.ndarray:
    ffutil.extract_audio_wav(src, dst, sr=SR, mono=True)
    data, _ = load_wav_mono(dst)
    return data


def _write_wav(path: str, data: np.ndarray) -> None:
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def make_pair(outdir: str, offset: float = 1.3) -> tuple[str, str]:
    os.makedirs(outdir, exist_ok=True)
    key = Providers().elevenlabs_key
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY not set (put it in engine/.env).")

    clips = []
    for spk, vid, text in LINES:
        mp3 = os.path.join(outdir, f"_tts_{spk}.mp3")
        wav = os.path.join(outdir, f"_tts_{spk}.wav")
        _tts(vid, text, mp3, key)
        clips.append(_to_wav(mp3, wav))

    a, b = clips
    start_a = 1.0
    gap = 1.0
    a_dur = len(a) / SR
    start_b = start_a + a_dur + gap
    total = start_b + len(b) / SR + 2.0

    room = np.zeros(int(total * SR), dtype=np.float32)
    ia = int(start_a * SR); room[ia:ia + len(a)] += a
    ib = int(start_b * SR); room[ib:ib + len(b)] += b

    cam1_audio = room
    cam2_audio = np.concatenate([np.zeros(int(offset * SR), np.float32), room])

    w1 = os.path.join(outdir, "_room1.wav"); _write_wav(w1, cam1_audio)
    w2 = os.path.join(outdir, "_room2.wav"); _write_wav(w2, cam2_audio)

    cam1 = os.path.join(outdir, "cam1.mp4")
    cam2 = os.path.join(outdir, "cam2.mp4")
    ffutil.run(["-f", "lavfi", "-i", f"color=c=navy:s=640x360:r=30:d={total:.2f}",
                "-i", w1, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", cam1])
    ffutil.run(["-f", "lavfi", "-i", f"color=c=maroon:s=640x360:r=30:d={total + offset:.2f}",
                "-i", w2, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", cam2])

    print(f"speaker A speaks ~{start_a:.1f}-{start_a + a_dur:.1f}s, "
          f"speaker B answers ~{start_b:.1f}-{start_b + len(b) / SR:.1f}s, cam2 offset {offset}s")
    return cam1, cam2


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "real_sample"
    c1, c2 = make_pair(out)
    print("wrote", c1, c2)
