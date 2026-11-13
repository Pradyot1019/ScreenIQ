"""Organizations (tenants) and memberships (which user has which role in which org)."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAt, TenantMixin, UUIDPk


class Plan(enum.StrEnum):
    FREE = "free"
    PRO = "pro"


class Role(enum.StrEnum):
    OWNER = "owner"
    RECRUITER = "recruiter"
    VIEWER = "viewer"


def _pg_enum(cls: type[enum.StrEnum], name: str) -> Enum:
    # Store the lowercase *values* ("owner"), not the Python names ("OWNER").
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUIDPk]
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    plan: Mapped[Plan] = mapped_column(
        _pg_enum(Plan, "plan"), default=Plan.FREE, server_default=Plan.FREE.value
    )
    blind_mode_default: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[CreatedAt]


class Membership(TenantMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id"),)

    id: Mapped[UUIDPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[Role] = mapped_column(_pg_enum(Role, "membership_role"))
    created_at: Mapped[CreatedAt]
