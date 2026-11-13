"""Candidates, their resume files, applications to jobs, and upload batches (FR-20 to FR-25)."""

import enum
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAt, TenantMixin, UUIDPk, pg_enum


class ParseStatus(enum.StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class ApplicationSource(enum.StrEnum):
    UPLOAD = "upload"
    PUBLIC_LINK = "public_link"


class Stage(enum.StrEnum):
    APPLIED = "applied"
    SCREENED = "screened"
    SHORTLISTED = "shortlisted"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"


class BatchStatus(enum.StrEnum):
    PROCESSING = "processing"
    DONE = "done"


class Candidate(TenantMixin, Base):
    __tablename__ = "candidates"
    # One candidate per email per org (FR-24). NULL emails don't collide in Postgres.
    __table_args__ = (UniqueConstraint("org_id", "email"),)

    id: Mapped[UUIDPk]
    full_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(CITEXT)
    phone: Mapped[str | None] = mapped_column(String(50))
    links: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    parsed: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    total_experience_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    created_at: Mapped[CreatedAt]


class Batch(TenantMixin, Base):
    __tablename__ = "batches"

    id: Mapped[UUIDPk]
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    total: Mapped[int] = mapped_column(Integer)
    processed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[BatchStatus] = mapped_column(
        pg_enum(BatchStatus, "batch_status"), default=BatchStatus.PROCESSING
    )
    created_at: Mapped[CreatedAt]


class Resume(TenantMixin, Base):
    __tablename__ = "resumes"

    id: Mapped[UUIDPk]
    # Unknown until parsed (the email inside the file decides which candidate it is).
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    # Additions to the spec: which upload batch this file came in, and its original name,
    # for per-file progress (FR-25).
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("batches.id", ondelete="SET NULL"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(String(300))  # None if rejected at upload
    file_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256, for dedupe
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    raw_text: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[ParseStatus] = mapped_column(
        pg_enum(ParseStatus, "parse_status"), default=ParseStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text)  # human-readable reason when failed
    created_at: Mapped[CreatedAt]


class Application(TenantMixin, Base):
    """A candidate applying to one job. The unit that gets screened and moved through stages."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("job_id", "candidate_id"),)

    id: Mapped[UUIDPk]
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    source: Mapped[ApplicationSource] = mapped_column(
        pg_enum(ApplicationSource, "application_source"), default=ApplicationSource.UPLOAD
    )
    # use_alter: applications <-> screenings reference each other, so this FK is
    # added after both tables exist.
    latest_screening_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("screenings.id", ondelete="SET NULL", use_alter=True)
    )
    stage: Mapped[Stage] = mapped_column(
        pg_enum(Stage, "application_stage"),
        default=Stage.APPLIED,
        server_default=Stage.APPLIED.value,
    )
    created_at: Mapped[CreatedAt]
