"""AI screenings (FR-30 to FR-36). One application can have many screenings over time
(re-screens); applications.latest_screening_id points at the current one."""

import enum
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAt, TenantMixin, UUIDPk, pg_enum


class ScreeningStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Recommendation(enum.StrEnum):
    STRONG = "strong"
    POSSIBLE = "possible"
    WEAK = "weak"


class Screening(TenantMixin, Base):
    __tablename__ = "screenings"

    id: Mapped[UUIDPk]
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ScreeningStatus] = mapped_column(
        pg_enum(ScreeningStatus, "screening_status"), default=ScreeningStatus.QUEUED
    )
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # 0-100
    recommendation: Mapped[Recommendation | None] = mapped_column(
        pg_enum(Recommendation, "recommendation")
    )
    knockout_failed: Mapped[bool | None] = mapped_column(Boolean)
    summary: Mapped[str | None] = mapped_column(Text)  # the model's one-line take
    strengths: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    gaps: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]

    criterion_scores: Mapped[list["CriterionScore"]] = relationship(
        order_by="CriterionScore.position", cascade="all, delete-orphan", lazy="selectin"
    )


class CriterionScore(Base):
    """One criterion's result. Name/weight/knockout are copied from the rubric at screening
    time, so editing the rubric later never rewrites the history of past screenings."""

    __tablename__ = "criterion_scores"

    id: Mapped[UUIDPk]
    screening_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screenings.id", ondelete="CASCADE"), index=True
    )
    criterion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rubric_criteria.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(Integer)
    criterion_name: Mapped[str] = mapped_column(String(120))
    weight: Mapped[int] = mapped_column(Integer)
    is_knockout: Mapped[bool]
    score: Mapped[int] = mapped_column(Integer)  # 0-10, after evidence checks
    reasoning: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list[str]] = mapped_column(JSONB, default=list)  # verified quotes only
    rejected_evidence: Mapped[list[str]] = mapped_column(JSONB, default=list)  # failed check
    low_confidence: Mapped[bool] = mapped_column(default=False)
