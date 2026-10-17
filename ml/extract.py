"""Builds timelines (detections + thumbnails) for every training video and caches them in data/cache/.

docker run --rm -v "$PWD:/work" -v "$PWD/backend/app:/srv/app" -w /work forte-ml python ml/extract.py [--only X-4] [--force]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# ml/ holds inspect.py, which would shadow the stdlib module torch imports: keep ml/ last on the path
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != HERE] + [HERE]
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from app.ml.features import build  # noqa: E402
from labels import find_videos  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/open")
    ap.add_argument("--cache", default="data/cache")
    ap.add_argument("--only", default="")
    ap.add_argument("--fps", type=float, default=None, help="default: adaptive 2-4 fps")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    only = {s.strip().upper() for s in a.only.split(",") if s.strip()}
    for name, path in find_videos(os.path.join(a.data, "videos")).items():
        if only and name not in only:
            continue
        out = os.path.join(a.cache, f"{name}.npz")
        if os.path.exists(out) and not a.force:
            continue
        t0 = time.time()
        tl = build(path, sample_fps=a.fps)
        tl.to_npz(out)
        print(f"{name:6s} dur={tl.duration:6.1f}s frames={len(tl.times):4d} time={time.time() - t0:5.1f}s", flush=True)


if __name__ == "__main__":
    main()
