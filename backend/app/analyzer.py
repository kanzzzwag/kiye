"""Video analysis entry point used by the worker. The return shape (Detected) is what tasks.py stores."""
from dataclasses import dataclass, field

from .ml import video
from .ml.pipeline import analyze_video


@dataclass
class Detected:
    type: str
    code: str
    timecode_sec: float
    description: str  # ends with "Норма: <документ>, <пункт>." (the jury schema has no separate field)
    confidence: float
    frame_times: list[float] = field(default_factory=list)
    legal_text: str = ""


def video_duration(path: str) -> float:
    return video.probe(path).duration


def analyze(path: str, progress=None) -> list[Detected]:
    return [Detected(type=e.name, code=e.code, timecode_sec=round(e.t, 2), description=e.full_description,
                     confidence=round(e.score, 3), frame_times=e.frame_times, legal_text=e.legal_text)
            for e in analyze_video(path, progress=progress)]


def grab_frames(path: str, times: list[float]) -> list[tuple[float, bytes]]:
    return video.grab_frames(path, times[:3])
