"""Render an EDL to a final MP4 with ffmpeg.

For each segment we take *video* from the chosen camera and *audio* from a
continuous master track (audio does not switch with the picture — that's how
real multicam works). Segments are normalised to a common size/fps so they
concatenate cleanly.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Dict, Optional

from . import ffutil
from .models import EDL

# HDR (PQ/HLG, BT.2020) phone footage must be tone-mapped to SDR before an SDR
# encode; without this the output carries wrong colour and players render it
# flat/desaturated. Prepended to the -vf chain for HDR inputs only.
# ffprobe colour names → zscale option names.
_ZSCALE_TRANSFER = {"smpte2084": "smpte2084", "arib-std-b67": "arib-std-b67"}
_ZSCALE_MATRIX = {"bt2020nc": "2020_ncl", "bt2020c": "2020_cl"}
_ZSCALE_PRIMARIES = {"bt2020": "2020"}


def hdr_to_sdr_vf(color: dict) -> str:
    """Tone-map chain for one HDR input. Input colour params are passed to
    zscale explicitly (from ffprobe) because zscale errors with "no path
    between colorspaces" when frames are untagged; missing fields fall back to
    the common phone defaults (HLG / BT.2020 / limited range)."""
    tin = _ZSCALE_TRANSFER.get(color["color_transfer"], "arib-std-b67")
    m_in = _ZSCALE_MATRIX.get(color["color_space"], "2020_ncl")
    pin = _ZSCALE_PRIMARIES.get(color["color_primaries"], "2020")
    rin = "full" if color["color_range"] == "pc" else "limited"
    return (f"zscale=tin={tin}:min={m_in}:pin={pin}:rin={rin}:t=linear:npl=100,"
            "format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
            "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")

# Every libx264 encode tags its output explicitly so players never have to guess.
# setparams stamps the frames so x264 writes the tags into the bitstream VUI —
# the -color_* output flags alone end up container-only and are LOST when the
# concat step stream-copies segments (verified with ffprobe on ffmpeg 8.1.2).
SDR_TAG_VF = "setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709"
SDR_COLOR_ARGS = ["-color_primaries", "bt709", "-color_trc", "bt709",
                  "-colorspace", "bt709", "-color_range", "tv"]


def _probe_size(path: str) -> tuple[int, int]:
    out = subprocess.run(
        [__import__("shutil").which("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", path],
        check=True, capture_output=True, text=True,
    ).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


def render(edl: EDL, cameras: Dict[str, str], workdir: str, out_path: str,
           camera_offsets: Optional[Dict[str, float]] = None,
           master_audio: Optional[str] = None, master_offset: float = 0.0,
           fps: Optional[float] = None) -> str:
    """cameras: {"cam1": path, "cam2": path, ...}. camera_offsets map a
    reference-timeline time to each camera's own time (cam_time = ref + offset).
    master_audio defaults to cam1's audio."""
    if not edl.segments:
        raise ValueError("EDL has no segments to render.")
    os.makedirs(workdir, exist_ok=True)
    camera_offsets = camera_offsets or {}
    ref_cam = cameras.get("cam1") or next(iter(cameras.values()))
    master_audio = master_audio or ref_cam
    W, H = _probe_size(ref_cam)
    fps = fps or edl.fps

    seg_dir = os.path.join(workdir, "segments")
    os.makedirs(seg_dir, exist_ok=True)
    list_path = os.path.join(seg_dir, "concat.txt")
    seg_files = []
    cam_hdr_vf = {name: hdr_to_sdr_vf(ffutil.probe_color(path))
                  for name, path in cameras.items() if ffutil.is_hdr(path)}

    with open(list_path, "w", encoding="utf-8") as lf:
        for k, s in enumerate(edl.segments):
            cam_path = cameras.get(s.camera) or ref_cam
            v_off = camera_offsets.get(s.camera, 0.0)
            v_start = max(0.0, s.src_start + v_off)
            a_start = max(0.0, s.src_start + master_offset)
            dur = s.duration
            seg_out = os.path.join(seg_dir, f"seg_{k:05d}.mp4")

            vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                  f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}")
            if s.camera in cam_hdr_vf:
                vf = cam_hdr_vf[s.camera] + "," + vf
            vf += "," + SDR_TAG_VF
            ffutil.run([
                "-ss", f"{v_start:.3f}", "-i", cam_path,
                "-ss", f"{a_start:.3f}", "-i", master_audio,
                "-t", f"{dur:.3f}",
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", *SDR_COLOR_ARGS,
                "-c:a", "aac", "-ar", "48000", "-ac", "2",
                "-video_track_timescale", "90000",
                seg_out,
            ])
            seg_files.append(seg_out)
            lf.write(f"file '{os.path.abspath(seg_out)}'\n")

    # Concatenate (streams share params, so stream-copy works).
    try:
        ffutil.run(["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path])
    except subprocess.CalledProcessError:
        # Fallback: re-encode the concatenation (segments are already SDR bt709).
        ffutil.run(["-f", "concat", "-safe", "0", "-i", list_path,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    *SDR_COLOR_ARGS, "-c:a", "aac", out_path])
    return out_path


def render_single(keep, source: str, workdir: str, out_path: str,
                  fps: Optional[float] = None) -> str:
    """Single-speaker render: just concat the KEEP intervals of one source."""
    os.makedirs(workdir, exist_ok=True)
    seg_dir = os.path.join(workdir, "segments")
    os.makedirs(seg_dir, exist_ok=True)
    W, H = _probe_size(source)
    fps = fps or ffutil.probe_fps(source)
    hdr_vf = hdr_to_sdr_vf(ffutil.probe_color(source)) if ffutil.is_hdr(source) else None
    list_path = os.path.join(seg_dir, "concat.txt")
    with open(list_path, "w", encoding="utf-8") as lf:
        for k, iv in enumerate(keep):
            seg_out = os.path.join(seg_dir, f"seg_{k:05d}.mp4")
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                  f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}")
            if hdr_vf:
                vf = hdr_vf + "," + vf
            vf += "," + SDR_TAG_VF
            ffutil.run([
                "-ss", f"{iv.start:.3f}", "-i", source, "-t", f"{iv.duration:.3f}",
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                *SDR_COLOR_ARGS,
                "-c:a", "aac", "-ar", "48000", "-ac", "2",
                "-video_track_timescale", "90000", seg_out,
            ])
            lf.write(f"file '{os.path.abspath(seg_out)}'\n")
    try:
        ffutil.run(["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path])
    except subprocess.CalledProcessError:
        ffutil.run(["-f", "concat", "-safe", "0", "-i", list_path,
                    "-c:v", "libx264", "-preset", "veryfast", *SDR_COLOR_ARGS,
                    "-c:a", "aac", out_path])
    return out_path
