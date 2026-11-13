"""Candidates, resumes, applications, batches (Phase 3).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14 01:41:19.845184
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column(
            "links", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column(
            "parsed", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("total_experience_years", sa.Numeric(precision=4, scale=1), nullable=True),
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
            name=op.f("fk_candidates_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
        sa.UniqueConstraint("org_id", "email", name=op.f("uq_candidates_org_id_email")),
    )
    op.create_index(op.f("ix_candidates_org_id"), "candidates", ["org_id"], unique=False)
    op.create_table(
        "batches",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.Enum("processing", "done", name="batch_status"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_batches_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_batches_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batches")),
    )
    op.create_index(op.f("ix_batches_job_id"), "batches", ["job_id"], unique=False)
    op.create_index(op.f("ix_batches_org_id"), "batches", ["org_id"], unique=False)
    op.create_table(
        "resumes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=300), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "parse_status",
            sa.Enum("queued", "parsing", "parsed", "failed", name="parse_status"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["batches.id"],
            name=op.f("fk_resumes_batch_id_batches"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_resumes_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_resumes_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resumes")),
    )
    op.create_index(op.f("ix_resumes_batch_id"), "resumes", ["batch_id"], unique=False)
    op.create_index(op.f("ix_resumes_candidate_id"), "resumes", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_resumes_file_hash"), "resumes", ["file_hash"], unique=False)
    op.create_index(op.f("ix_resumes_org_id"), "resumes", ["org_id"], unique=False)
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source", sa.Enum("upload", "public_link", name="application_source"), nullable=False
        ),
        sa.Column(
            "stage",
            sa.Enum(
                "applied",
                "screened",
                "shortlisted",
                "interview",
                "offer",
                "hired",
                "rejected",
                name="application_stage",
            ),
            server_default="applied",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_applications_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_applications_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_applications_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes.id"],
            name=op.f("fk_applications_resume_id_resumes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
        sa.UniqueConstraint(
            "job_id", "candidate_id", name=op.f("uq_applications_job_id_candidate_id")
        ),
    )
    op.create_index(
        op.f("ix_applications_candidate_id"), "applications", ["candidate_id"], unique=False
    )
    op.create_index(op.f("ix_applications_job_id"), "applications", ["job_id"], unique=False)
    op.create_index(op.f("ix_applications_org_id"), "applications", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_applications_org_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_job_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_candidate_id"), table_name="applications")
    op.drop_table("applications")
    op.drop_index(op.f("ix_resumes_org_id"), table_name="resumes")
    op.drop_index(op.f("ix_resumes_file_hash"), table_name="resumes")
    op.drop_index(op.f("ix_resumes_candidate_id"), table_name="resumes")
    op.drop_index(op.f("ix_resumes_batch_id"), table_name="resumes")
    op.drop_table("resumes")
    op.drop_index(op.f("ix_batches_org_id"), table_name="batches")
    op.drop_index(op.f("ix_batches_job_id"), table_name="batches")
    op.drop_table("batches")
    op.drop_index(op.f("ix_candidates_org_id"), table_name="candidates")
    op.drop_table("candidates")
    # Autogenerate creates enum types implicitly but never drops them.
    for enum_name in (
        "application_stage",
        "application_source",
        "parse_status",
        "batch_status",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
