"""Simulates the jury: upload a video, poll the job, validate the response shape."""
import sys
import time

import httpx

base, key, video = sys.argv[1], sys.argv[2], sys.argv[3]
h = {"X-API-Key": key}
assert httpx.post(f"{base}/api/v1/analyze", files={"file": ("x.mov", b"0")}).status_code == 401, "no-key request must fail"
t0 = time.time()
with open(video, "rb") as f:
    r = httpx.post(f"{base}/api/v1/analyze", headers=h, files={"file": ("video.mov", f, "video/quicktime")}, timeout=120)
r.raise_for_status()
job_id = r.json()["job_id"]
while True:
    j = httpx.get(f"{base}/api/v1/jobs/{job_id}", headers=h, timeout=30).json()
    if j["status"] != "processing":
        break
    time.sleep(2)
dt = time.time() - t0
assert set(j) <= {"job_id", "status", "verdict", "violations"}, j.keys()
assert j["status"] == "done", j
assert j["verdict"] in ("violation", "no_violation")
for v in j["violations"]:
    assert set(v) == {"type", "timecode_sec", "description", "evidence_frames"}
    assert 1 <= len(v["evidence_frames"]) <= 3
print(f"OK {dt:.1f}s verdict={j['verdict']} violations={len(j['violations'])}")
assert dt < 300, "over the 5-minute limit"
