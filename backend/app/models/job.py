"""Jobs and their scoring rubric (spec FR-10 to FR-13)."""

import enum
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAt, TenantMixin, UUIDPk, pg_enum


class JobStatus(enum.StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class EmploymentType(enum.StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class CriterionType(enum.StrEnum):
    SKILL = "skill"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    OTHER = "other"


class Job(TenantMixin, Base):
    __tablename__ = "jobs"
    # Serves "this org's jobs, newest first, after cursor X" with one index range scan.
    __table_args__ = (Index("ix_jobs_org_id_created_at_id", "org_id", "created_at", "id"),)

    id: Mapped[UUIDPk]
    title: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(120))
    employment_type: Mapped[EmploymentType] = mapped_column(
        pg_enum(EmploymentType, "employment_type")
    )
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"),
        default=JobStatus.DRAFT,
        server_default=JobStatus.DRAFT.value,
    )
    # Globally unique (not per org) because it appears in the public URL /apply/{slug}.
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    blind_mode: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[CreatedAt]

    criteria: Mapped[list["RubricCriterion"]] = relationship(
        back_populates="job",
        order_by="RubricCriterion.position",
        cascade="all, delete-orphan",
        lazy="selectin",  # always loaded with the job; async code can't lazy-load later
    )


class RubricCriterion(Base):
    """One line of a job's rubric. Not tenant-scoped itself: it's only ever reached
    through its Job, and the Job query is the one filtered by org_id."""

    __tablename__ = "rubric_criteria"
    __table_args__ = (CheckConstraint("weight BETWEEN 0 AND 100", name="weight_range"),)

    id: Mapped[UUIDPk]
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    type: Mapped[CriterionType] = mapped_column(pg_enum(CriterionType, "criterion_type"))
    weight: Mapped[int] = mapped_column(Integer)
    is_knockout: Mapped[bool] = mapped_column(default=False, server_default="false")
    position: Mapped[int] = mapped_column(Integer)

    job: Mapped[Job] = relationship(back_populates="criteria")
