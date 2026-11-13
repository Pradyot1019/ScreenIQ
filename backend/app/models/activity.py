"""Notes and stage history on applications (FR-41, FR-42).

Both use clock_timestamp() rather than now(): now() is the *transaction* start time, so
several events written in one transaction would tie and their order would be lost.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.candidate import Stage
from app.models.mixins import TenantMixin, UUIDPk, pg_enum


class Note(TenantMixin, Base):
    __tablename__ = "notes"

    id: Mapped[UUIDPk]
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class StageEvent(TenantMixin, Base):
    """Append-only: who moved which candidate from where to where, and when."""

    __tablename__ = "stage_events"

    id: Mapped[UUIDPk]
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    from_stage: Mapped[Stage] = mapped_column(pg_enum(Stage, "application_stage", existing=True))
    to_stage: Mapped[Stage] = mapped_column(pg_enum(Stage, "application_stage", existing=True))
    # NULL actor = the system (the AI's applied -> screened move); otherwise a person.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
