"""Token prices, used to record cost_usd on every LLM call.

Prices are USD per 1 million tokens: (input, output), at PAID-tier rates. On Google's
free tier the real charge is $0, but we still record what the call *would* cost, so
the cost dashboard (Phase 9) shows true unit economics before anyone pays.

Provider prices change; check https://aistudio.google.com/docs/pricing and update this
table (and the date). Last reviewed: 2026-11-14. Unknown models are recorded at cost 0
with a warning, so a new model never breaks a request, but you'll see it in the logs.
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

PRICES_PER_MTOK: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-3.5-flash-lite": (Decimal("0.30"), Decimal("2.50")),  # default (ADR 0003)
    "gemini-3.1-flash-lite": (Decimal("0.25"), Decimal("1.50")),
    # 3.8 Flash doubles to $1.50 / $7.50 on 2027-01-01; update this row then.
    "gemini-3.8-flash": (Decimal("0.75"), Decimal("3.75")),
    "gemini-2.5-flash-lite": (Decimal("0.10"), Decimal("0.40")),
    "gemini-2.5-flash": (Decimal("0.30"), Decimal("2.50")),  # retired for new keys
}

_MILLION = Decimal(1_000_000)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    # Longest prefix wins, so "gemini-2.5-flash-lite-001" matches flash-lite, not flash.
    matches = [m for m in PRICES_PER_MTOK if model.startswith(m)]
    if not matches:
        logger.warning("llm_price_unknown", extra={"extra_fields": {"model": model}})
        return Decimal(0)
    price_in, price_out = PRICES_PER_MTOK[max(matches, key=len)]
    total = (input_tokens * price_in + output_tokens * price_out) / _MILLION
    return total.quantize(Decimal("0.000001"))
