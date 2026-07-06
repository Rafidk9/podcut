"""Runtime configuration and switching-engine tunables.

Editorial behaviour lives in `SwitchConfig`. These are the knobs that decide
whether the auto-edit *feels* human. They are deliberately exposed and
documented so they can be tuned per show.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _load_dotenv() -> None:
    """Minimal .env loader (avoids a python-dotenv dependency)."""
    here = os.path.dirname(__file__)
    for path in (os.path.join(here, "..", ".env"), os.path.join(os.getcwd(), ".env")):
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass
class SwitchConfig:
    # Minimum time we hold on a camera before we're allowed to cut again.
    # Prevents flicker on rapid back-and-forth. Real editors rarely cut <2s.
    min_shot: float = 2.0

    # Anticipation: when a question is aimed at B, cut to B this many seconds
    # BEFORE they start answering, to catch the reaction. This is the move pure
    # audio-following cannot make.
    anticipation_lead: float = 0.35

    # If we anticipate a speaker but they don't actually speak within this
    # window, we bail out (revert to two-shot / current) instead of holding a
    # dead shot. Real turn-taking has 1–2.5s "thinking" pauses between a question
    # and its answer — covering that pause is the whole point of the cut — so
    # this must be generous. (Measured 1.46s on a real Scribe transcript.)
    anticipation_timeout: float = 2.5

    # Utterances shorter than this from the non-active speaker are treated as
    # backchannels ("yeah", "mhm") and do NOT trigger a switch.
    backchannel_max: float = 1.0

    # If both speakers are active (overlap) for longer than this, show the wide
    # / two-shot instead of fighting over who to show.
    overlap_two_shot: float = 0.6

    # During a long single-speaker monologue, cut away to a listener reaction
    # every `monologue_cutaway_every` seconds for `monologue_cutaway_hold`
    # seconds. Set every<=0 to disable.
    monologue_cutaway_every: float = 0.0     # off by default; opinionated
    monologue_cutaway_hold: float = 1.5

    # Do we have a real wide/two-shot camera? If False, overlaps fall back to
    # the primary (louder / question-asker) speaker instead of "wide".
    has_wide_camera: bool = False


@dataclass
class ZoomConfig:
    # Annotation-driven punch-in/out effects, layered onto the HyperFrames render.
    # Reuses the same conversational-structure annotations that drive camera
    # switching — no extra AI call.
    enabled: bool = True

    # Quick punch-in on a landed joke/emphatic moment; holds then eases back.
    punchline_scale: float = 1.10
    punchline_ramp: float = 0.15
    punchline_release: float = 0.25

    # Slow zoom across a long monologue to avoid a static shot feeling dead.
    # >1.0 = zoom IN over the span; set <1.0 for a slow zoom OUT instead.
    monologue_scale: float = 1.06
    monologue_release: float = 1.2

    # Builds through a question, peaking exactly at the anticipation cut — the
    # visual tension-build that pure audio-following can't do.
    anticipation_scale: float = 1.05
    anticipation_hold: float = 0.6
    anticipation_release: float = 0.8

    # Minimum spacing enforced between two accepted zoom events (prevents two
    # effects from fighting back-to-back).
    min_gap: float = 0.3


@dataclass
class FillerConfig:
    remove_fillers: bool = True
    remove_silence: bool = True
    # Gap between consecutive words longer than this (seconds) is "dead air".
    max_pause: float = 0.6
    # Leave a little breathing room around kept speech so cuts aren't clipped.
    pad: float = 0.08
    # Words treated as filler (lowercased, punctuation-stripped).
    filler_words: tuple = ("um", "uh", "erm", "er", "ah", "hmm", "uhh", "umm")


@dataclass
class Providers:
    anthropic_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    elevenlabs_key: str = os.environ.get("ELEVENLABS_API_KEY", "")
    openai_key: str = os.environ.get("OPENAI_API_KEY", "")
    anthropic_model: str = os.environ.get("PODCUT_ANNOTATE_MODEL", "claude-haiku-4-5-20251001")
    # "auto" (Anthropic if key present, else heuristic), "anthropic", "heuristic".
    annotator: str = os.environ.get("PODCUT_ANNOTATOR", "auto")
    video_use_path: str = os.environ.get("VIDEO_USE_PATH", "")
    hyperframes_path: str = os.environ.get("HYPERFRAMES_PATH", "")


@dataclass
class Config:
    switch: SwitchConfig = None
    filler: FillerConfig = None
    zoom: ZoomConfig = None
    providers: Providers = None
    fps: float = 30.0
    workdir: str = ".podcut_work"

    def __post_init__(self):
        self.switch = self.switch or SwitchConfig()
        self.filler = self.filler or FillerConfig()
        self.zoom = self.zoom or ZoomConfig()
        self.providers = self.providers or Providers()
