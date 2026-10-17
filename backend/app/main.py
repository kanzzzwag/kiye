import base64
import hashlib
import hmac
import os
import subprocess
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import jobqueue
from .config import settings
from .db import SessionLocal, init_db
from .models import AuditLog, Job, Violation
from .schemas import AnalyzeOut, EvidenceFrameOut, JobOut, ViolationOut

app = FastAPI(title="ForteGuard API", version="0.1")
init_db()
os.makedirs(os.path.join(settings.storage_dir, "videos"), exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_key(x_api_key: str | None = Header(default=None)):
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def probe_duration(path: str) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=20,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


@app.get("/healthz")
def healthz():
    return {"ok": True, "model_version": settings.model_version}


@app.post("/api/v1/analyze", response_model=AnalyzeOut, dependencies=[Depends(require_key)])
async def analyze(
    file: UploadFile = File(...),
    desk_id: int | None = Form(default=None),
    recorded_at: datetime | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if not (file.filename or "").lower().endswith((".mov", ".mp4")):
        raise HTTPException(400, "Only .mov or .mp4 files are accepted")
    job_id = uuid.uuid4().hex
    path = os.path.join(settings.storage_dir, "videos", f"{job_id}.mov")
    sha, size, limit = hashlib.sha256(), 0, settings.max_upload_mb * 1024 * 1024
    with open(path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                f.close()
                os.remove(path)
                raise HTTPException(413, "File too large")
            sha.update(chunk)
            f.write(chunk)
    dur = probe_duration(path)
    if dur is None or dur <= 0 or dur > settings.max_video_sec:
        os.remove(path)
        raise HTTPException(400, "Not a readable video or too long")
    db.add(Job(id=job_id, file_path=path, file_sha256=sha.hexdigest(), desk_id=desk_id,
               recorded_at=recorded_at, model_version=settings.model_version))
    db.commit()
    jobqueue.enqueue(job_id)
    return AnalyzeOut(job_id=job_id)


@app.get("/api/v1/jobs/{job_id}", response_model=JobOut, response_model_exclude_none=True,
         dependencies=[Depends(require_key)])
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "done":
        return JobOut(job_id=job.id, status=job.status)
    out = []
    for v in job.violations:
        frames = []
        for fr in v.frames:
            with open(fr.path, "rb") as f:
                frames.append(EvidenceFrameOut(timestamp_sec=round(fr.timestamp_sec, 2),
                                               image_base64=base64.b64encode(f.read()).decode()))
        out.append(ViolationOut(type=v.type_name, timecode_sec=round(v.timecode_sec, 2),
                                description=v.description, evidence_frames=frames))
    return JobOut(job_id=job.id, status="done", verdict=job.verdict, violations=out)


# ---- internal endpoints for our own UI (not part of the jury spec) ----

@app.get("/api/internal/violations", dependencies=[Depends(require_key)])
def list_violations(db: Session = Depends(get_db)):
    rows = db.scalars(select(Violation).order_by(Violation.id.desc()).limit(500)).all()
    return [
        {
            "id": v.id, "job_id": v.job_id, "type": v.type_name, "timecode_sec": v.timecode_sec,
            "occurred_at": v.occurred_at, "created_at": v.job.created_at,
            "legal": (v.violation_type.legal_rule.document_title + " " + v.violation_type.legal_rule.clause)
            if v.violation_type and v.violation_type.legal_rule else "",
            "teller": v.employee.full_name if v.employee else "",
            "review_status": v.review_status, "review_comment": v.review_comment,
        }
        for v in rows
    ]


@app.patch("/api/internal/violations/{vid}", dependencies=[Depends(require_key)])
def review_violation(vid: int, body: dict, db: Session = Depends(get_db)):
    v = db.get(Violation, vid)
    if not v:
        raise HTTPException(404)
    status = body.get("review_status")
    if status not in (None, "new", "confirmed", "rejected"):
        raise HTTPException(400, "bad review_status")
    if status:
        v.review_status = status
    if "review_comment" in body:
        v.review_comment = str(body["review_comment"])[:2000]
    db.add(AuditLog(actor="ui", action="review", entity="violation", entity_id=str(vid), payload=str(body)[:2000]))
    db.commit()
    return {"ok": True}


@app.get("/api/internal/frames/{job_id}/{name}", dependencies=[Depends(require_key)])
def frame(job_id: str, name: str):
    if not job_id.isalnum() or "/" in name or ".." in name:
        raise HTTPException(400)
    p = os.path.join(settings.storage_dir, "frames", job_id, name)
    if not os.path.isfile(p):
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


_frontend = os.environ.get("FRONTEND_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.isdir(_frontend):
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
