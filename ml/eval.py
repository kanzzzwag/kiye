"""Quality report on the open data: verdict TP/FP/FN/TN, timecode error, type, processing time.

python ml/eval.py                       # uses cached timelines (data/cache), builds missing ones
python ml/eval.py --full                # re-run detection for every video (true end-to-end timing)
python ml/eval.py --augment             # robustness: rotate/perspective/scale/mirror/brightness copies
python ml/eval.py --only X-4,X-13 -v    # subset, print detected events

Expected types come from the table in docs/violation-types.md (the reviewed ground truth), never from the rules.
Writes docs/eval-latest.md (or docs/eval-augment.md).
"""
import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# ml/ holds inspect.py, which would shadow the stdlib module torch imports: keep ml/ last on the path
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != HERE] + [HERE]
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app.ml import features, pipeline  # noqa: E402
from labels import find_videos, load_labels  # noqa: E402

TOL = 3.0  # seconds: timecode counts as correct within this error


def expected_types(md_path="docs/violation-types.md") -> dict[str, list[str]]:
    out = {}
    if not os.path.exists(md_path):
        return out
    for line in open(md_path, encoding="utf-8"):
        m = re.match(r"\|\s*(X-\d+)[^|]*\|\s*[\d.]+\s*\|\s*([A-Z_]+)", line)
        if m:
            out.setdefault(m.group(1), []).append(m.group(2))
    return out


# ---- augmentations that imitate another camera position ----
def _rotate(deg):
    def f(img):
        h, w = img.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
        return cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)
    return f


def _perspective(k):
    def f(img):
        h, w = img.shape[:2]
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[w * k, h * k * .5], [w * (1 - k * .3), 0], [w, h], [0, h * (1 - k * .4)]])
        return cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w, h), borderMode=cv2.BORDER_REFLECT)
    return f


def _scale(s):
    def f(img):
        h, w = img.shape[:2]
        r = cv2.resize(img, (int(w * s), int(h * s)))
        if s >= 1:
            y, x = (r.shape[0] - h) // 2, (r.shape[1] - w) // 2
            return r[y:y + h, x:x + w]
        out = cv2.copyMakeBorder(r, (h - r.shape[0]) // 2, h - r.shape[0] - (h - r.shape[0]) // 2,
                                 (w - r.shape[1]) // 2, w - r.shape[1] - (w - r.shape[1]) // 2, cv2.BORDER_REFLECT)
        return out
    return f


def _bright(g):
    def f(img):
        return cv2.convertScaleAbs(img, alpha=g, beta=0)
    return f


AUGS = {
    "rot+15": _rotate(15), "rot-15": _rotate(-15), "persp": _perspective(0.18),
    "scale0.7": _scale(0.7), "scale1.3": _scale(1.3), "mirror": lambda im: cv2.flip(im, 1),
    "bright0.6": _bright(0.6), "bright1.4": _bright(1.4),
}


def timeline_for(name, path, cache_dir, force=False, transform=None):
    p = os.path.join(cache_dir, f"{name}.npz")
    if os.path.exists(p) and not force:
        return features.Timeline.from_npz(p)
    os.makedirs(cache_dir, exist_ok=True)
    tl = features.build(path, transform=transform)
    tl.to_npz(p)
    return tl


def evaluate(videos, labels, exp, cache_dir, force=False, transform=None, verbose=False):
    rows = []
    for name, path in videos.items():
        if name not in labels:
            continue
        tl = timeline_for(name, path, cache_dir, force, transform)
        t0 = time.time()
        events = pipeline.analyze_timeline(tl)
        rules_sec = time.time() - t0
        gt = labels[name]
        pred = bool(events)
        verdict = {(True, True): "TP", (False, True): "FP", (True, False): "FN", (False, False): "TN"}[(gt["violation"], pred)]
        err, type_ok, got = None, None, ",".join(sorted({e.code for e in events})) or "-"
        if gt["violation"] and events:
            errs = [min(abs(e.t - g) for e in events) for g in gt["times"]]
            err = max(errs) if errs else None
            want = exp.get(name, [])
            near = [e for e in events if any(abs(e.t - g) <= TOL for g in gt["times"])] or events
            type_ok = bool(want) and any(e.code in want for e in near)
        rows.append({"name": name, "gt": gt, "verdict": verdict, "err": err, "type_ok": type_ok, "got": got,
                     "want": ",".join(exp.get(name, [])) or "-", "sec": tl.stats.get("sec", 0.0) + rules_sec,
                     "dur": tl.duration, "events": events})
        if verbose:
            print(f"{name}: {verdict} want={rows[-1]['want']} gt={gt['times']}")
            for e in events:
                print(f"    {e.t:6.1f}s {e.code:20s} {e.score:.2f} {e.details}")
    return rows


def summarize(rows):
    c = {k: sum(r["verdict"] == k for r in rows) for k in ("TP", "FP", "FN", "TN")}
    recall = c["TP"] / max(1, c["TP"] + c["FN"])
    precision = c["TP"] / max(1, c["TP"] + c["FP"])
    errs = [r["err"] for r in rows if r["err"] is not None]
    typed = [r["type_ok"] for r in rows if r["type_ok"] is not None]
    t_ok = [e <= TOL for e in errs]
    return {**c, "recall": recall, "precision": precision, "accuracy": (c["TP"] + c["TN"]) / max(1, len(rows)),
            "mean_err": float(np.mean(errs)) if errs else None, "tc_ok": f"{sum(t_ok)}/{len(t_ok)}",
            "type_acc": f"{sum(typed)}/{len(typed)}", "max_sec": max(r["sec"] for r in rows),
            "max_sec_per_min": max(r["sec"] / max(r["dur"], 1) * 60 for r in rows)}


def to_markdown(rows, s, title):
    lines = [f"# {title}", "", f"Дата: {time.strftime('%Y-%m-%d %H:%M', time.gmtime())} UTC. Допуск таймкода ±{TOL:.0f} с.", "",
             "| Метрика | Значение |", "|---|---|",
             f"| Recall | {s['recall']:.0%} ({s['TP']}/{s['TP'] + s['FN']}) |",
             f"| Precision | {s['precision']:.0%} ({s['TP']}/{s['TP'] + s['FP']}) |",
             f"| Точность вердикта | {s['accuracy']:.0%} |",
             f"| TP / FP / FN / TN | {s['TP']} / {s['FP']} / {s['FN']} / {s['TN']} |",
             f"| Средняя ошибка таймкода | {s['mean_err']:.1f} с |" if s["mean_err"] is not None else "| Средняя ошибка таймкода | — |",
             f"| Таймкод в допуске | {s['tc_ok']} |",
             f"| Тип верный | {s['type_acc']} |",
             f"| Макс. время на видео | {s['max_sec']:.0f} с |",
             f"| Макс. время на минуту видео | {s['max_sec_per_min']:.0f} с |", "",
             "Время обработки берётся из кэша признаков и включает нагрузку, которая шла на машине во время его "
             "построения; для честного замера end-to-end используйте `--full` на свободной машине "
             "(ролик 145 с на 4 ядрах: ~106 с).", "",
             "| Видео | Длит., с | Разметка | Вердикт | Ошибка t, с | Ожид. тип | Найдено | Тип | Время, с |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: int(r["name"].split("-")[1])):
        g = ", ".join(f"{t:.0f}" for t in r["gt"]["times"]) or "нет"
        err = "" if r["err"] is None else f"{r['err']:.1f}"
        typ = "" if r["type_ok"] is None else ("да" if r["type_ok"] else "нет")
        lines.append(f"| {r['name']} | {r['dur']:.0f} | {g} | {r['verdict']} | {err} | {r['want']} | {r['got']} | "
                     f"{typ} | {r['sec']:.0f} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/open")
    ap.add_argument("--cache", default="data/cache")
    ap.add_argument("--only", default="")
    ap.add_argument("--full", action="store_true", help="re-run detection (end-to-end timing)")
    ap.add_argument("--augment", action="store_true")
    ap.add_argument("--augs", default=",".join(AUGS))
    ap.add_argument("--out", default="")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    labels = load_labels(os.path.join(a.data, "open_labels.xlsx"))
    videos = find_videos(os.path.join(a.data, "videos"))
    only = {s.strip().upper() for s in a.only.split(",") if s.strip()}
    if only:
        videos = {k: v for k, v in videos.items() if k in only}
    exp = expected_types()
    if not a.augment:
        rows = evaluate(videos, labels, exp, a.cache, force=a.full, verbose=a.verbose)
        s = summarize(rows)
        md = to_markdown(rows, s, "Оценка на открытых данных")
        print(md)
        if not only:
            with open(a.out or "docs/eval-latest.md", "w", encoding="utf-8") as f:
                f.write(md)
        return
    subset = ", ".join(sorted(videos, key=lambda s: int(s.split("-")[1])))
    parts = ["# Устойчивость к ракурсу (аугментации)", "",
             "Каждое видео прогоняется заново с искажением кадра (детектор видит изменённую картинку).",
             f"Видео ({len(videos)}): {subset}.", "",
             "| Аугментация | Recall | Precision | TP/FP/FN/TN | Тип верный | Таймкод в допуске |", "|---|---|---|---|---|---|"]
    for aug in [x for x in a.augs.split(",") if x]:
        rows = evaluate(videos, labels, exp, os.path.join(a.cache + "_aug", aug), force=a.full,
                        transform=AUGS[aug], verbose=a.verbose)
        s = summarize(rows)
        line = (f"| {aug} | {s['recall']:.0%} | {s['precision']:.0%} | {s['TP']}/{s['FP']}/{s['FN']}/{s['TN']} | "
                f"{s['type_acc']} | {s['tc_ok']} |")
        print(line, flush=True)
        parts.append(line)
    rows = evaluate(videos, labels, exp, a.cache)  # the same subset without distortion, for reference
    s = summarize(rows)
    parts.insert(parts.index("|---|---|---|---|---|---|") + 1,
                 f"| без искажений | {s['recall']:.0%} | {s['precision']:.0%} | {s['TP']}/{s['FP']}/{s['FN']}/{s['TN']} | "
                 f"{s['type_acc']} | {s['tc_ok']} |")
    md = "\n".join(parts) + "\n"
    print(md)
    with open(a.out or "docs/eval-augment.md", "w", encoding="utf-8") as f:  # augmented runs are usually subsets
        f.write(md)


if __name__ == "__main__":
    main()
