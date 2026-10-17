"""Video decoding. Always sequential: seeking by time returns empty frames on some phone .mov files."""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class VideoInfo:
    fps: float
    n_frames: int
    width: int
    height: int

    @property
    def duration(self) -> float:
        return self.n_frames / self.fps if self.fps else 0.0


def probe(path: str) -> VideoInfo:
    cap = cv2.VideoCapture(path)
    info = VideoInfo(cap.get(cv2.CAP_PROP_FPS) or 30.0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                     int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    return info


def iter_frames(path: str, sample_fps: float = 4.0, max_side: int = 848):
    """Yields (t_sec, bgr_frame) at ~sample_fps. Frames are downscaled so the long side <= max_side."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps / sample_fps)))
    i = 0
    while cap.grab():
        if i % step == 0:
            ok, img = cap.retrieve()
            if ok and img is not None:
                h, w = img.shape[:2]
                s = max_side / max(h, w)
                if s < 1:
                    img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
                yield i / fps, img
        i += 1
    cap.release()


def grab_frames(path: str, times: list[float], quality: int = 85) -> list[tuple[float, bytes]]:
    """JPEG frames nearest to the requested times, decoded in one sequential pass."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 10 ** 9
    want = {}
    for t in times:
        want.setdefault(min(n - 1, max(0, int(round(t * fps)))), t)
    out, i, last = {}, 0, max(want) if want else -1
    while i <= last and cap.grab():
        if i in want:
            ok, img = cap.retrieve()
            if ok and img is not None:
                ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
                if ok:
                    out[want[i]] = buf.tobytes()
        i += 1
    cap.release()
    if not out and want:  # stream shorter than its header says: fall back to the last decodable frame
        return _last_frame(path, times[:1], quality)
    return [(t, out[t]) for t in times if t in out]


def _last_frame(path, times, quality):
    cap = cv2.VideoCapture(path)
    last = None
    while True:
        ok, img = cap.read()
        if not ok:
            break
        last = img
    cap.release()
    if last is None:
        return []
    ok, buf = cv2.imencode(".jpg", last, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return [(times[0], buf.tobytes())] if ok else []


def small_gray(img: np.ndarray, width: int = 116) -> np.ndarray:
    h, w = img.shape[:2]
    g = cv2.cvtColor(cv2.resize(img, (width, int(h * width / w)), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    return g
