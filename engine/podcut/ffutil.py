"""Thin wrappers around ffmpeg / ffprobe."""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import List


class FFmpegNotFound(RuntimeError):
    pass


def _bin(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise FFmpegNotFound(
            f"'{name}' not found on PATH. Install ffmpeg (winget install Gyan.FFmpeg) "
            f"and restart the shell so PATH refreshes."
        )
    return path


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run(args: List[str], quiet: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with the given args (the 'ffmpeg' binary is prepended)."""
    cmd = [_bin("ffmpeg"), "-y", "-hide_banner"]
    if quiet:
        cmd += ["-loglevel", "error"]
    cmd += args
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def probe_duration(path: str) -> float:
    out = subprocess.run(
        [_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        check=True, capture_output=True, text=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def probe_color(path: str) -> dict:
    """Colour metadata of the first video stream (empty strings when untagged)."""
    out = subprocess.run(
        [_bin("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries",
         "stream=pix_fmt,color_range,color_space,color_transfer,color_primaries",
         "-of", "json", path],
        check=True, capture_output=True, text=True,
    ).stdout
    s = json.loads(out)["streams"][0]
    return {k: s.get(k, "") or "" for k in
            ("pix_fmt", "color_range", "color_space", "color_transfer", "color_primaries")}


def is_hdr(path: str) -> bool:
    """True when the clip is HDR (PQ/HLG transfer or BT.2020 primaries) — typical
    of modern phone footage. Such input must be tone-mapped to SDR bt709 before
    an SDR encode, or players colour-manage the result wrong (flat/desaturated)."""
    c = probe_color(path)
    return (c["color_transfer"] in ("smpte2084", "arib-std-b67")
            or c["color_primaries"] == "bt2020"
            or c["color_space"] in ("bt2020nc", "bt2020c"))


def probe_fps(path: str) -> float:
    out = subprocess.run(
        [_bin("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "json", path],
        check=True, capture_output=True, text=True,
    ).stdout
    rate = json.loads(out)["streams"][0]["r_frame_rate"]
    num, den = rate.split("/")
    den = float(den) or 1.0
    return float(num) / den


def extract_audio_wav(src: str, dst: str, sr: int = 16000, mono: bool = True) -> str:
    """Extract audio to a PCM WAV for analysis (sync, VAD, energy)."""
    args = ["-i", src, "-vn", "-ac", "1" if mono else "2", "-ar", str(sr),
            "-c:a", "pcm_s16le", dst]
    run(args)
    return dst
