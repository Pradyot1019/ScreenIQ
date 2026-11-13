"""Notes and stage_events (Phase 5). Reuses the application_stage enum type.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-14 02:16:49.042438
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_notes_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name=op.f("fk_notes_author_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_notes_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notes")),
    )
    op.create_index(op.f("ix_notes_application_id"), "notes", ["application_id"], unique=False)
    op.create_index(op.f("ix_notes_org_id"), "notes", ["org_id"], unique=False)
    op.create_table(
        "stage_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column(
            "from_stage",
            postgresql.ENUM(
                "applied",
                "screened",
                "shortlisted",
                "interview",
                "offer",
                "hired",
                "rejected",
                name="application_stage",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "to_stage",
            postgresql.ENUM(
                "applied",
                "screened",
                "shortlisted",
                "interview",
                "offer",
                "hired",
                "rejected",
                name="application_stage",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_stage_events_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_stage_events_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_stage_events_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stage_events")),
    )
    op.create_index(
        op.f("ix_stage_events_application_id"), "stage_events", ["application_id"], unique=False
    )
    op.create_index(op.f("ix_stage_events_org_id"), "stage_events", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stage_events_org_id"), table_name="stage_events")
    op.drop_index(op.f("ix_stage_events_application_id"), table_name="stage_events")
    op.drop_table("stage_events")
    op.drop_index(op.f("ix_notes_org_id"), table_name="notes")
    op.drop_index(op.f("ix_notes_application_id"), table_name="notes")
    op.drop_table("notes")
