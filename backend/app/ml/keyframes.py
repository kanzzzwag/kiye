"""Second, slower look at selected key frames: open-vocabulary detection (Grounding DINO tiny, Apache-2.0) on a
full-resolution crop of the work zone. The first pass (RT-DETR on the whole frame) misses small things on the desk:
a coffee cup, banknote stacks, an open safe door. Running it on every frame is too slow on CPU (~3 s per crop),
so it only sees key frames picked from the first pass."""
import os
import threading

import numpy as np

MODEL_NAME = os.environ.get("OV_MODEL", "IDEA-Research/grounding-dino-tiny").split("/")[-1]
MODELS_DIR = os.environ.get("MODELS_DIR", "/srv/models")

# text query -> group used by the rules
QUERIES = [
    ("coffee cup", "drink"), ("drink bottle", "drink"),
    ("stack of banknotes", "cash"), ("money bag", "bag"), ("handbag", "bag"),
    ("coat", "coat"), ("jacket", "coat"),
    ("open safe door", "open_door"), ("open cabinet door", "open_door"),
]
PROMPT = ". ".join(q for q, _ in QUERIES) + "."

_lock = threading.Lock()
_model = None


def _load():
    global _model
    with _lock:
        if _model is None:
            import torch
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

            path = MODELS_DIR and os.path.join(MODELS_DIR, MODEL_NAME)
            src = path if path and os.path.isdir(path) else os.environ.get("OV_MODEL", "IDEA-Research/grounding-dino-tiny")
            _model = (AutoProcessor.from_pretrained(src), AutoModelForZeroShotObjectDetection.from_pretrained(src).eval(),
                      torch)
    return _model


def group_of(label: str) -> str | None:
    """Grounding DINO returns the matched phrase (sometimes several merged); map it to one group."""
    label = label.lower()
    for key, grp in (("cup", "drink"), ("drink", "drink"), ("bottle", "drink"), ("banknote", "cash"), ("stack", "cash"),
                     ("money", "bag"), ("handbag", "bag"), ("bag", "bag"), ("coat", "coat"), ("jacket", "coat"),
                     ("safe", "open_door"), ("cabinet", "open_door"), ("door", "open_door")):
        if key in label:
            return grp
    return None


def detect(crops_bgr: list[np.ndarray], short_side: int = 480, box_threshold: float = 0.25) -> list[list[tuple]]:
    """Per crop: list of (group, score, x1, y1, x2, y2) in crop pixels."""
    from PIL import Image

    proc, model, torch = _load()
    out = []
    for crop in crops_bgr:
        img = Image.fromarray(np.ascontiguousarray(crop[:, :, ::-1]))
        inp = proc(images=img, text=PROMPT, return_tensors="pt",
                   size={"shortest_edge": short_side, "longest_edge": int(short_side * 1.6)})
        with torch.inference_mode():
            res = model(**inp)
        r = proc.post_process_grounded_object_detection(res, inp.input_ids, box_threshold=box_threshold,
                                                        text_threshold=0.2, target_sizes=torch.tensor([img.size[::-1]]))[0]
        dets = []
        for s, lab, b in zip(r["scores"].tolist(), r["labels"], r["boxes"].tolist()):
            g = group_of(lab)
            if g:
                dets.append((g, round(s, 3), *[round(v, 1) for v in b]))
        out.append(dets)
    return out


def grab_crops(path: str, times: list[float], box, transform=None) -> dict[float, np.ndarray]:
    """Full-resolution crops of `box` at the given times, one sequential decoding pass.
    transform: the same frame distortion as the first pass used (eval --augment)."""
    import cv2

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    want = {}
    for t in times:
        want.setdefault(max(0, int(round(t * fps))), t)
    out, i, last = {}, 0, max(want) if want else -1
    x1, y1, x2, y2 = [int(v) for v in box]
    while i <= last and cap.grab():
        if i in want:
            ok, img = cap.retrieve()
            if ok and img is not None:
                if transform is not None:
                    img = transform(img)
                h, w = img.shape[:2]
                out[want[i]] = img[max(0, y1):min(h, y2), max(0, x1):min(w, x2)].copy()
        i += 1
    cap.release()
    return out
