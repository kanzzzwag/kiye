"""Object detector: RT-DETR (Apache-2.0) via Hugging Face transformers, CPU only, weights baked into the image."""
import os
import threading

import numpy as np

MODEL_NAME = os.environ.get("DETECTOR_MODEL", "PekingU/rtdetr_r18vd_coco_o365").split("/")[-1]
MODELS_DIR = os.environ.get("MODELS_DIR", "/srv/models")

# COCO classes the rules care about (names as in the model config)
KEEP = {
    "person", "handbag", "backpack", "suitcase", "umbrella",
    "cup", "bottle", "wine glass", "bowl", "banana", "apple", "sandwich", "orange", "donut", "cake", "pizza",
    "cell phone", "laptop", "keyboard", "mouse", "book", "remote", "scissors",
    "dining table", "chair", "refrigerator", "microwave", "oven", "tv",
}

_lock = threading.Lock()
_model = None


def _load():
    global _model
    with _lock:
        if _model is None:
            import torch
            from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

            torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
            path = os.path.join(MODELS_DIR, MODEL_NAME)
            proc = RTDetrImageProcessor.from_pretrained(path)
            model = RTDetrForObjectDetection.from_pretrained(path).eval()
            _model = (proc, model, torch)
    return _model


class Detection(tuple):
    """(label, score, x1, y1, x2, y2) in pixels of the input frame."""
    __slots__ = ()

    label = property(lambda s: s[0])
    score = property(lambda s: s[1])
    box = property(lambda s: s[2:6])


def input_size(h: int, w: int, long_side: int) -> dict:
    """Keep the aspect ratio (portrait phone video stays portrait); sides are multiples of 32."""
    s = long_side / max(h, w)
    return {"height": max(32, int(round(h * s / 32)) * 32), "width": max(32, int(round(w * s / 32)) * 32)}


def detect(frames_bgr: list[np.ndarray], threshold: float = 0.3, size: int = 640) -> list[list[Detection]]:
    proc, model, torch = _load()
    rgb = [f[:, :, ::-1] for f in frames_bgr]
    h, w = frames_bgr[0].shape[:2]
    inputs = proc(images=rgb, return_tensors="pt", size=input_size(h, w, size))
    with torch.inference_mode():
        out = model(**inputs)
    sizes = torch.tensor([f.shape[:2] for f in frames_bgr])
    res = proc.post_process_object_detection(out, target_sizes=sizes, threshold=threshold)
    id2label = model.config.id2label
    result = []
    for r in res:
        dets = []
        for s, l, b in zip(r["scores"].tolist(), r["labels"].tolist(), r["boxes"].tolist()):
            name = id2label[l]
            if name in KEEP:
                dets.append(Detection((name, round(s, 3), *[round(v, 1) for v in b])))
        result.append(dets)
    return result
