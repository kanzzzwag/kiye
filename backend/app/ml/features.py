"""Per-video timeline: sampled frames -> detections + small frames. The rules run on this, not on raw video."""
import json
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import detector
from .video import iter_frames, probe

SMALL_W = 160  # width of the thumbnails used for change detection

# det tuple layout
LABEL, SCORE, X1, Y1, X2, Y2, HUE, SAT, VAL, WHITE = range(10)


@dataclass
class Timeline:
    duration: float
    width: int  # size of frames the boxes refer to
    height: int
    times: np.ndarray  # (T,)
    dets: list  # T lists of (label, score, x1, y1, x2, y2, hue, sat, val, white_frac)
    small: np.ndarray  # (T, h, SMALL_W, 3) uint8 BGR thumbnails
    stats: dict = field(default_factory=dict)

    def to_npz(self, path):
        np.savez_compressed(path, duration=self.duration, size=np.array([self.width, self.height]), times=self.times,
                            build_sec=float(self.stats.get("sec", 0.0)), dets=json.dumps(self.dets),
                            small=self.small)

    @classmethod
    def from_npz(cls, path):
        z = np.load(path)
        dets = [[tuple(d) for d in fr] for fr in json.loads(str(z["dets"]))]
        tl = cls(float(z["duration"]), int(z["size"][0]), int(z["size"][1]), z["times"], dets, z["small"])
        tl.stats = {"sec": float(z["build_sec"]), "frames": len(tl.times)}
        return tl


def box_stats(hsv: np.ndarray, box) -> tuple[float, float, float, float]:
    """Mean hue/sat/val of the box and the share of bright, unsaturated pixels (white paper, lit screen)."""
    h, w = hsv.shape[:2]
    x1, y1, x2, y2 = max(0, int(box[0])), max(0, int(box[1])), min(w, int(box[2])), min(h, int(box[3]))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return 0.0, 0.0, 0.0, 0.0
    roi = hsv[y1:y2, x1:x2]
    hh, ss, vv = roi[..., 0], roi[..., 1], roi[..., 2]
    white = float(np.mean((vv > 170) & (ss < 50)))
    return float(hh.mean()), float(ss.mean()), float(vv.mean()), round(white, 3)


def pick_fps(duration: float, budget_frames: int = 360, lo: float = 2.0, hi: float = 4.0) -> float:
    """2-4 fps: short clips get 4 fps, long ones fewer so a 145 s clip stays well under 2 minutes on CPU.
    Clips over 3 minutes may go below 2 fps so that even a 10-minute upload finishes inside the 5-minute limit."""
    if duration <= 0:
        return hi
    floor = lo if duration <= 180 else 0.5
    return float(min(hi, max(floor, budget_frames / duration)))


def build(path: str, sample_fps: float | None = None, batch: int = 1, det_size: int = 640, threshold: float = 0.3,
          progress=None, transform=None) -> Timeline:
    """transform: optional fn(frame)->frame (used by eval --augment to simulate other camera angles)."""
    info = probe(path)
    sample_fps = sample_fps or pick_fps(info.duration)
    t0 = time.time()
    times, dets, small, buf = [], [], [], []
    w = h = 0

    def flush():
        res = detector.detect([f for _, f in buf], threshold=threshold, size=det_size)
        for (t, f), r in zip(buf, res):
            hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
            fr = []
            for d in r:
                st = box_stats(hsv, d[2:6])
                fr.append([d[0], d[1], *d[2:6], *[round(v, 1) for v in st[:3]], st[3]])
            times.append(round(t, 3))
            dets.append(fr)
            small.append(cv2.resize(f, (SMALL_W, int(f.shape[0] * SMALL_W / f.shape[1])), interpolation=cv2.INTER_AREA))
        buf.clear()
        if progress and info.duration:
            progress(min(0.95, 0.95 * times[-1] / info.duration))

    for t, f in iter_frames(path, sample_fps):
        if transform is not None:
            f = transform(f)
        h, w = f.shape[:2]
        buf.append((t, f))
        if len(buf) == batch:
            flush()
    if buf:
        flush()
    if not times:
        raise ValueError("no decodable frames")
    hs = min(s.shape[0] for s in small)
    tl = Timeline(info.duration or times[-1], w, h, np.asarray(times), [[tuple(d) for d in fr] for fr in dets],
                  np.stack([s[:hs] for s in small]))
    tl.stats = {"frames": len(times), "sec": round(time.time() - t0, 1)}
    return tl
