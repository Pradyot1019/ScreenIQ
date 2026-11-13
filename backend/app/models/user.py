"""A person who can log in. Users are global; org access comes from memberships."""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAt, UUIDPk


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUIDPk]
    # CITEXT = case-insensitive text, so "Prem@x.com" and "prem@x.com" are the
    # same account and the UNIQUE constraint enforces that in the database.
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    email_verified: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[CreatedAt]
