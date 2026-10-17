"""Run at `docker build`: fetch detector weights into the image so the service works offline.

Model: PekingU/rtdetr_r18vd_coco_o365 (RT-DETR, Apache-2.0, weights Apache-2.0), see docs/LICENSES.md.
"""
import os
import sys

from huggingface_hub import snapshot_download

MODEL_ID = os.environ.get("DETECTOR_MODEL", "PekingU/rtdetr_r18vd_coco_o365")
REVISION = os.environ.get("DETECTOR_REVISION", "386c43855d01bcd966e548f3296fbd2cd2a2a40b")  # pinned
TARGET = os.environ.get("MODELS_DIR", "/srv/models")

if __name__ == "__main__":
    path = snapshot_download(MODEL_ID, revision=REVISION, local_dir=os.path.join(TARGET, MODEL_ID.split("/")[-1]),
                             allow_patterns=["*.json", "*.safetensors", "*.txt", "LICENSE*", "README*"])
    print("downloaded", MODEL_ID, "->", path, file=sys.stderr)
