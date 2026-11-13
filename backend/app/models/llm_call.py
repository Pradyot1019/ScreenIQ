"""One row per LLM API call: what it cost, how long it took, which prompt version.

This is the project's LLM observability (spec FR-36, NFR "Observability" and "Cost").
Failed calls are logged too: a timeout still costs time, and often tokens.
"""

import enum
from decimal import Decimal

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAt, TenantMixin, UUIDPk, pg_enum


class LLMPurpose(enum.StrEnum):
    JD_PARSE = "jd_parse"
    RESUME_PARSE = "resume_parse"
    SCREEN = "screen"
    CHAT = "chat"
    QUESTIONS = "questions"


class LLMCall(TenantMixin, Base):
    __tablename__ = "llm_calls"

    id: Mapped[UUIDPk]
    purpose: Mapped[LLMPurpose] = mapped_column(pg_enum(LLMPurpose, "llm_purpose"))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40))  # e.g. "jd_parse_v1"
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0))
    latency_ms: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool]
    # Short machine-readable reason on failure ("timeout", "invalid_output", ...).
    # Never the prompt or the response text: those can contain PII.
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]
