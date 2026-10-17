"""Video analysis. STUB: real detection replaces analyze() later; the return shape stays."""
from dataclasses import dataclass, field

import cv2


@dataclass
class Detected:
    type: str
    code: str
    timecode_sec: float
    description: str
    confidence: float
    frame_times: list[float] = field(default_factory=list)


def video_duration(path: str) -> float:
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return n / fps if n > 0 else 0.0


def analyze(path: str) -> list[Detected]:
    dur = video_duration(path)
    t = min(10.0, max(0.0, dur / 2))
    return [
        Detected(
            type="Заглушка: проверка пайплайна",
            code="stub",
            timecode_sec=t,
            description="Тестовый результат. Модель детекции ещё не подключена.",
            confidence=0.0,
            frame_times=[max(0.0, t - 1), t, min(dur, t + 1)],
        )
    ]


def grab_frames(path: str, times: list[float]) -> list[tuple[float, bytes]]:
    cap = cv2.VideoCapture(path)
    out = []
    for t in times[:3]:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, img = cap.read()
        if ok:
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                out.append((t, buf.tobytes()))
    cap.release()
    return out
