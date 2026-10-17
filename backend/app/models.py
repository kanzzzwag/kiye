import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc)


class Desk(Base):
    __tablename__ = "desks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch: Mapped[str] = mapped_column(String(200), default="")
    name: Mapped[str] = mapped_column(String(100))


class Employee(Base):
    # no photos or biometrics are stored, by design
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    personnel_no: Mapped[str] = mapped_column(String(50), default="")


class Shift(Base):
    # source of the teller name: who worked at which desk and when
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    desk_id: Mapped[int] = mapped_column(ForeignKey("desks.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    employee: Mapped[Employee] = relationship()


class LegalRule(Base):
    __tablename__ = "legal_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    document_title: Mapped[str] = mapped_column(Text)
    clause: Mapped[str] = mapped_column(String(100), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[str] = mapped_column(String(100), default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    quote: Mapped[str] = mapped_column(Text, default="")


class ViolationType(Base):
    __tablename__ = "violation_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name_ru: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    legal_rule_id: Mapped[int | None] = mapped_column(ForeignKey("legal_rules.id"), nullable=True)
    legal_rule: Mapped[LegalRule | None] = relationship()


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_path: Mapped[str] = mapped_column(Text)
    file_sha256: Mapped[str] = mapped_column(String(64))
    desk_id: Mapped[int | None] = mapped_column(ForeignKey("desks.id"), nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    violations: Mapped[list["Violation"]] = relationship(back_populates="job", order_by="Violation.timecode_sec")


class Violation(Base):
    __tablename__ = "violations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    type_name: Mapped[str] = mapped_column(String(200))
    violation_type_id: Mapped[int | None] = mapped_column(ForeignKey("violation_types.id"), nullable=True)
    timecode_sec: Mapped[float] = mapped_column(Float)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(Text)
    legal_text: Mapped[str] = mapped_column(Text, default="")
    review_status: Mapped[str] = mapped_column(String(20), default="new")  # new | confirmed | rejected
    review_comment: Mapped[str] = mapped_column(Text, default="")
    job: Mapped[Job] = relationship(back_populates="violations")
    employee: Mapped[Employee | None] = relationship()
    violation_type: Mapped[ViolationType | None] = relationship()
    frames: Mapped[list["EvidenceFrame"]] = relationship(order_by="EvidenceFrame.timestamp_sec")


class EvidenceFrame(Base):
    __tablename__ = "evidence_frames"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    violation_id: Mapped[int] = mapped_column(ForeignKey("violations.id"))
    timestamp_sec: Mapped[float] = mapped_column(Float)
    path: Mapped[str] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
