"""Honest threshold check: 5-fold cross-validation by room.

Rooms are found automatically (clustering of the median background frame of each clip, so duplicates and
clips of one camera set-up land in one fold). For every fold the thresholds in GRID are tuned on the other
rooms (objective F2: recall weighs more than precision) and the tuned rules are applied to the held-out room.

python ml/cv.py            # prints the per-fold choice and the pooled out-of-fold metrics
"""
import copy
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != HERE] + [HERE]
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app.ml import pipeline, rules  # noqa: E402
from eval import load_extras, timeline_for  # noqa: E402
from labels import find_videos, load_labels  # noqa: E402

# dotted path in rules.yaml -> candidate values (kept small: 3^k combinations x 5 folds)
GRID = {
    "rules.door.min_diff": [10.0, 15.0, 20.0],
    "rules.open_area.min_area": [0.07, 0.1, 0.14],
    "rules.cash_on_entry.min_share": [0.1, 0.2, 0.3],
    "rules.keyframe.drink_score": [0.45, 0.5, 0.55],
}


def set_path(cfg, path, value):
    d = cfg
    keys = path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def rooms(names, cache_dir, k=5):
    """Average-linkage clustering of the median thumbnails into k camera set-ups."""
    vecs = []
    for n in names:
        z = np.load(os.path.join(cache_dir, f"{n}.npz"))
        m = np.median(z["small"][::4], axis=0).astype(np.uint8)
        g = cv2.resize(cv2.cvtColor(m, cv2.COLOR_BGR2GRAY), (40, 73)).astype(float).ravel()
        vecs.append((g - g.mean()) / (g.std() + 1e-6))
    x = np.array(vecs)
    c = x @ x.T / x.shape[1]
    cl = [[i] for i in range(len(names))]
    while len(cl) > k:
        best = None
        for a in range(len(cl)):
            for b in range(a + 1, len(cl)):
                s = np.mean([c[i, j] for i in cl[a] for j in cl[b]])
                if best is None or s > best[0]:
                    best = (s, a, b)
        _, a, b = best
        cl[a] += cl[b]
        del cl[b]
    return [[names[i] for i in grp] for grp in cl]


def f2(v):
    tp = sum(g and p for g, p in v.values())
    fp = sum((not g) and p for g, p in v.values())
    fn = sum(g and (not p) for g, p in v.values())
    r = tp / max(1, tp + fn)
    pr = tp / max(1, tp + fp)
    return 5 * pr * r / max(1e-9, 4 * pr + r)


def main():
    data, cache = "data/open", "data/cache"
    labels = load_labels(os.path.join(data, "open_labels.xlsx"))
    videos = find_videos(os.path.join(data, "videos"))
    names = sorted([n for n in videos if n in labels], key=lambda s: int(s.split("-")[1]))
    tls = {n: timeline_for(n, videos[n], cache) for n in names}
    extras = {n: load_extras(n) for n in names}
    base = rules.load_config()
    folds = rooms(names, cache)
    combos = [dict(zip(GRID, vals)) for vals in itertools.product(*GRID.values())]
    cfgs = []
    for combo in combos:
        cfg = copy.deepcopy(base)
        for p, v in combo.items():
            set_path(cfg, p, v)
        cfgs.append(cfg)
    # verdict table: video -> one verdict per threshold combination (the scene of a video is built once)
    table = {}
    for n in names:
        table[n] = [bool(pipeline.analyze_timeline(tls[n], cfg, extras.get(n))) for cfg in cfgs]
    pooled = {}
    for k, test in enumerate(folds):
        train = [n for n in names if n not in test]
        scores = [f2({n: (labels[n]["violation"], table[n][j]) for n in train}) for j in range(len(cfgs))]
        j = int(np.argmax(scores))
        res = {n: (labels[n]["violation"], table[n][j]) for n in test}
        pooled.update(res)
        tp = sum(g and p for g, p in res.values())
        print(f"fold {k + 1}: test={','.join(test)}\n   chosen={combos[j]} trainF2={scores[j]:.2f} "
              f"test TP/FP/FN/TN={tp}/{sum((not g) and p for g, p in res.values())}/"
              f"{sum(g and not p for g, p in res.values())}/{sum((not g) and not p for g, p in res.values())}")
    tp = sum(g and p for g, p in pooled.values())
    fp = sum((not g) and p for g, p in pooled.values())
    fn = sum(g and (not p) for g, p in pooled.values())
    print(f"\nCV by room (out-of-fold, {len(folds)} folds): recall {tp / max(1, tp + fn):.0%} ({tp}/{tp + fn}), "
          f"precision {tp / max(1, tp + fp):.0%} ({tp}/{tp + fp})")


if __name__ == "__main__":
    main()
