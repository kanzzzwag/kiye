"""Automatic scene model from the timeline, no manual markup (works on an unseen camera angle):

- the cashier = the person who spends most of the clip in one place (usually seated at the desk);
- work zone  = cashier's usual box + persistent objects next to it (laptop, counter, phone), slightly expanded;
- valid persons = boxes that overlap the work zone (people seen through glass walls never do);
- tracks of valid persons, their entries and exits;
- thumbnails stacked as float arrays for change detection (desk, door, safe areas).
"""
from dataclasses import dataclass, field

import numpy as np

from .features import HUE, LABEL, SAT, SCORE, VAL, WHITE, X1, X2, Y1, Y2, Timeline
from .tracker import Tracker, iou

DESK_OBJECTS = {"laptop", "keyboard", "mouse", "suitcase", "handbag", "cell phone", "remote", "book", "tv",
                "microwave", "oven", "dining table", "cup", "bottle"}


def box_area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def inter_area(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def expand(b, dx, dy, w, h):
    return [max(0.0, b[0] - dx), max(0.0, b[1] - dy), min(float(w), b[2] + dx), min(float(h), b[3] + dy)]


@dataclass
class Scene:
    tl: Timeline
    cfg: dict
    W: int = 0
    H: int = 0
    dt: float = 0.25
    cashier_h: float = 0.0
    anchor: list = field(default_factory=list)  # cashier's usual box
    zone: list = field(default_factory=list)  # work zone (x1, y1, x2, y2)
    desk: list = field(default_factory=list)  # desk surface estimate
    persons: list = field(default_factory=list)  # per frame: list of (box, score) inside the zone
    tracks: list = field(default_factory=list)
    background: list = field(default_factory=list)  # still people outside the room (through glass)
    far_edge: float = 0.0  # image y of the far edge of the desk; feet above it are outside the room
    gray: np.ndarray | None = None  # (T, h, w) float32 thumbnails
    sx: float = 1.0  # thumbnail px per frame px
    light: np.ndarray | None = None  # mean brightness per frame

    # ---- helpers ----
    def t_index(self, t: float) -> int:
        return int(np.clip(np.searchsorted(self.tl.times, t), 0, len(self.tl.times) - 1))

    def count(self, i: int) -> int:
        return len(self.persons[i])

    def objects(self, i: int, labels=None, min_score=0.3, region=None):
        out = []
        for d in self.tl.dets[i]:
            if d[LABEL] == "person" or d[SCORE] < min_score or (labels and d[LABEL] not in labels):
                continue
            b = d[X1:Y2 + 1]
            if region is not None and inter_area(b, region) < 0.5 * box_area(b):
                continue
            out.append(d)
        return out

    def thumb_box(self, b):
        g = self.gray
        x1, y1 = int(b[0] * self.sx), int(b[1] * self.sx)
        x2, y2 = int(np.ceil(b[2] * self.sx)), int(np.ceil(b[3] * self.sx))
        return max(0, x1), max(0, y1), min(g.shape[2], max(x2, x1 + 1)), min(g.shape[1], max(y2, y1 + 1))

    def person_mask(self, i: int, pad: float = 0.04) -> np.ndarray:
        """Thumbnail mask of all person boxes (any size) in frame i, used to ignore occluded pixels."""
        g = self.gray
        m = np.zeros(g.shape[1:], bool)
        for d in self.tl.dets[i]:
            if d[LABEL] == "person" and d[SCORE] >= 0.35:
                b = expand(d[X1:Y2 + 1], pad * self.W, pad * self.H, self.W, self.H)
                x1, y1, x2, y2 = self.thumb_box(b)
                m[y1:y2, x1:x2] = True
        return m


def _all_persons(tl: Timeline, min_score: float):
    return [[(list(d[X1:Y2 + 1]), d[SCORE]) for d in ds if d[LABEL] == "person" and d[SCORE] >= min_score]
            for ds in tl.dets]


def build_scene(tl: Timeline, cfg: dict) -> Scene:
    sc = Scene(tl, cfg, W=tl.width, H=tl.height)
    sc.dt = float(np.median(np.diff(tl.times))) if len(tl.times) > 1 else 0.25
    pmin = cfg.get("person_score", 0.5)
    allp = _all_persons(tl, pmin)

    # 1) cashier anchor: the place where a big person box stays longest (seated at the desk)
    raw = Tracker(max_gap=1.5, min_iou=0.3, max_dist=0.08)
    diag = float(np.hypot(sc.W, sc.H))
    for t, ps in zip(tl.times, allp):
        raw.update(float(t), [b for b, _ in ps], [s for _, s in ps], diag)
    best, best_score = None, -1.0
    for tr in raw.result(min_len=3):
        hs = np.array([b[3] - b[1] for b in tr.boxes])
        score = len(tr.times) * float(np.median(hs))  # long and large wins over far/through-glass people
        if score > best_score:
            best, best_score = tr, score
    if best is not None:
        bx = np.array(best.boxes)
        sc.anchor = [float(np.percentile(bx[:, 0], 20)), float(np.percentile(bx[:, 1], 20)),
                     float(np.percentile(bx[:, 2], 80)), float(np.percentile(bx[:, 3], 80))]
        sc.cashier_h = float(np.median(bx[:, 3] - bx[:, 1]))
    else:  # nobody in the clip: whole lower 2/3 of the frame
        sc.anchor = [0.0, sc.H / 3, float(sc.W), float(sc.H)]
        sc.cashier_h = sc.H / 4

    # 2) desk: persistent objects near the cashier
    near = expand(sc.anchor, sc.cashier_h * 0.9, sc.cashier_h * 0.9, sc.W, sc.H)
    pts = []
    n = len(tl.times)
    for lab in DESK_OBJECTS:
        boxes = [d[X1:Y2 + 1] for ds in tl.dets for d in ds if d[LABEL] == lab and d[SCORE] >= 0.3
                 and inter_area(d[X1:Y2 + 1], near) > 0.5 * box_area(d[X1:Y2 + 1])]
        if len(boxes) >= 0.2 * n:
            pts.append(np.median(np.array(boxes), axis=0))
    sc.far_edge = sc.anchor[1]
    if pts:
        p = np.array(pts)
        sc.far_edge = float(p[:, 3].min())  # objects stand on the desk: their lowest bottom edge is on it
        desk = [float(p[:, 0].min()), float(p[:, 1].min()), float(p[:, 2].max()), float(p[:, 3].max())]
        # the desk surface reaches the cashier's hands: join with the upper half of the cashier box
        a = sc.anchor
        hands = [a[0], a[1], a[2], a[1] + 0.5 * (a[3] - a[1])]
        sc.desk = [min(desk[0], hands[0]), min(desk[1], hands[1]), max(desk[2], hands[2]), max(desk[3], hands[3])]
    else:
        a = sc.anchor
        sc.desk = [a[0] - 0.3 * (a[2] - a[0]), a[1] - 0.3 * sc.cashier_h, a[2] + 0.3 * (a[2] - a[0]),
                   a[1] + 0.5 * (a[3] - a[1])]
    sc.desk = expand(sc.desk, 0, 0, sc.W, sc.H)
    zone = [min(sc.desk[0], sc.anchor[0]), min(sc.desk[1], sc.anchor[1]), max(sc.desk[2], sc.anchor[2]),
            max(sc.desk[3], sc.anchor[3])]
    m = cfg.get("zone_margin", 0.35) * sc.cashier_h
    sc.zone = expand(zone, m, m, sc.W, sc.H)
    # optional manual calibration (fractions of the frame) overrides the automatic estimate
    manual = cfg.get("manual_zones") or {}
    for key in ("desk", "zone"):
        if manual.get(key):
            x1, y1, x2, y2 = manual[key]
            setattr(sc, key, [x1 * sc.W, y1 * sc.H, x2 * sc.W, y2 * sc.H])

    # 3) valid persons: overlap the work zone and are not tiny
    minh = cfg.get("min_person_rel_h", 0.4) * sc.cashier_h
    ov = cfg.get("zone_overlap", 0.25)
    # people who sit still for most of the clip away from the cashier's place and the desk surface are
    # outside the cash room (seen through a glass wall): their positions are ignored
    background = []
    for tr in raw.result(min_len=3):
        if tr is best or tr.duration < cfg.get("bg_min_share", 0.4) * max(1.0, float(tl.times[-1])):
            continue
        bx = np.array(tr.boxes)
        cx, cy = (bx[:, 0] + bx[:, 2]) / 2, (bx[:, 1] + bx[:, 3]) / 2
        mb = list(np.median(bx, axis=0))
        still = max(cx.std(), cy.std()) < cfg.get("bg_max_motion", 0.08) * sc.cashier_h
        if still and inter_area(mb, sc.anchor) < 0.1 * box_area(mb) and inter_area(mb, sc.desk) < 0.35 * box_area(mb):
            background.append(mb)
    sc.background = background
    floor_y = sc.far_edge - cfg.get("behind_desk_margin", 0.5) * sc.cashier_h
    for ps in allp:
        keep = [(b, s) for b, s in ps if (b[3] - b[1]) >= minh and inter_area(b, sc.zone) >= ov * box_area(b)
                and b[3] >= floor_y and not any(iou(b, g) > 0.4 for g in background)]
        # drop duplicates (two boxes on one person)
        keep.sort(key=lambda x: -x[1])
        uniq = []
        for b, s in keep:
            if all(iou(b, u) < 0.6 and inter_area(b, u) < 0.8 * min(box_area(b), box_area(u)) for u, _ in uniq):
                uniq.append((b, s))
        sc.persons.append(uniq)

    trk = Tracker(max_gap=cfg.get("track_gap", 1.5), min_iou=0.2, max_dist=0.15)
    for t, ps in zip(tl.times, sc.persons):
        trk.update(float(t), [b for b, _ in ps], [s for _, s in ps], diag)
    sc.tracks = trk.result(min_len=2)

    # 4) thumbnails for change detection
    small = tl.small.astype(np.float32)
    sc.gray = small.mean(axis=3)
    sc.sx = sc.gray.shape[2] / float(sc.W)
    sc.light = sc.gray.reshape(len(sc.gray), -1).mean(axis=1)
    return sc


def episodes(mask: np.ndarray, times: np.ndarray, min_len: float, max_gap: float = 0.0):
    """Contiguous True runs as (t_start, t_end, i_start, i_end), merging gaps <= max_gap seconds."""
    runs, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        if not v and start is not None:
            runs.append([start, i - 1])
            start = None
    if start is not None:
        runs.append([start, len(mask) - 1])
    merged = []
    for r in runs:
        if merged and times[r[0]] - times[merged[-1][1]] <= max_gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [(float(times[a]), float(times[b]), a, b) for a, b in merged if times[b] - times[a] >= min_len - 1e-6]


__all__ = ["Scene", "build_scene", "episodes", "box_area", "inter_area", "expand", "HUE", "SAT", "VAL", "WHITE"]
