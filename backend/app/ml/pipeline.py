"""video -> timeline (decode 2-4 fps + RT-DETR) -> scene -> key frames (Grounding DINO on the work-zone crop)
-> rules -> events."""
import numpy as np

from . import features, keyframes, rules
from .scene import build_scene
from .video import probe


def pick_keyframes(tl: features.Timeline, cfg: dict) -> list[float]:
    """Regular grid plus the last frame (what is left behind), capped so a 145 s clip stays within budget."""
    k = cfg.get("keyframes", {})
    every, cap = k.get("every", 5.0), k.get("max", 20)
    dur = float(tl.duration)
    times = list(np.arange(every / 2, max(every / 2, dur - 0.3), every))
    if len(times) > cap:
        times = list(np.linspace(times[0], times[-1], cap))
    times.append(max(0.0, dur - 0.4))
    return sorted({round(float(t), 2) for t in times})


def compute_extras(path: str, tl: features.Timeline, cfg: dict, progress=None, transform=None) -> dict:
    k = cfg.get("keyframes", {})
    if not k.get("enabled", True):
        return {}
    sc = build_scene(tl, cfg)
    scale = probe(path).height / float(tl.height) if tl.height else 1.0  # timeline boxes -> original pixels
    zone = [v * scale for v in sc.zone]
    times = pick_keyframes(tl, cfg)
    crops = keyframes.grab_crops(path, times, zone, transform)
    ts = [t for t in times if t in crops]
    dets = []
    for i, t in enumerate(ts):
        d = keyframes.detect([crops[t]], short_side=k.get("short_side", 480))[0]
        dets.append([(g, s, *[v / scale for v in b]) for g, s, *b in d])  # back to timeline pixels, crop-relative
        if progress:
            progress(0.8 + 0.19 * (i + 1) / max(1, len(ts)))
    return {"kf": {"zone": sc.zone, "times": ts, "dets": dets}}


def analyze_timeline(tl: features.Timeline, cfg: dict | None = None, extras: dict | None = None) -> list:
    return rules.run(tl, cfg or rules.load_config(), extras or {})


def analyze_video(path: str, progress=None, cfg: dict | None = None, transform=None) -> list:
    cfg = cfg or rules.load_config()
    prog1 = (lambda p: progress(0.8 * p)) if progress else None
    tl = features.build(path, progress=prog1, transform=transform)
    extras = compute_extras(path, tl, cfg, progress, transform)
    events = analyze_timeline(tl, cfg, extras)
    if progress:
        progress(1.0)
    return events
