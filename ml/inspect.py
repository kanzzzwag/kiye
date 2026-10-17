"""Data review: cuts contact sheets around each labelled timestamp and an overview of every clip.

python ml/inspect.py [--data data/open] [--out data/inspect] [--only X-4,X-13] [--step 1] [--span 4]
                     [--width 240] [--cols 5] [--crop x0,y0,x1,y1] [--at 14,18] [--no-overview]
Writes <out>/<name>_event<k>.jpg (frames t-span..t+span) and <out>/<name>_overview.jpg (12 frames over the clip).
Frames are decoded sequentially: seeking by time is unreliable on some of these .mov files (X-11 returns nothing).
"""
import sys

# this file is named like the stdlib module `inspect`; move its folder to the end of sys.path
# so numpy/dataclasses still import the real one
sys.path.append(sys.path.pop(0))

import argparse  # noqa: E402
import os  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from labels import find_videos, load_labels  # noqa: E402


def read_times(path, times, crop=None):
    """Decode once, front to back, and return {t: frame} for the frames nearest to each requested time."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    want = {}
    for t in times:
        want.setdefault(max(0, int(round(t * fps))), []).append(t)
    out, i, last = {}, 0, max(want) if want else -1
    while i <= last and cap.grab():
        if i in want:
            ok, img = cap.retrieve()
            if ok and crop:
                h, w = img.shape[:2]
                img = img[int(crop[1] * h):int(crop[3] * h), int(crop[0] * w):int(crop[2] * w)]
            for t in want[i]:
                out[t] = img if ok else None
        i += 1
    cap.release()
    return out


def tile(img, label, w=240):
    if img is None:
        img = np.zeros((int(w * 848 / 464), w, 3), np.uint8)
    h = int(img.shape[0] * w / img.shape[1])
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    cv2.rectangle(img, (0, 0), (w, 22), (0, 0, 0), -1)
    cv2.putText(img, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
    return img


def sheet(tiles, cols):
    h, w = tiles[0].shape[:2]
    while len(tiles) % cols:
        tiles.append(np.zeros((h, w, 3), np.uint8))
    rows = [np.hstack([cv2.resize(t, (w, h)) for t in tiles[i:i + cols]]) for i in range(0, len(tiles), cols)]
    return np.vstack(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/open")
    ap.add_argument("--out", default="data/inspect")
    ap.add_argument("--only", default="")
    ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--span", type=float, default=4.0)
    ap.add_argument("--overview", type=int, default=12)
    ap.add_argument("--width", type=int, default=240)
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--at", default="", help="override event times, e.g. 14,18 (for clean clips)")
    ap.add_argument("--crop", default="", help="x0,y0,x1,y1 in 0..1, zoom into a region")
    ap.add_argument("--no-overview", action="store_true")
    a = ap.parse_args()
    crop = tuple(float(v) for v in a.crop.split(",")) if a.crop else None
    os.makedirs(a.out, exist_ok=True)
    labels = load_labels(os.path.join(a.data, "open_labels.xlsx"))
    videos = find_videos(os.path.join(a.data, "videos"))
    only = {s.strip().upper() for s in a.only.split(",") if s.strip()}
    for name, path in videos.items():
        if only and name not in only:
            continue
        lab = labels.get(name, {"violation": None, "times": []})
        cap = cv2.VideoCapture(path)
        dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
        cap.release()
        times = [float(v) for v in a.at.split(",")] if a.at else lab["times"]
        events = [[round(t, 2) for t in np.arange(t0 - a.span, t0 + a.span + 1e-6, a.step) if 0 <= t < dur]
                  for t0 in times]
        overview = [] if a.no_overview else [round(t, 2) for t in np.linspace(0, max(0.0, dur - 0.5), a.overview)]
        frames = read_times(path, [t for ev in events for t in ev] + overview, crop)
        for k, (t0, ts) in enumerate(zip(times, events)):
            tiles = [tile(frames.get(t), f"{name} {t:.1f}s" + (" *" if abs(t - t0) < 1e-6 else ""), a.width)
                     for t in ts]
            cv2.imwrite(os.path.join(a.out, f"{name}_event{k}.jpg"), sheet(tiles, a.cols), [cv2.IMWRITE_JPEG_QUALITY, 80])
        if overview:
            tiles = [tile(frames.get(t), f"{name} {t:.1f}s") for t in overview]
            cv2.imwrite(os.path.join(a.out, f"{name}_overview.jpg"), sheet(tiles, 6), [cv2.IMWRITE_JPEG_QUALITY, 80])
        print(f"{name:6s} dur={dur:6.1f}s violation={lab['violation']} times={lab['times']}")


if __name__ == "__main__":
    main()
