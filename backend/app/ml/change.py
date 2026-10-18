"""Persistent scene change on thumbnails: which parts of the room look different from the start of the clip
and stay different (an opened door or safe, an object put on the desk). Pixels covered by people are ignored,
lighting changes are normalised. Pure numpy, a few ms per frame."""
import warnings

import numpy as np

from .scene import Scene


class ChangeMap:
    def __init__(self, sc: Scene, window: float = 1.5, pad: float = 0.03):
        g = sc.gray  # (T, h, w)
        T = len(g)
        self.sc = sc
        light = np.median(g.reshape(T, -1), axis=1)
        ref_light = np.median(light[: max(1, min(T, int(3 / sc.dt)))])
        self.norm = (g * (ref_light / np.maximum(light, 1.0))[:, None, None]).astype(np.float32)
        self.occ = np.stack([sc.person_mask(i, pad) for i in range(T)])
        # baseline: per-pixel median of the first unoccluded observations (up to ~3 s of them)
        k = max(3, int(3 / sc.dt))
        vis = ~self.occ
        csum = np.cumsum(vis, axis=0)
        take = vis & (csum <= k)
        cnt = take.sum(0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            self.base = np.nanmedian(np.where(take, self.norm, np.float32(np.nan)), axis=0)
        self.base_known = cnt > 0
        self.win = max(1, int(round(window / sc.dt)))
        self._diff = {}  # frame index -> (diff, known); rules ask for the same frames repeatedly

    def current(self, i: int) -> tuple[np.ndarray, np.ndarray]:
        """Median of unoccluded values over the last `window` seconds and whether it is known."""
        a = max(0, i - self.win + 1)
        vals = np.where(self.occ[a:i + 1], np.nan, self.norm[a:i + 1])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cur = np.nanmedian(vals, axis=0)
        known = ~np.isnan(cur) & self.base_known
        return cur, known

    def diff(self, i: int) -> tuple[np.ndarray, np.ndarray]:
        if i in self._diff:
            return self._diff[i]
        cur, known = self.current(i)
        d = np.abs(np.nan_to_num(cur) - np.nan_to_num(self.base))
        d[~known] = 0
        self._diff[i] = (d, known)
        return d, known

    def region_diff(self, i: int, box) -> tuple[float, float]:
        """Mean abs difference in the box over known pixels, and the share of the box that is known."""
        x1, y1, x2, y2 = self.sc.thumb_box(box)
        d, known = self.diff(i)
        k = known[y1:y2, x1:x2]
        if k.sum() == 0:
            return 0.0, 0.0
        return float(d[y1:y2, x1:x2][k].mean()), float(k.mean())

    def changed_area(self, i: int, box, thr: float) -> float:
        """Share of the box's known pixels that differ from the baseline by more than thr."""
        x1, y1, x2, y2 = self.sc.thumb_box(box)
        d, known = self.diff(i)
        k = known[y1:y2, x1:x2]
        if k.sum() == 0:
            return 0.0
        return float((d[y1:y2, x1:x2][k] > thr).mean())
