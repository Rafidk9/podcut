"""Transcription with pluggable providers and a local, key-free fallback.

Everything downstream needs word-level timestamps. Order of preference:
  1. ElevenLabs Scribe   (word ts + diarization)   — ELEVENLABS_API_KEY
  2. OpenAI Whisper API   (word ts)                 — OPENAI_API_KEY
  3. faster-whisper       (local, word ts)          — pip install faster-whisper
  4. energy fallback      (no words, only VAD)       — always available

The fallback produces pseudo-"words" from voiced regions so the pipeline still
runs (filler removal by text is skipped, switching uses diarization energy).
"""
from __future__ import annotations

import os
from typing import List

from .config import Providers
from .models import Word, Transcript
from . import ffutil
from .audio import load_wav_mono, rms_envelope


def from_file(path: str) -> Transcript:
    """Load a pre-made transcript JSON ({'provider','words':[...]}). Lets the
    full pipeline run offline, or reuse a transcript from a previous run."""
    import json  # noqa: PLC0415
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    words = [Word(start=float(x["start"]), end=float(x["end"]), text=x["text"],
                  speaker=x.get("speaker"), confidence=float(x.get("confidence", 1.0)))
             for x in d.get("words", [])]
    return Transcript(words=words, provider=d.get("provider", "file"))


def transcribe(media: str, providers: Providers, workdir: str) -> Transcript:
    if providers.elevenlabs_key:
        try:
            return _elevenlabs(media, providers, workdir)
        except Exception as e:                      # noqa: BLE001
            print(f"[transcribe] ElevenLabs failed ({e}); trying next provider.")
    if providers.openai_key:
        try:
            return _openai_whisper(media, providers, workdir)
        except Exception as e:                      # noqa: BLE001
            print(f"[transcribe] OpenAI Whisper failed ({e}); trying next provider.")
    try:
        return _faster_whisper(media, workdir)
    except Exception as e:                          # noqa: BLE001
        print(f"[transcribe] faster-whisper unavailable ({e}); using energy fallback.")
    return _energy_fallback(media, workdir)


def _elevenlabs(media: str, providers: Providers, workdir: str) -> Transcript:
    import math  # noqa: PLC0415
    import requests  # noqa: PLC0415

    model = os.environ.get("PODCUT_ELEVENLABS_MODEL", "scribe_v1")  # or scribe_v2
    data_fields = {
        "model_id": model,
        "diarize": "true",
        "timestamps_granularity": "word",
        "tag_audio_events": "false",
    }
    num_speakers = os.environ.get("PODCUT_NUM_SPEAKERS")
    if num_speakers:
        data_fields["num_speakers"] = num_speakers

    audio = ffutil.extract_audio_wav(media, os.path.join(workdir, "_stt.wav"), sr=16000)
    with open(audio, "rb") as f:
        resp = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": providers.elevenlabs_key},
            data=data_fields,
            files={"file": f},
            timeout=1200,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()

    words: List[Word] = []
    for w in data.get("words", []):
        # keep only spoken words; skip spacing / audio_event entries
        if w.get("type", "word") != "word":
            continue
        logprob = w.get("logprob")
        conf = float(math.exp(min(0.0, logprob))) if isinstance(logprob, (int, float)) else 1.0
        words.append(Word(
            start=float(w["start"]), end=float(w["end"]), text=w["text"],
            speaker=_norm_speaker(w.get("speaker_id")),
            confidence=conf,
        ))
    if not words:
        raise RuntimeError("ElevenLabs returned no word-level results")
    return Transcript(words=words, provider=f"elevenlabs:{model}")


def _openai_whisper(media: str, providers: Providers, workdir: str) -> Transcript:
    from openai import OpenAI  # noqa: PLC0415

    audio = ffutil.extract_audio_wav(media, os.path.join(workdir, "_stt.wav"), sr=16000)
    client = OpenAI(api_key=providers.openai_key)
    with open(audio, "rb") as f:
        r = client.audio.transcriptions.create(
            model="whisper-1", file=f, response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    words = [Word(start=float(w.start), end=float(w.end), text=w.word)
             for w in getattr(r, "words", [])]
    return Transcript(words=words, provider="openai-whisper")


def _faster_whisper(media: str, workdir: str) -> Transcript:
    from faster_whisper import WhisperModel  # noqa: PLC0415

    audio = ffutil.extract_audio_wav(media, os.path.join(workdir, "_stt.wav"), sr=16000)
    model = WhisperModel(os.environ.get("PODCUT_WHISPER_MODEL", "base"),
                         device="auto", compute_type="int8")
    segments, _ = model.transcribe(audio, word_timestamps=True)
    words: List[Word] = []
    for seg in segments:
        for w in (seg.words or []):
            words.append(Word(start=float(w.start), end=float(w.end), text=w.word.strip()))
    return Transcript(words=words, provider="faster-whisper")


def _energy_fallback(media: str, workdir: str) -> Transcript:
    """No transcript available — emit voiced regions as placeholder words so the
    rest of the pipeline (diarization/switching) still functions."""
    audio = ffutil.extract_audio_wav(media, os.path.join(workdir, "_stt.wav"), sr=16000)
    data, sr = load_wav_mono(audio)
    env = rms_envelope(data, sr, hop=0.05)
    floor = float(__import__("numpy").percentile(env.energy, 55))
    words: List[Word] = []
    voiced = env.energy > floor
    i, n = 0, len(voiced)
    while i < n:
        if voiced[i]:
            j = i
            while j < n and voiced[j]:
                j += 1
            words.append(Word(start=i * env.hop, end=j * env.hop, text="[speech]"))
            i = j
        else:
            i += 1
    return Transcript(words=words, provider="energy-fallback")


def _norm_speaker(sid) -> str:
    if sid is None:
        return "A"
    s = str(sid)
    # Map arbitrary provider ids to A/B/C...
    mapping = _norm_speaker._map  # type: ignore[attr-defined]
    if s not in mapping:
        mapping[s] = chr(ord("A") + len(mapping))
    return mapping[s]


_norm_speaker._map = {}  # type: ignore[attr-defined]
