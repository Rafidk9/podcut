"""Core data structures shared across the pipeline.

Time convention: everything is in **seconds on the reference (cam1) timeline**.
cam2 is mapped onto this timeline via a single `sync_offset` (see sync.py), so
downstream stages never worry about the raw camera offsets.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json


@dataclass
class Word:
    """One transcribed word with timing and (optional) speaker label."""
    start: float
    end: float
    text: str
    speaker: Optional[str] = None      # e.g. "A" / "B"; None if unknown
    confidence: float = 1.0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class Transcript:
    words: List[Word] = field(default_factory=list)
    provider: str = "unknown"

    @property
    def duration(self) -> float:
        return self.words[-1].end if self.words else 0.0

    def speakers(self) -> List[str]:
        seen = []
        for w in self.words:
            if w.speaker and w.speaker not in seen:
                seen.append(w.speaker)
        return seen


@dataclass
class Turn:
    """A contiguous stretch where one speaker is active."""
    start: float
    end: float
    speaker: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


# Conversational-structure labels the AI (or heuristic fallback) produces.
KIND_STATEMENT = "statement"
KIND_QUESTION = "question"
KIND_ANSWER = "answer"
KIND_MONOLOGUE = "monologue"
KIND_BACKCHANNEL = "backchannel"     # "yeah", "mhm" — do NOT cut for these
KIND_INTERRUPTION = "interruption"
KIND_PUNCHLINE = "punchline"         # hold on speaker; suppress cutaways


@dataclass
class Annotation:
    """A labeled span of conversation. References the *time*, snapped from the
    word span the AI labeled. `subject_speaker` is who the moment is 'about' —
    e.g. for a QUESTION it is the person expected to answer next."""
    start: float
    end: float
    kind: str
    speaker: str                       # who is producing this span
    subject_speaker: Optional[str] = None
    note: str = ""


@dataclass
class Interval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class Segment:
    """One entry of the final Edit Decision List.

    `src_start`/`src_end` are times on the reference timeline. `camera` selects
    which angle to show ("cam1", "cam2", or "wide" for a two-shot when both
    speak). `reason` is for debugging / explainability of the edit.
    """
    src_start: float
    src_end: float
    camera: str
    reason: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.src_end - self.src_start)


@dataclass
class ZoomEvent:
    """A punch-in/out effect on the EDITED (rendered) timeline: scale ramps from
    1.0 up to `scale` by `peak`, holds until `release`, then eases back to 1.0 by
    `end`. Reuses the same annotations that drive camera switching — e.g. a quick
    punch-in on a punchline, a slow zoom through a monologue, or a tension-build
    through a question that peaks right at the anticipation cut."""
    start: float
    peak: float
    release: float
    end: float
    scale: float
    reason: str = ""


@dataclass
class EDL:
    segments: List[Segment] = field(default_factory=list)
    fps: float = 30.0
    notes: List[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.segments)

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def from_json(path: str) -> "EDL":
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        segs = [Segment(**s) for s in d.get("segments", [])]
        return EDL(segments=segs, fps=d.get("fps", 30.0), notes=d.get("notes", []))
