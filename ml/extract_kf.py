"""Open-vocabulary detections on key frames for every training video -> data/cache_kf/<name>.json.
Used to design and tune the key-frame rules without re-running the slow model.

docker run ... forteguard-backend python ml/extract_kf.py [--only X-46] [--force]
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != HERE] + [HERE]
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

import numpy as np  # noqa: E402

from app.ml import keyframes, pipeline, rules  # noqa: E402
from app.ml.features import Timeline  # noqa: E402
from app.ml.scene import build_scene  # noqa: E402
from labels import find_videos  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/open")
    ap.add_argument("--cache", default="data/cache")
    ap.add_argument("--out", default="data/cache_kf")
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    only = {s.strip().upper() for s in a.only.split(",") if s.strip()}
    cfg = rules.load_config()
    for name, path in find_videos(os.path.join(a.data, "videos")).items():
        if only and name not in only:
            continue
        out = os.path.join(a.out, f"{name}.json")
        if os.path.exists(out) and not a.force:
            continue
        tl = Timeline.from_npz(os.path.join(a.cache, f"{name}.npz"))
        sc = build_scene(tl, cfg)
        times = pipeline.pick_keyframes(tl, cfg)  # the same key frames the service will use
        t0 = time.time()
        crops = keyframes.grab_crops(path, times, sc.zone)
        ts = [t for t in times if t in crops]
        dets = keyframes.detect([crops[t] for t in ts])
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"zone": sc.zone, "times": ts, "dets": dets}, f)
        print(f"{name:6s} keyframes={len(ts):3d} time={time.time() - t0:5.1f}s", flush=True)


if __name__ == "__main__":
    main()
