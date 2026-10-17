"""Rules on synthetic timelines: hand-made detections and thumbnails, no model and no video needed."""
import numpy as np
import pytest

from app.ml import legal, rules
from app.ml.features import SMALL_W, Timeline

W, H, DT = 464, 848, 0.25
CASHIER = (180, 380, 280, 590)  # seated cashier, the same place all the time
DESK_OBJ = [("laptop", 0.8, 240, 360, 300, 440), ("suitcase", 0.6, 40, 400, 115, 490)]


def person(box, score=0.9):
    return ("person", score, *box, 40.0, 60.0, 110.0, 0.0)


def obj(o):
    return (*o, 30.0, 30.0, 120.0, 0.05)


def make_tl(duration, frame_fn, light_fn=None):
    """frame_fn(t) -> list of detection tuples; thumbnails are flat grey (no scene change) unless light_fn."""
    times = np.round(np.arange(0, duration, DT), 3)
    dets = [[*frame_fn(t)] for t in times]
    hs = int(H * SMALL_W / W)
    small = np.full((len(times), hs, SMALL_W, 3), 128, np.uint8)
    if light_fn:
        for i, t in enumerate(times):
            small[i] = np.uint8(np.clip(128 * light_fn(t), 0, 255))
    tl = Timeline(duration, W, H, times, dets, small)
    tl.stats = {"sec": 0.0}
    return tl


@pytest.fixture(scope="module")
def cfg():
    return rules.load_config()


def codes(events):
    return [e.code for e in events]


def test_quiet_cashier_no_events(cfg):
    tl = make_tl(30, lambda t: [person(CASHIER)] + [obj(o) for o in DESK_OBJ])
    assert rules.run(tl, cfg) == []


def test_third_person_is_unauthorized(cfg):
    client = (165, 300, 235, 425)
    intruder = (30, 200, 120, 430)

    def f(t):
        out = [person(CASHIER), person(client)] + [obj(o) for o in DESK_OBJ]
        if 10 <= t <= 16:
            out.append(person(intruder))
        return out

    ev = rules.run(make_tl(25, f), cfg)
    hit = [e for e in ev if e.code == "UNAUTHORIZED_PERSON"]
    assert hit and abs(hit[0].t - 10) <= 1.0
    assert "3 человека" in hit[0].details


def test_short_visit_is_cit_procedure(cfg):
    visitor = (60, 200, 160, 420)

    def f(t):
        out = [person(CASHIER)] + [obj(o) for o in DESK_OBJ]
        if 4 <= t <= 12:
            out.append(person(visitor))
        return out

    ev = rules.run(make_tl(25, f), cfg)
    assert "CIT_PROCEDURE" in codes(ev)
    e = next(e for e in ev if e.code == "CIT_PROCEDURE")
    assert 6 <= e.t <= 10


def test_long_client_visit_is_normal(cfg):
    client = (165, 300, 235, 425)

    def f(t):
        out = [person(CASHIER)] + [obj(o) for o in DESK_OBJ]
        if 3 <= t <= 40:
            out.append(person(client))
        return out

    assert rules.run(make_tl(45, f), cfg) == []


def test_new_client_while_cash_on_desk(cfg):
    client = (165, 300, 235, 425)
    cash = ("remote", 0.45, 140, 435, 168, 452)

    def f(t):
        out = [person(CASHIER)] + [obj(o) for o in DESK_OBJ] + [obj(cash)]
        if t >= 12:
            out.append(person(client))
        return out

    ev = rules.run(make_tl(25, f), cfg)
    hit = [e for e in ev if e.code == "CASH_EXPOSED"]
    assert hit and abs(hit[0].t - 12) <= 1.0


def test_cashier_leaves_until_end(cfg):
    def f(t):
        out = [obj(o) for o in DESK_OBJ]
        if t < 16:
            out.append(person(CASHIER))
        return out

    ev = rules.run(make_tl(20, f), cfg)
    hit = [e for e in ev if e.code in ("CASH_UNATTENDED", "WORKPLACE_LEFT")]
    assert hit and abs(hit[0].t - (16 - cfg["rules"]["departure"]["lead"])) <= 1.0


def test_short_absence_is_not_a_departure(cfg):
    def f(t):
        out = [obj(o) for o in DESK_OBJ]
        if not 10 <= t <= 12:
            out.append(person(CASHIER))
        return out

    assert rules.run(make_tl(25, f), cfg) == []


def test_lights_off_do_not_fire_change_rules(cfg):
    def f(t):
        return [person(CASHIER)] + [obj(o) for o in DESK_OBJ]

    ev = rules.run(make_tl(20, f, light_fn=lambda t: 1.0 if t < 10 else 0.5), cfg)
    assert "DOOR_OPEN" not in codes(ev)


def test_evidence_frames_and_description(cfg):
    def f(t):
        return [obj(o) for o in DESK_OBJ] + ([person(CASHIER)] if t < 16 else [])

    for e in rules.run(make_tl(20, f), cfg):
        assert 1 <= len(e.frame_times) <= 3
        assert all(0 <= x <= 20 for x in e.frame_times)
        assert e.frame_times[0] == pytest.approx(e.t, abs=0.05)
        assert e.full_description.rstrip().endswith(".")
        assert "Норма:" in e.full_description


def test_norm_text_never_invents_a_clause():
    data = legal.load()
    for t in data["types"]:
        text = legal.norm_text(t["code"])
        rule = data["rules_by_id"][t["rule_id"]]
        assert text.startswith("Норма: ")
        if rule.get("clause"):
            assert rule["clause"] in text
        else:
            assert "п. " not in text  # no clause in the source -> no clause in the output
        assert ("требует проверки" in text) == (not rule.get("verified"))


def test_merge_keeps_strongest_nearby():
    a = rules.Event("DOOR_OPEN", 10.0, 0.5, "a")
    b = rules.Event("UNAUTHORIZED_PERSON", 11.0, 0.6, "b")
    c = rules.Event("DOOR_OPEN", 30.0, 0.5, "c")
    assert codes(rules.merge([a, b, c], 4.0)) == ["UNAUTHORIZED_PERSON", "DOOR_OPEN"]


def test_manual_zones_override(cfg):
    from app.ml.scene import build_scene

    tl = make_tl(10, lambda t: [person(CASHIER)] + [obj(o) for o in DESK_OBJ])
    manual = {**cfg, "manual_zones": {"desk": [0.1, 0.4, 0.7, 0.6], "zone": None}}
    sc = build_scene(tl, manual)
    assert sc.desk == pytest.approx([0.1 * W, 0.4 * H, 0.7 * W, 0.6 * H])
    auto = build_scene(tl, cfg)
    assert auto.desk != sc.desk
