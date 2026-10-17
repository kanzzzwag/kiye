"""Seed data: violation types and legal norms (always synced from legal_rules.json),
plus demo desks, employees and shifts (fictional names, only when the desks table is empty).

python -m app.seed            # types + norms + demo data if empty
python -m app.seed --no-demo  # types + norms only
"""

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select

from ..db import SessionLocal
from ..ml import legal
from ..models import Desk, Employee, LegalRule, Shift, ViolationType

ALMATY = timezone(timedelta(hours=5))

DEMO_DESKS = [("Филиал «Демо-Центр», г. Алматы", "Касса 1"), ("Филиал «Демо-Центр», г. Алматы", "Касса 2"),
              ("Филиал «Демо-Восток», г. Астана", "Касса 1")]
# fictional people, no photos or biometrics
DEMO_EMPLOYEES = [("Айгерим Демонова", "D-0001"), ("Данияр Тестов", "D-0002"), ("Мария Образцова", "D-0003"),
                  ("Ерлан Примеров", "D-0004"), ("Сауле Учебная", "D-0005"), ("Тимур Макетов", "D-0006")]


def sync_norms(db):
    data = legal.load()
    by_code = {}
    for r in data["rules"]:
        doc = data["documents"][r["document"]]
        row = db.scalars(select(LegalRule).where(LegalRule.code == r["id"])).first() or LegalRule(code=r["id"])
        row.document_title = doc["short"]
        row.clause = r.get("clause", "")
        row.url = doc["url"]
        row.verified = bool(r.get("verified"))
        row.quote = r.get("quote", "")
        row.verified_by = row.verified_by or ""
        db.add(row)
        by_code[r["id"]] = row
    db.flush()
    for t in data["types"]:
        row = db.scalars(select(ViolationType).where(ViolationType.code == t["code"])).first() \
            or ViolationType(code=t["code"])
        row.name_ru = t["name_ru"]
        row.description = t.get("description", "")
        row.legal_rule_id = by_code[t["rule_id"]].id
        db.add(row)


def seed_demo(db, days_back=60, days_forward=60):
    if db.scalars(select(Desk)).first():
        return False
    desks = [Desk(branch=b, name=n) for b, n in DEMO_DESKS]
    emps = [Employee(full_name=n, personnel_no=p) for n, p in DEMO_EMPLOYEES]
    db.add_all(desks + emps)
    db.flush()
    today = datetime.now(ALMATY).date()
    for k in range(-days_back, days_forward + 1):
        day = today + timedelta(days=k)
        for di, desk in enumerate(desks):
            # two shifts a day per desk; who works rotates by day
            morning = emps[(di * 2 + k) % len(emps)]
            evening = emps[(di * 2 + k + 1) % len(emps)]
            db.add(Shift(employee_id=morning.id, desk_id=desk.id,
                         starts_at=datetime.combine(day, time(8, 0), ALMATY),
                         ends_at=datetime.combine(day, time(14, 0), ALMATY)))
            db.add(Shift(employee_id=evening.id, desk_id=desk.id,
                         starts_at=datetime.combine(day, time(14, 0), ALMATY),
                         ends_at=datetime.combine(day, time(20, 0), ALMATY)))
    return True


def run(demo: bool = True):
    db = SessionLocal()
    try:
        sync_norms(db)
        added = seed_demo(db) if demo else False
        db.commit()
        return added
    finally:
        db.close()
