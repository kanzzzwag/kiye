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


def _wall(dt: datetime) -> datetime:
    """Almaty wall-clock time without tzinfo (SQLite returns naive values, PostgreSQL aware ones)."""
    return dt if dt.tzinfo is None else dt.astimezone(ALMATY).replace(tzinfo=None)


def seed_demo(db, days_back=60, days_forward=60):
    """Demo desks and employees once; shifts for +-60 days are topped up on every start (idempotent).
    Two 12-hour shifts a day (08-20 and 20-08 Almaty time) so a demo upload at any hour finds a teller."""
    added = False
    desks = db.scalars(select(Desk).order_by(Desk.id)).all()
    if not desks:
        desks = [Desk(branch=b, name=n) for b, n in DEMO_DESKS]
        db.add_all(desks + [Employee(full_name=n, personnel_no=p) for n, p in DEMO_EMPLOYEES])
        db.flush()
        added = True
    emps = db.scalars(select(Employee).where(Employee.personnel_no.like("D-%")).order_by(Employee.id)).all()
    if not emps:
        return added
    existing = {(s.desk_id, _wall(s.starts_at)) for s in db.scalars(select(Shift))}
    today = datetime.now(ALMATY).date()
    for k in range(-days_back, days_forward + 1):
        day = today + timedelta(days=k)
        for di, desk in enumerate(desks):
            for j, (start, hours) in enumerate(((time(8, 0), 12), (time(20, 0), 12))):
                starts = datetime.combine(day, start, ALMATY)
                if (desk.id, _wall(starts)) in existing:
                    continue
                emp = emps[(di * 2 + k + j) % len(emps)]  # who works rotates by day
                db.add(Shift(employee_id=emp.id, desk_id=desk.id, starts_at=starts, ends_at=starts + timedelta(hours=hours)))
                added = True
    return added


def run(demo: bool = True):
    db = SessionLocal()
    try:
        sync_norms(db)
        added = seed_demo(db) if demo else False
        db.commit()
        return added
    finally:
        db.close()
