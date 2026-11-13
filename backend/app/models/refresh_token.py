"""Refresh tokens: one row per issued token, so tokens can be revoked and rotated.

We store only a SHA-256 hash of the token. If the database leaks, the hashes
can't be replayed as cookies.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAt, UUIDPk


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUIDPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # The org this login session is acting in. Refreshing keeps the same org,
    # so the new access token carries the same `org` claim. (Addition to the
    # spec's table: without it, a refresh couldn't know which org to resume.)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
