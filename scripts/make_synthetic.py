"""Synthetic .mov clips for CI (real bank footage is never committed).

python scripts/make_synthetic.py out_dir [n=3]
Draws a desk, a grey box and moving silhouettes so the decoder, detector and rules run end to end.
"""
import os
import sys

import cv2
import numpy as np


def make(path, seconds, seed, w=464, h=848, fps=30):
    rng = np.random.default_rng(seed)
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not vw.isOpened():
        raise RuntimeError("OpenCV cannot write mp4v")
    x0 = rng.integers(40, 200)
    for i in range(int(seconds * fps)):
        img = np.full((h, w, 3), (205, 208, 212), np.uint8)
        cv2.rectangle(img, (0, int(h * .35)), (w, h), (120, 110, 100), -1)  # floor
        cv2.rectangle(img, (30, int(h * .30)), (330, int(h * .40)), (90, 140, 180), -1)  # desk
        cv2.rectangle(img, (350, int(h * .20)), (440, int(h * .38)), (170, 170, 175), -1)  # grey box
        x = int(x0 + 120 * np.sin(i / fps / 3))
        cv2.ellipse(img, (x, int(h * .25)), (22, 28), 0, 0, 360, (60, 70, 90), -1)  # head
        cv2.rectangle(img, (x - 35, int(h * .28)), (x + 35, int(h * .45)), (150, 120, 200), -1)  # body
        vw.write(img)
    vw.release()


if __name__ == "__main__":
    out = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    os.makedirs(out, exist_ok=True)
    for k in range(n):
        p = os.path.join(out, f"synthetic_{k + 1}.mov")
        make(p, seconds=8 + 6 * k, seed=k)
        print(p)
