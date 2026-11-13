"""Jobs, rubric_criteria, llm_calls (Phase 2).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13 23:40:16.529441
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column(
            "employment_type",
            sa.Enum("full_time", "part_time", "contract", "internship", name="employment_type"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "open", "closed", name="job_status"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("blind_mode", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_jobs_created_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_jobs_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("slug", name=op.f("uq_jobs_slug")),
    )
    op.create_index(op.f("ix_jobs_org_id"), "jobs", ["org_id"], unique=False)
    op.create_index(
        "ix_jobs_org_id_created_at_id", "jobs", ["org_id", "created_at", "id"], unique=False
    )
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum("jd_parse", "resume_parse", "screen", "chat", "questions", name="llm_purpose"),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_llm_calls_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_calls")),
    )
    op.create_index(op.f("ix_llm_calls_org_id"), "llm_calls", ["org_id"], unique=False)
    op.create_table(
        "rubric_criteria",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "type",
            sa.Enum("skill", "experience", "education", "other", name="criterion_type"),
            nullable=False,
        ),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("is_knockout", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "weight BETWEEN 0 AND 100", name=op.f("ck_rubric_criteria_weight_range")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_rubric_criteria_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rubric_criteria")),
    )
    op.create_index(op.f("ix_rubric_criteria_job_id"), "rubric_criteria", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rubric_criteria_job_id"), table_name="rubric_criteria")
    op.drop_table("rubric_criteria")
    op.drop_index(op.f("ix_llm_calls_org_id"), table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_index("ix_jobs_org_id_created_at_id", table_name="jobs")
    op.drop_index(op.f("ix_jobs_org_id"), table_name="jobs")
    op.drop_table("jobs")
    # Autogenerate creates enum types implicitly but never drops them.
    for enum_name in ("criterion_type", "llm_purpose", "job_status", "employment_type"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
