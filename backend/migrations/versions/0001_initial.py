"""initial schema (as created by the first skeleton)

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "desks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("branch", sa.String(200), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
    )
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("personnel_no", sa.String(50), nullable=False),
    )
    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("desk_id", sa.Integer, sa.ForeignKey("desks.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "legal_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_title", sa.Text, nullable=False),
        sa.Column("clause", sa.String(100), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("verified_by", sa.String(100), nullable=False),
    )
    op.create_table(
        "violation_types",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name_ru", sa.String(200), nullable=False),
        sa.Column("legal_rule_id", sa.Integer, sa.ForeignKey("legal_rules.id"), nullable=True),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("verdict", sa.String(20), nullable=True),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("desk_id", sa.Integer, sa.ForeignKey("desks.id"), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "violations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_id", sa.String(32), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("type_name", sa.String(200), nullable=False),
        sa.Column("violation_type_id", sa.Integer, sa.ForeignKey("violation_types.id"), nullable=True),
        sa.Column("timecode_sec", sa.Float, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False),
        sa.Column("review_comment", sa.Text, nullable=False),
    )
    op.create_table(
        "evidence_frames",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("violation_id", sa.Integer, sa.ForeignKey("violations.id"), nullable=False),
        sa.Column("timestamp_sec", sa.Float, nullable=False),
        sa.Column("path", sa.Text, nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    for t in ("audit_log", "evidence_frames", "violations", "jobs", "violation_types", "legal_rules",
              "shifts", "employees", "desks"):
        op.drop_table(t)
