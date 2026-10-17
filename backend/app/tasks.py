import os
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import analyzer
from .config import settings
from .db import SessionLocal
from .models import Job, Shift, Violation, ViolationType, EvidenceFrame


def find_teller(db, desk_id, at):
    if desk_id is None or at is None:
        return None
    q = select(Shift).where(Shift.desk_id == desk_id, Shift.starts_at <= at, Shift.ends_at >= at)
    shift = db.scalars(q).first()
    return shift.employee_id if shift else None


def run_job(job_id: str):
    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        found = analyzer.analyze(job.file_path)
        frames_dir = os.path.join(settings.storage_dir, "frames", job_id)
        os.makedirs(frames_dir, exist_ok=True)
        for i, d in enumerate(found):
            occurred = job.recorded_at + timedelta(seconds=d.timecode_sec) if job.recorded_at else None
            vtype = db.scalars(select(ViolationType).where(ViolationType.code == d.code)).first()
            v = Violation(
                job_id=job_id, type_name=d.type, timecode_sec=d.timecode_sec, description=d.description,
                confidence=d.confidence, occurred_at=occurred, violation_type=vtype,
                employee_id=find_teller(db, job.desk_id, occurred),
            )
            db.add(v)
            db.flush()
            for t, jpg in analyzer.grab_frames(job.file_path, d.frame_times):
                p = os.path.join(frames_dir, f"{i}_{t:.2f}.jpg")
                with open(p, "wb") as f:
                    f.write(jpg)
                db.add(EvidenceFrame(violation_id=v.id, timestamp_sec=t, path=p))
        job.verdict = "violation" if found else "no_violation"
        job.status = "done"
    except Exception:
        db.rollback()
        job = db.get(Job, job_id)
        job.status = "failed"
        job.error = traceback.format_exc()[-2000:]
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.close()
