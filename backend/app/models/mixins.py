"""Column helpers shared by models.

- `UUIDPk`: random UUID primary keys. Unlike 1, 2, 3… they can't be guessed or
  enumerated, and they leak nothing about how many rows another tenant has.
- `CreatedAt`: set by Postgres (server clock, UTC), not by the app.
- `TenantMixin`: the `org_id` column every tenant-owned table carries. The
  TenantRepository (Step 2) relies on it to filter every query by org.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

UUIDPk = Annotated[
    uuid.UUID,
    mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")),
]
CreatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False),
]


class TenantMixin:
    if TYPE_CHECKING:  # every tenant model defines its own `id`; this tells mypy so
        id: Mapped[uuid.UUID]

    @declared_attr
    def org_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805 - SQLAlchemy passes the class
        return mapped_column(
            ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
        )
