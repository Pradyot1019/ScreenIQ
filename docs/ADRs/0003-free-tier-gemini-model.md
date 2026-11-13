# ADR 0003: Default LLM is gemini-3.5-flash-lite on Google's free tier

**Status:** Accepted (Phase 2, 2026-11-14). Amends spec Section 5 ("Gemini 2.5 Flash").

## Context
The spec planned `gemini-2.5-flash`. A live call returned 404: "no longer available to new
users". Google suggests `gemini-3.8-flash`, which returned 503 (high demand) in testing and
costs $0.75 / $3.75 per 1M tokens, doubling on 2027-01-01. The project needs a free LLM.

Live test of the `jd_parse_v1` prompt on 2026-11-14:

| Model | Result | Latency | Tokens in / out / thinking |
|---|---|---|---|
| gemini-2.5-flash | 404 retired for new users | – | – |
| gemini-3.5-flash | OK, 7 criteria | 7.7 s | 554 / 321 / 728 |
| gemini-3.5-flash-lite | OK, 7 criteria | 2.3 s | 554 / 483 / none |
| gemini-3.8-flash | 503 overloaded | – | – |

## Decision
Default `LLM_MODEL=gemini-3.5-flash-lite`, called through the Gemini API **free tier**
($0). Its paid price ($0.30 / $2.50) equals what the spec budgeted for 2.5 Flash, so cost
tracking still records realistic numbers.

## Consequences
- **Data use:** on the free tier Google may use prompts and responses to improve its
  products (paid tier: no). Prompts contain resumes, so development and evals must use
  synthetic or consented resumes only. Any deployment with real candidates must switch
  the key to the paid tier first.
- **Rate limits:** free-tier per-minute and per-day caps apply (see
  https://aistudio.google.com/rate-limit). Upstream 429/503 are mapped to our own 503
  "busy, try again", and Phase 3 workers will retry with backoff.
- **Switching models** is a one-line `.env` change thanks to the `LLMProvider` interface;
  the cost table in `app/llm/cost.py` lists the alternatives. The Phase 6 eval harness
  is where a switch should be justified with numbers.
