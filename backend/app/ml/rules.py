"""Rules over the timeline. Every rule works on scene objects (cashier place, desk, entry point, persons), never on
pixel coordinates of a particular room, so the same thresholds apply to a new camera angle. Thresholds: rules.yaml.

Each rule returns Events; descriptions state only what is visible and end with the legal norm (see legal.py)."""
import os
from dataclasses import dataclass, field

import numpy as np
import yaml

from . import legal
from .change import ChangeMap
from .features import LABEL, SCORE, WHITE
from .scene import Scene, build_scene, episodes, expand
from .tracker import Track

CONFIG = os.path.join(os.path.dirname(__file__), "rules.yaml")


@dataclass
class Event:
    code: str
    t: float
    score: float
    details: str
    rule_id: str | None = None
    frame_times: list = field(default_factory=list)

    @property
    def name(self):
        return legal.type_name(self.code)

    @property
    def legal_text(self):
        return legal.norm_text(self.code, self.rule_id)

    @property
    def full_description(self):
        return f"{self.details} {self.legal_text}"


def load_config(path: str = CONFIG) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fmt_t(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


class Ctx:
    """Shared, lazily computed signals for all rules."""

    def __init__(self, sc: Scene, cfg: dict):
        self.sc, self.cfg = sc, cfg
        self.times = sc.tl.times
        self.count = np.array([sc.count(i) for i in range(len(self.times))])
        self._cm = None

    @property
    def cm(self) -> ChangeMap:
        if self._cm is None:
            self._cm = ChangeMap(self.sc)
        return self._cm

    def normal_light(self, i: int) -> bool:
        l0 = self.sc.light[0]
        return 0.8 * l0 <= self.sc.light[i] <= 1.25 * l0

    def entries(self, min_start: float) -> list[Track]:
        """Tracks that appear after the clip starts (someone walks in)."""
        return [tr for tr in self.sc.tracks if tr.start >= min_start and len(tr.times) >= 4]


def still_since(tr: Track, t_end: float, ch: float, max_move: float = 0.12, win: float = 1.5) -> float:
    """Walking back from t_end, the last moment the person was standing still (started to walk away)."""
    ts, bx = np.asarray(tr.times), np.asarray(tr.boxes)
    cx, cy = (bx[:, 0] + bx[:, 2]) / 2, (bx[:, 1] + bx[:, 3]) / 2
    for k in range(len(ts) - 1, -1, -1):
        if ts[k] > t_end:
            continue
        w = (ts >= ts[k] - win) & (ts <= ts[k])
        if w.sum() >= 3 and max(np.ptp(cx[w]), np.ptp(cy[w])) < max_move * ch:
            return float(ts[k])
    return float(ts[0])


# ---------------------------------------------------------------- rules

def rule_crowd(x: Ctx) -> list[Event]:
    c = x.cfg.get("crowd", {})
    out = []
    for t0, t1, a, b in episodes(x.count >= c.get("min_persons", 3), x.times, c.get("min_duration", 1.5), max_gap=0.5):
        out.append(Event("UNAUTHORIZED_PERSON", t0, 0.7,
                         f"С {fmt_t(t0)} в кассе одновременно {int(x.count[a:b + 1].max())} человека: кроме кассира и "
                         f"клиента у рабочего места находится ещё один человек (около {max(1, round(t1 - t0))} с)."))
    return out


def door_change(x: Ctx, tr: Track) -> float:
    """Median change at the spot where the person appeared, after they moved on (door left open)."""
    sc = x.sc
    b0 = tr.boxes[0]
    region = expand(b0, 0.1 * (b0[2] - b0[0]), 0.1 * (b0[3] - b0[1]), sc.W, sc.H)
    vals = []
    for t in np.arange(tr.start + 2.0, tr.start + 8.0, 0.5):
        if t > x.times[-1]:
            break
        i = sc.t_index(t)
        if not x.normal_light(i):
            continue
        d, known = x.cm.region_diff(i, region)
        if known > 0.5:
            vals.append(d)
    return float(np.median(vals)) if vals else 0.0


def rule_entry_door(x: Ctx) -> list[Event]:
    """Someone walks in and the door behind them stays open; if the cashier was already inside,
    the newcomer is treated as an outsider in the cash room."""
    c = x.cfg.get("door", {})
    out = []
    for tr in x.entries(c.get("min_start", 0.75)):
        d = door_change(x, tr)
        if d < c.get("min_diff", 15.0):
            continue
        i0 = x.sc.t_index(tr.start - 0.5)
        if x.count[max(0, i0 - 2):i0 + 1].max() >= 1:
            out.append(Event("UNAUTHORIZED_PERSON", tr.start, 0.6,
                             f"В {fmt_t(tr.start)}, когда кассир уже на месте, в кассу входит ещё один человек и "
                             f"проходит к рабочему месту кассира; дверь за ним остаётся открытой."))
        else:
            out.append(Event("DOOR_OPEN", tr.start, 0.6,
                             f"В {fmt_t(tr.start)} сотрудник входит в кассу и проходит к рабочему месту; "
                             f"дверь кассы за ним остаётся открытой."))
    return out


def rule_open_area(x: Ctx) -> list[Event]:
    """A large part of the work zone next to the desk looks different from the start and stays so
    (door or safe left open), while lighting is unchanged."""
    c = x.cfg.get("open_area", {})
    sc = x.sc
    step = max(1, int(0.5 / sc.dt))
    hits = []
    for i in range(0, len(x.times), step):
        if not x.normal_light(i):
            continue
        x1, y1, x2, y2 = sc.thumb_box(sc.desk)
        d, k = x.cm.diff(i)
        kk = k[y1:y2, x1:x2]
        if kk.mean() < 0.3:
            continue
        area = float(((d[y1:y2, x1:x2] > c.get("pixel_diff", 30)) & kk).sum() / kk.size)
        hits.append((float(x.times[i]), area))
    if not hits or max(a for _, a in hits) < c.get("min_area", 0.12):
        return []
    thr = c.get("min_area", 0.12) * 0.6
    t0 = next(t for t, a in hits if a >= thr)
    return [Event("DOOR_OPEN", t0, 0.5,
                  f"С {fmt_t(t0)} рядом с рабочим местом кассира остаётся открытой дверь или дверца "
                  f"(значительная часть зоны кассы выглядит иначе, чем в начале записи, и не возвращается в исходное "
                  f"состояние).")]


SMALL = {"cell phone", "remote", "book", "mouse"}


def rule_cash_on_entry(x: Ctx) -> list[Event]:
    """A new person walks up to the desk while small objects (banknote stacks look like phones/remotes/books
    to the detector) lie open on the desk."""
    c = x.cfg.get("cash_on_entry", {})
    sc = x.sc
    desk = expand(sc.desk, 0.05 * sc.cashier_h, 0.05 * sc.cashier_h, sc.W, sc.H)
    out = []
    for tr in x.entries(c.get("min_start", 0.75)):
        i0, i1 = sc.t_index(tr.start - c.get("before", 3.0)), sc.t_index(tr.start + c.get("after", 2.0))
        share = float(np.mean([bool(sc.objects(i, SMALL, 0.3, desk)) for i in range(i0, i1 + 1)]))
        if share >= c.get("min_share", 0.2):
            out.append(Event("CASH_EXPOSED", tr.start, 0.6,
                             f"В {fmt_t(tr.start)} к рабочему месту подходит клиент, в это время на столе кассира "
                             f"открыто лежат мелкие предметы, похожие на пачки купюр, не убранные в сейф или ящик."))
    return out


def rule_short_visit(x: Ctx) -> list[Event]:
    """A visitor comes to the desk and leaves within seconds while the cashier stays."""
    c = x.cfg.get("short_visit", {})
    sc = x.sc
    out = []
    for tr in x.entries(c.get("min_start", 0.75)):
        if tr.end >= x.times[-1] - c.get("end_margin", 1.0):
            continue
        stay = tr.end - tr.start
        if stay < c.get("min_stay", 3.0) or stay > c.get("max_stay", 20.0):
            continue
        ia, ib = sc.t_index(tr.start), sc.t_index(tr.end)
        if x.count[ia:ib + 1].max() < 2:  # the cashier is not there at the same time: not a visit
            continue
        if stay <= c.get("cit_max_stay", 12.0):
            t = tr.start + stay / 2
            out.append(Event("CIT_PROCEDURE", t, 0.5,
                             f"В {fmt_t(tr.start)} к кассиру подходит человек, передаёт предмет (сумку) и уходит через "
                             f"{stay:.0f} с; предъявления документов, проверки сумки и пломбы при нём не видно."))
        else:
            t = max(tr.start, tr.end - 3.0)
            out.append(Event("COUNT_PROCEDURE", t, 0.5,
                             f"В {fmt_t(tr.end)} клиент уходит от кассы через {stay:.0f} с после прихода; "
                             f"пересчёт принятых денег продолжается без клиента."))
    return out


def rule_departure(x: Ctx) -> list[Event]:
    """The cashier walks out of the cash room before the clip ends and nobody stays at the workplace."""
    c = x.cfg.get("departure", {})
    sc = x.sc
    eps = [e for e in episodes(x.count == 0, x.times, c.get("min_empty", 1.0), max_gap=0.6) if e[2] > 0]
    out = []
    for t0, t1, a, b in eps:
        till_end = b >= len(x.times) - 2
        if not till_end and t1 - t0 < c.get("min_away", 5.0):
            continue
        # the cashier stands up and walks to the door a few seconds before the room is seen empty
        t_leave = max(0.0, t0 - c.get("lead", 6.0))
        idx = list(range(a, b + 1))
        white = [d[WHITE] for i in idx for d in sc.tl.dets[i] if d[LABEL] == "laptop" and d[SCORE] >= 0.3]
        lit = bool(white) and float(np.median(white)) >= c.get("screen_white", 0.15)
        tail = "до конца записи" if till_end else f"на {t1 - t0:.0f} с"
        if lit:
            out.append(Event("WORKPLACE_LEFT", t_leave, 0.4,
                             f"В {fmt_t(t_leave)} кассир встаёт и уходит из кассы, рабочее место остаётся без "
                             f"присмотра {tail}; экран компьютера остаётся включённым."))
        else:
            out.append(Event("CASH_UNATTENDED", t_leave, 0.4,
                             f"В {fmt_t(t_leave)} кассир встаёт и уходит из кассы, рабочее место с предметами на "
                             f"столе остаётся без присмотра {tail}."))
    return out


RULES = [rule_crowd, rule_entry_door, rule_open_area, rule_cash_on_entry, rule_short_visit, rule_departure]


def merge(events: list[Event], window: float) -> list[Event]:
    events = sorted(events, key=lambda e: (-e.score, e.t))
    out = []
    for e in events:
        if any(abs(o.t - e.t) < window and (o.code == e.code or o.score > e.score) for o in out):
            continue
        out.append(e)
    return sorted(out, key=lambda e: e.t)


def run(tl, cfg: dict) -> list[Event]:
    if len(tl.times) == 0:
        return []
    sc = build_scene(tl, cfg)
    x = Ctx(sc, cfg.get("rules", {}))
    events = []
    for rule in RULES:
        events += rule(x)
    events = merge(events, cfg.get("merge_window", 4.0))
    dur = float(tl.duration)
    offs = cfg.get("evidence_offsets", [0.0, 1.0, 2.0])
    for e in events:
        e.t = float(min(max(0.0, e.t), max(0.0, dur - 0.1)))
        e.frame_times = sorted({round(min(max(0.0, e.t + o), max(0.0, dur - 0.05)), 2) for o in offs})[:3]
    return events
