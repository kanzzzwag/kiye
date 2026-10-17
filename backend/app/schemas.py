"""Response schema fixed by the jury spec. Do not add or rename fields here."""
from typing import Literal

from pydantic import BaseModel


class EvidenceFrameOut(BaseModel):
    timestamp_sec: float
    image_base64: str


class ViolationOut(BaseModel):
    type: str
    timecode_sec: float
    description: str
    evidence_frames: list[EvidenceFrameOut]


class JobOut(BaseModel):
    job_id: str
    status: Literal["processing", "done", "failed"]
    verdict: Literal["violation", "no_violation"] | None = None
    violations: list[ViolationOut] = []


class AnalyzeOut(BaseModel):
    job_id: str
