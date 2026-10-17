"""video -> timeline (decode 4 fps + RT-DETR) -> scene + tracks -> rules -> events."""
from . import features, rules


def analyze_timeline(tl: features.Timeline, cfg: dict | None = None) -> list:
    return rules.run(tl, cfg or rules.load_config())


def analyze_video(path: str, progress=None, cfg: dict | None = None, transform=None) -> list:
    tl = features.build(path, progress=progress, transform=transform)
    events = analyze_timeline(tl, cfg)
    if progress:
        progress(1.0)
    return events
