"""Minimal multi-object tracker: greedy IoU / centre-distance matching with a short memory (own code)."""
from dataclasses import dataclass, field

import numpy as np


def iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def centre(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


@dataclass
class Track:
    id: int
    times: list = field(default_factory=list)
    boxes: list = field(default_factory=list)
    scores: list = field(default_factory=list)

    @property
    def start(self):
        return self.times[0]

    @property
    def end(self):
        return self.times[-1]

    @property
    def duration(self):
        return self.end - self.start

    def box_at(self, t, tol=0.6):
        if not self.times:
            return None
        i = int(np.argmin(np.abs(np.asarray(self.times) - t)))
        return self.boxes[i] if abs(self.times[i] - t) <= tol else None


class Tracker:
    def __init__(self, max_gap: float = 2.0, min_iou: float = 0.2, max_dist: float = 0.25):
        self.max_gap, self.min_iou, self.max_dist = max_gap, min_iou, max_dist
        self.tracks: list[Track] = []
        self._next = 1

    def update(self, t: float, boxes: list, scores: list, frame_diag: float):
        live = [tr for tr in self.tracks if t - tr.end <= self.max_gap]
        pairs = []
        for ti, tr in enumerate(live):
            for di, b in enumerate(boxes):
                ov = iou(tr.boxes[-1], b)
                (cx1, cy1), (cx2, cy2) = centre(tr.boxes[-1]), centre(b)
                d = np.hypot(cx1 - cx2, cy1 - cy2) / frame_diag
                if ov >= self.min_iou or d <= self.max_dist * min(1.0, (t - tr.end) / 0.5 + 0.3):
                    pairs.append((ov - d, ti, di))
        pairs.sort(reverse=True)
        used_t, used_d = set(), set()
        for _, ti, di in pairs:
            if ti in used_t or di in used_d:
                continue
            used_t.add(ti)
            used_d.add(di)
            tr = live[ti]
            tr.times.append(t)
            tr.boxes.append(list(boxes[di]))
            tr.scores.append(scores[di])
        for di, b in enumerate(boxes):
            if di not in used_d:
                tr = Track(self._next, [t], [list(b)], [scores[di]])
                self._next += 1
                self.tracks.append(tr)

    def result(self, min_len: int = 2) -> list[Track]:
        return [tr for tr in self.tracks if len(tr.times) >= min_len]
