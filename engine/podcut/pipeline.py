"""End-to-end orchestration for both modes.

One-shot entry points, kept for the CLI and callers that don't need a review
checkpoint. Both are thin wrappers over plan.py's two phases (analyze →
plan.json → render), so a one-shot run and a reviewed-but-untouched plan
produce the identical result by construction.
"""
from __future__ import annotations

from typing import Callable, Optional

from . import plan as plan_mod
from .config import Config


def run_podcast(cam1: str, cam2: str, out_path: str, cfg: Config,
                progress: Optional[Callable[[str], None]] = None,
                do_video_use: bool = True, do_hyperframes: bool = True,
                transcript_path: Optional[str] = None,
                behind_subject_captions: bool = False,
                speaker_names: Optional[dict] = None) -> dict:
    """Podcast/interview mode: sync → transcribe → diarize → annotate → fillers →
    switch → render → (video-use) → (HyperFrames)."""
    plan_mod.build_plan_podcast(cam1, cam2, out_path, cfg, progress=progress,
                                transcript_path=transcript_path,
                                do_video_use=do_video_use,
                                do_hyperframes=do_hyperframes,
                                behind_subject_captions=behind_subject_captions,
                                speaker_names=speaker_names)
    return plan_mod.render_from_plan(cfg.workdir, cfg, progress=progress)


def run_single(video: str, out_path: str, cfg: Config,
               progress: Optional[Callable[[str], None]] = None,
               do_video_use: bool = True, do_hyperframes: bool = True,
               transcript_path: Optional[str] = None,
               behind_subject_captions: bool = False,
               speaker_names: Optional[dict] = None) -> dict:
    """Single-speaker mode: transcribe → annotate → fillers → render → (video-use)
    → (HyperFrames)."""
    plan_mod.build_plan_single(video, out_path, cfg, progress=progress,
                               transcript_path=transcript_path,
                               do_video_use=do_video_use,
                               do_hyperframes=do_hyperframes,
                               behind_subject_captions=behind_subject_captions,
                               speaker_names=speaker_names)
    return plan_mod.render_from_plan(cfg.workdir, cfg, progress=progress)
