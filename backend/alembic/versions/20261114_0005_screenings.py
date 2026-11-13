"""Screenings + criterion_scores; applications.latest_screening_id (Phase 4).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-14 02:00:16.770107
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screenings",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "done", "failed", name="screening_status"),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "recommendation",
            sa.Enum("strong", "possible", "weak", name="recommendation"),
            nullable=True,
        ),
        sa.Column("knockout_failed", sa.Boolean(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "strengths",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "gaps", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_screenings_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_screenings_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screenings")),
    )
    op.create_index(
        op.f("ix_screenings_application_id"), "screenings", ["application_id"], unique=False
    )
    op.create_index(op.f("ix_screenings_org_id"), "screenings", ["org_id"], unique=False)
    op.create_table(
        "criterion_scores",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("screening_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("criterion_name", sa.String(length=120), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("is_knockout", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rejected_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("low_confidence", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["criterion_id"],
            ["rubric_criteria.id"],
            name=op.f("fk_criterion_scores_criterion_id_rubric_criteria"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["screening_id"],
            ["screenings.id"],
            name=op.f("fk_criterion_scores_screening_id_screenings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_criterion_scores")),
    )
    op.create_index(
        op.f("ix_criterion_scores_screening_id"), "criterion_scores", ["screening_id"], unique=False
    )
    op.add_column("applications", sa.Column("latest_screening_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_applications_latest_screening_id_screenings"),
        "applications",
        "screenings",
        ["latest_screening_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_applications_latest_screening_id_screenings"), "applications", type_="foreignkey"
    )
    op.drop_column("applications", "latest_screening_id")
    op.drop_index(op.f("ix_criterion_scores_screening_id"), table_name="criterion_scores")
    op.drop_table("criterion_scores")
    op.drop_index(op.f("ix_screenings_org_id"), table_name="screenings")
    op.drop_index(op.f("ix_screenings_application_id"), table_name="screenings")
    op.drop_table("screenings")
    # Autogenerate creates enum types implicitly but never drops them.
    for enum_name in ("recommendation", "screening_status"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
