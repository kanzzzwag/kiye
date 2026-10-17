"""legal rule code/verified/quote, type description, job progress, violation legal text, journal indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("legal_rules") as b:
        b.add_column(sa.Column("code", sa.String(50), nullable=True))
        b.add_column(sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("quote", sa.Text, nullable=False, server_default=""))
        b.create_unique_constraint("uq_legal_rules_code", ["code"])
    with op.batch_alter_table("violation_types") as b:
        b.add_column(sa.Column("description", sa.Text, nullable=False, server_default=""))
    with op.batch_alter_table("jobs") as b:
        b.add_column(sa.Column("progress", sa.Float, nullable=False, server_default="0"))
    with op.batch_alter_table("violations") as b:
        b.add_column(sa.Column("legal_text", sa.Text, nullable=False, server_default=""))
    op.create_index("ix_violations_job_id", "violations", ["job_id"])
    op.create_index("ix_violations_review_status", "violations", ["review_status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_shifts_desk_time", "shifts", ["desk_id", "starts_at", "ends_at"])


def downgrade():
    op.drop_index("ix_shifts_desk_time", "shifts")
    op.drop_index("ix_jobs_created_at", "jobs")
    op.drop_index("ix_violations_review_status", "violations")
    op.drop_index("ix_violations_job_id", "violations")
    with op.batch_alter_table("violations") as b:
        b.drop_column("legal_text")
    with op.batch_alter_table("jobs") as b:
        b.drop_column("progress")
    with op.batch_alter_table("violation_types") as b:
        b.drop_column("description")
    with op.batch_alter_table("legal_rules") as b:
        b.drop_constraint("uq_legal_rules_code", type_="unique")
        b.drop_column("quote")
        b.drop_column("verified")
        b.drop_column("code")
