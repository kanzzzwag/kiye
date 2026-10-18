import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import subprocess
import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import jobqueue, seed
from .ml import legal
from .config import settings
from .db import SessionLocal, init_db
from .models import AuditLog, Job, Violation, ViolationType
from .schemas import AnalyzeOut, EvidenceFrameOut, JobOut, ViolationOut
from .security import SECURITY_HEADERS, check_rate

log = logging.getLogger("forteguard")

app = FastAPI(title="ForteGuard API", version="1.0")
init_db()
seed.run(demo=settings.seed_demo)
os.makedirs(os.path.join(settings.storage_dir, "videos"), exist_ok=True)

if settings.cors_origins.strip():
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                       allow_methods=["GET", "POST", "PATCH"], allow_headers=["X-API-Key", "Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # field names only, no echo of submitted values
    fields = sorted({".".join(str(p) for p in e.get("loc", [])[1:]) or "body" for e in exc.errors()})
    return JSONResponse({"detail": "Invalid request", "fields": fields}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)  # full trace stays in the server log
    return JSONResponse({"detail": "Internal error"}, status_code=500)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_key(x_api_key: str | None = Header(default=None)):
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), settings.api_key.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    return x_api_key


VIDEO_FORMATS = {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}  # ffprobe names the QuickTime/MP4 family "mov,mp4,..."


def probe_video(path: str) -> float | None:
    """Duration in seconds if ffprobe sees a QuickTime/MP4 container with a video stream, else None."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,format_name:stream=codec_type",
             "-of", "json", path],
            capture_output=True, text=True, timeout=20,
        )
        info = json.loads(out.stdout or "{}")
        fmt = info.get("format", {})
        if not set(fmt.get("format_name", "").split(",")) & VIDEO_FORMATS:
            return None
        if not any(s.get("codec_type") == "video" for s in info.get("streams", [])):
            return None
        return float(fmt.get("duration"))
    except Exception:
        return None


@app.get("/healthz")
def healthz():
    return {"ok": True, "model_version": settings.model_version}


@app.post("/api/v1/analyze", response_model=AnalyzeOut)
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    desk_id: int | None = Form(default=None),
    recorded_at: datetime | None = Form(default=None),
    db: Session = Depends(get_db),
    key: str = Depends(require_key),
):
    check_rate(request, key)
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
    dur = probe_video(path)
    if dur is None or dur <= 0 or dur > settings.max_video_sec:
        os.remove(path)
        raise HTTPException(400, "Not a readable .mov/.mp4 video or too long")
    if recorded_at is not None and recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    db.add(Job(id=job_id, file_path=path, file_sha256=sha.hexdigest(), desk_id=desk_id,
               recorded_at=recorded_at, model_version=settings.model_version))
    db.add(AuditLog(actor="api", action="upload", entity="job", entity_id=job_id,
                    payload=json.dumps({"size": size, "duration": round(dur, 2), "desk_id": desk_id})))
    db.commit()
    jobqueue.enqueue(job_id)
    return AnalyzeOut(job_id=job_id)


def _job_out(job: Job) -> JobOut:
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


@app.get("/api/v1/jobs/{job_id}", response_model=JobOut, response_model_exclude_none=True,
         dependencies=[Depends(require_key)])
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id) if job_id.isalnum() else None
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_out(job)


# ---- internal endpoints for our own UI (not part of the jury spec) ----

@app.get("/api/internal/jobs/{job_id}", dependencies=[Depends(require_key)])
def job_progress(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id) if job_id.isalnum() else None
    if not job:
        raise HTTPException(404, "Job not found")
    out = {"job_id": job.id, "status": job.status, "progress": round(job.progress or 0.0, 3), "violations": []}
    if job.finished_at and job.created_at:
        out["elapsed_sec"] = round((job.finished_at - job.created_at).total_seconds(), 1)
    if job.status != "done":
        return out
    types = legal.load()["types_by_code"]
    for v in job.violations:
        code = v.violation_type.code if v.violation_type else ""
        rule = v.violation_type.legal_rule if v.violation_type else None
        out["violations"].append({
            "id": v.id, "code": code, "type": v.type_name, "timecode_sec": v.timecode_sec,
            "seen": v.description.split(" Норма:")[0].strip(),
            "why": types.get(code, {}).get("why", ""),
            "legal": v.legal_text,
            "law": {"act": rule.document_title, "clause": rule.clause, "quote": rule.quote, "url": rule.url,
                    "verified": rule.verified} if rule else None,
            "frames": [{"t": fr.timestamp_sec, "url": f"/api/internal/frames/{job.id}/{os.path.basename(fr.path)}"}
                       for fr in v.frames],
        })
    return out


@app.get("/api/public/types")
def public_types():
    """What the service looks for, with the norm reference (no key needed: no case data here)."""
    d = legal.load()
    return [{"code": t["code"], "name": t["name_ru"], "ref": legal.short_ref(t["rule_id"]),
             "description": t.get("description", ""), "why": t.get("why", "")} for t in d["types"]]


@app.get("/api/internal/types", dependencies=[Depends(require_key)])
def list_types(db: Session = Depends(get_db)):
    return [{"code": t.code, "name": t.name_ru} for t in db.scalars(select(ViolationType).order_by(ViolationType.id))]


def _filtered(db, date_from, date_to, type_code, status, limit=1000):
    q = select(Violation).join(Job).order_by(Violation.id.desc())
    if date_from:
        q = q.where(Job.created_at >= datetime.combine(date_from, time.min, timezone.utc))
    if date_to:
        q = q.where(Job.created_at < datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc))
    if type_code:
        q = q.join(ViolationType, Violation.violation_type_id == ViolationType.id).where(ViolationType.code == type_code)
    if status:
        q = q.where(Violation.review_status == status)
    return db.scalars(q.limit(limit)).all()


def _row(v: Violation) -> dict:
    return {
        "id": v.id, "job_id": v.job_id, "type": v.type_name,
        "code": v.violation_type.code if v.violation_type else "",
        "timecode_sec": v.timecode_sec, "occurred_at": v.occurred_at, "created_at": v.job.created_at,
        "description": v.description, "legal": v.legal_text,
        "teller": v.employee.full_name if v.employee else "",
        "review_status": v.review_status, "review_comment": v.review_comment,
    }


@app.get("/api/internal/violations", dependencies=[Depends(require_key)])
def list_violations(date_from: date | None = None, date_to: date | None = None,
                    type: str | None = Query(default=None, max_length=50),
                    status: str | None = Query(default=None, pattern="^(new|confirmed|rejected)$"),
                    db: Session = Depends(get_db)):
    return [_row(v) for v in _filtered(db, date_from, date_to, type, status, limit=500)]


def _csv_cell(v) -> str:
    s = "" if v is None else (v.isoformat() if isinstance(v, datetime) else str(v))
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s  # no formula injection in Excel


@app.get("/api/internal/violations.csv", dependencies=[Depends(require_key)])
def export_violations(date_from: date | None = None, date_to: date | None = None,
                      type: str | None = Query(default=None, max_length=50),
                      status: str | None = Query(default=None, pattern="^(new|confirmed|rejected)$"),
                      db: Session = Depends(get_db)):
    cols = [("id", "ID"), ("created_at", "Загружено"), ("occurred_at", "Время события"), ("job_id", "Задача"),
            ("code", "Код"), ("type", "Тип"), ("timecode_sec", "Таймкод, с"), ("teller", "Кассир"),
            ("legal", "Норма"), ("description", "Описание"), ("review_status", "Статус"), ("review_comment", "Комментарий")]
    buf = io.StringIO()
    buf.write("﻿")  # Excel opens UTF-8 Cyrillic correctly with a BOM
    w = csv.writer(buf, delimiter=";")
    w.writerow([c[1] for c in cols])
    for v in _filtered(db, date_from, date_to, type, status, limit=100000):
        r = _row(v)
        w.writerow([_csv_cell(r[c[0]]) for c in cols])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="violations.csv"'})


@app.patch("/api/internal/violations/{vid}", dependencies=[Depends(require_key)])
def review_violation(vid: int, body: dict, db: Session = Depends(get_db)):
    v = db.get(Violation, vid)
    if not v:
        raise HTTPException(404, "Not found")
    status = body.get("review_status")
    if status not in (None, "new", "confirmed", "rejected"):
        raise HTTPException(400, "bad review_status")
    if status:
        v.review_status = status
    if "review_comment" in body:
        v.review_comment = str(body["review_comment"])[:2000]
    db.add(AuditLog(actor="ui", action="review", entity="violation", entity_id=str(vid),
                    payload=json.dumps({k: body.get(k) for k in ("review_status", "review_comment") if k in body},
                                       ensure_ascii=False)[:2000]))
    db.commit()
    return {"ok": True}


@app.get("/api/internal/frames/{job_id}/{name}", dependencies=[Depends(require_key)])
def frame(job_id: str, name: str):
    if not job_id.isalnum() or "/" in name or "\\" in name or ".." in name or not name.endswith(".jpg"):
        raise HTTPException(400, "Bad path")
    p = os.path.join(settings.storage_dir, "frames", job_id, name)
    if not os.path.isfile(p):
        raise HTTPException(404, "Not found")
    return FileResponse(p, media_type="image/jpeg")


_frontend = os.environ.get("FRONTEND_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.isdir(_frontend):
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
