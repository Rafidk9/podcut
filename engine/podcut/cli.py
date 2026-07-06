"""Command-line interface: `python -m podcut podcast|single …`."""
from __future__ import annotations

import argparse
import json
import sys

from .config import Config, SwitchConfig, FillerConfig, ZoomConfig


def _t_dump(t, path: str) -> None:
    from dataclasses import asdict
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"provider": t.provider, "words": [asdict(w) for w in t.words]}, f, indent=2)


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", default="final.mp4", help="output mp4 path")
    p.add_argument("--transcript", default=None,
                   help="use a pre-made transcript JSON instead of transcribing")
    p.add_argument("--workdir", default=".podcut_work")
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--no-fillers", action="store_true", help="keep filler words")
    p.add_argument("--no-silence", action="store_true", help="keep long pauses")
    p.add_argument("--annotator", choices=["auto", "anthropic", "heuristic"], default="auto",
                   help="conversational-structure annotator (default auto)")
    p.add_argument("--no-video-use", action="store_true")
    p.add_argument("--no-hyperframes", action="store_true")
    p.add_argument("--no-zoom", action="store_true",
                   help="disable annotation-driven punch-in/out zoom effects")
    p.add_argument("--speaker-a", default=None,
                   help="display name for speaker A (cam1) — enables an animated "
                        "lower-third name plate on their first appearance")
    p.add_argument("--speaker-b", default=None,
                   help="display name for speaker B (cam2)")
    p.add_argument("--behind-subject-captions", action="store_true",
                   help="run HyperFrames background removal so captions render BEHIND "
                        "the subject (matte occlusion). Slow (CPU), needs a real person "
                        "in frame — degenerates to on-top captions on footage with none.")


def _build_cfg(a) -> Config:
    cfg = Config(fps=a.fps, workdir=a.workdir,
                 switch=SwitchConfig(), filler=FillerConfig(), zoom=ZoomConfig())
    if getattr(a, "no_fillers", False):
        cfg.filler.remove_fillers = False
    if getattr(a, "no_silence", False):
        cfg.filler.remove_silence = False
    if getattr(a, "min_shot", None):
        cfg.switch.min_shot = a.min_shot
    if getattr(a, "wide", False):
        cfg.switch.has_wide_camera = True
    if getattr(a, "annotator", None):
        cfg.providers.annotator = a.annotator
    if getattr(a, "no_zoom", False):
        cfg.zoom.enabled = False
    return cfg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="podcut", description="AI-assisted video editor")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pod = sub.add_parser("podcast", help="two-camera interview/podcast")
    pod.add_argument("--cam1", required=True)
    pod.add_argument("--cam2", required=True)
    pod.add_argument("--min-shot", type=float, default=2.0)
    pod.add_argument("--wide", action="store_true", help="a wide/two-shot camera exists")
    _common(pod)

    sg = sub.add_parser("single", help="single-speaker talking head")
    sg.add_argument("--video", required=True)
    _common(sg)

    tr = sub.add_parser("transcribe", help="transcribe only (test your key; make a transcript.json)")
    tr.add_argument("--media", required=True, help="audio or video file")
    tr.add_argument("--out", default="transcript.json")
    tr.add_argument("--workdir", default=".podcut_work")

    pl = sub.add_parser("plan", help="analyze only — write plan.json (the reviewable "
                                     "cut list) without rendering anything")
    pl.add_argument("--cam1", help="podcast mode: camera 1 (speaker A near mic)")
    pl.add_argument("--cam2", help="podcast mode: camera 2 (speaker B near mic)")
    pl.add_argument("--video", help="single-speaker mode: the one clip")
    pl.add_argument("--min-shot", type=float, default=2.0)
    pl.add_argument("--wide", action="store_true", help="a wide/two-shot camera exists")
    _common(pl)

    rp = sub.add_parser("render-plan", help="render from a (possibly edited) plan.json")
    rp.add_argument("--workdir", required=True, help="workdir containing plan.json")

    a = ap.parse_args(argv)

    if a.cmd == "transcribe":
        from . import transcribe as _t
        from .config import Providers
        import os as _os
        _os.makedirs(a.workdir, exist_ok=True)
        t = _t.transcribe(a.media, Providers(), a.workdir)
        _t_dump(t, a.out)
        spk = t.speakers()
        preview = " ".join(w.text for w in t.words[:16])
        print(f"provider : {t.provider}")
        print(f"words    : {len(t.words)}")
        print(f"speakers : {spk or '(none detected)'}")
        print(f"preview  : {preview}")
        print(f"written  : {a.out}")
        return 0

    if a.cmd == "render-plan":
        from . import plan as plan_mod
        res = plan_mod.render_from_plan(a.workdir)
        print("\n=== RESULT ===")
        print(json.dumps(res, indent=2))
        return 0

    if a.cmd == "plan":
        from . import plan as plan_mod
        cfg = _build_cfg(a)
        names = {k: v for k, v in (("A", a.speaker_a), ("B", a.speaker_b)) if v}
        if a.cam1 and a.cam2:
            plan = plan_mod.build_plan_podcast(
                a.cam1, a.cam2, a.out, cfg, transcript_path=a.transcript,
                do_video_use=not a.no_video_use, do_hyperframes=not a.no_hyperframes,
                behind_subject_captions=a.behind_subject_captions, speaker_names=names)
        elif a.video:
            plan = plan_mod.build_plan_single(
                a.video, a.out, cfg, transcript_path=a.transcript,
                do_video_use=not a.no_video_use, do_hyperframes=not a.no_hyperframes,
                behind_subject_captions=a.behind_subject_captions, speaker_names=names)
        else:
            ap.error("plan needs either --cam1 + --cam2 (podcast) or --video (single)")
        print("\n=== PLAN ===")
        print(json.dumps({"plan": plan_mod.plan_path(cfg.workdir),
                          "mode": plan["mode"], "segments": len(plan["segments"]),
                          "cuts": len(plan["cuts"]), "zoom_events": len(plan["zoom_events"])},
                         indent=2))
        return 0

    # import here so `--help` works even before heavy deps are installed
    from . import pipeline

    cfg = _build_cfg(a)
    names = {k: v for k, v in (("A", a.speaker_a), ("B", a.speaker_b)) if v}
    if a.cmd == "podcast":
        res = pipeline.run_podcast(a.cam1, a.cam2, a.out, cfg,
                                   do_video_use=not a.no_video_use,
                                   do_hyperframes=not a.no_hyperframes,
                                   transcript_path=a.transcript,
                                   behind_subject_captions=a.behind_subject_captions,
                                   speaker_names=names)
    else:
        res = pipeline.run_single(a.video, a.out, cfg,
                                  do_video_use=not a.no_video_use,
                                  do_hyperframes=not a.no_hyperframes,
                                  transcript_path=a.transcript,
                                  behind_subject_captions=a.behind_subject_captions,
                                  speaker_names=names)
    print("\n=== RESULT ===")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
