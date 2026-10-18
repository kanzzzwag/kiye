"""Contract test: the jury response shape (app/schemas.py) and API hygiene, with the analyzer stubbed."""
import base64
import os
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

KEY = os.environ["API_KEY"]
H = {"X-API-Key": KEY}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from app import analyzer

    def fake_analyze(path, progress=None):
        if progress:
            progress(0.5)
        return [analyzer.Detected(type="Ценности без присмотра", code="CASH_UNATTENDED", timecode_sec=1.0,
                                  description="Тест. Норма: Документ, п. 1.", confidence=0.9,
                                  frame_times=[1.0, 2.0, 3.0], legal_text="Норма: Документ, п. 1.")]

    analyzer.analyze = fake_analyze
    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    subprocess.run([sys.executable, os.path.join(root, "scripts", "make_synthetic.py"), str(d), "1"], check=True)
    return os.path.join(d, "synthetic_1.mov")


def wait_done(client, job_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/v1/jobs/{job_id}", headers=H).json()
        if j["status"] != "processing":
            return j
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_no_key_rejected(client):
    assert client.post("/api/v1/analyze", files={"file": ("x.mov", b"0")}).status_code == 401
    assert client.get("/api/v1/jobs/abc", headers={"X-API-Key": "wrong"}).status_code == 401


def test_not_a_video_rejected(client):
    r = client.post("/api/v1/analyze", headers=H, files={"file": ("x.mov", b"not a video at all")})
    assert r.status_code == 400
    r = client.post("/api/v1/analyze", headers=H, files={"file": ("x.avi", b"0")})
    assert r.status_code == 400


def test_response_schema(client, video):
    with open(video, "rb") as f:
        r = client.post("/api/v1/analyze", headers=H, files={"file": ("v.mov", f, "video/quicktime")})
    assert r.status_code == 200 and set(r.json()) == {"job_id"}
    j = wait_done(client, r.json()["job_id"])
    assert set(j) <= {"job_id", "status", "verdict", "violations"}
    assert j["status"] == "done" and j["verdict"] in ("violation", "no_violation")
    assert j["verdict"] == "violation"
    for v in j["violations"]:
        assert set(v) == {"type", "timecode_sec", "description", "evidence_frames"}
        assert isinstance(v["timecode_sec"], float)
        assert 1 <= len(v["evidence_frames"]) <= 3
        for fr in v["evidence_frames"]:
            assert set(fr) == {"timestamp_sec", "image_base64"}
            assert base64.b64decode(fr["image_base64"])[:2] == b"\xff\xd8"  # JPEG
        assert "Норма:" in v["description"]


def test_processing_shape(client):
    from app.db import SessionLocal
    from app.models import Job

    db = SessionLocal()
    db.add(Job(id="p" * 32, file_path="/nonexistent", file_sha256="0" * 64, model_version="t"))
    db.commit()
    db.close()
    j = client.get("/api/v1/jobs/" + "p" * 32, headers=H).json()
    assert j == {"job_id": "p" * 32, "status": "processing", "violations": []}


def test_unknown_job_404_without_trace(client):
    r = client.get("/api/v1/jobs/doesnotexist", headers=H)
    assert r.status_code == 404
    assert "Traceback" not in r.text


def test_security_headers(client):
    r = client.get("/healthz")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
    r = client.get("/healthz", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_journal_filters_and_csv(client, video):
    rows = client.get("/api/internal/violations", headers=H).json()
    assert rows and rows[0]["legal"].startswith("Норма:")
    assert client.get("/api/internal/violations?type=CASH_UNATTENDED", headers=H).json()
    assert client.get("/api/internal/violations?type=DOOR_OPEN", headers=H).json() == []
    assert client.get("/api/internal/violations?status=bogus", headers=H).status_code == 422
    r = client.get("/api/internal/violations.csv?status=new", headers=H)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "Норма" in r.content.decode("utf-8-sig").splitlines()[0]
    types = client.get("/api/internal/types", headers=H).json()
    assert {"CASH_UNATTENDED", "SUSPICIOUS_ACTION"} <= {t["code"] for t in types}


def test_rate_limit():
    from app.security import RateLimiter

    rl = RateLimiter(3)
    assert [rl.hit("k", "1.2.3.4") for _ in range(4)] == [True, True, True, False]
    assert rl.hit("k", "5.6.7.8")  # other IP has its own budget


def test_public_types_without_key(client):
    r = client.get("/api/public/types")
    assert r.status_code == 200
    types = r.json()
    assert {"CASH_UNATTENDED", "FOOD_DRINK"} <= {t["code"] for t in types}
    assert all(t["name"] and t["ref"] for t in types)
    assert any(t["ref"].startswith("№231 п.") for t in types)


def test_job_details_for_ui(client, video):
    with open(video, "rb") as f:
        job_id = client.post("/api/v1/analyze", headers=H, files={"file": ("v.mov", f, "video/quicktime")}).json()["job_id"]
    wait_done(client, job_id)
    d = client.get(f"/api/internal/jobs/{job_id}", headers=H).json()
    v = d["violations"][0]
    assert v["seen"] == "Тест." and v["why"] and v["law"]["act"] and v["frames"]
    assert "elapsed_sec" in d


def test_docs_page_has_no_cdn(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "cdn." not in r.text and "unpkg" not in r.text
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]
    assert client.get("/openapi.json").status_code == 200
