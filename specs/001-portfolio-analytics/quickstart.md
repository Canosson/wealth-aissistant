# Quickstart & Validation: Portfolio Tracking & Analytics

**Feature**: `001-portfolio-analytics` | **Date**: 2026-06-12

A run/validation guide proving the feature works end-to-end. Implementation details live in `tasks.md`
and the code; this file only shows how to set up, run, and verify. See `data-model.md` and
`contracts/` for schemas.

## Prerequisites

- Python 3.14 + `uv`
- PostgreSQL reachable (local instance or container)
- (Optional) Plaid **sandbox** credentials. Without them, use the **fake** aggregation provider —
  everything below works fully offline against the fake.

## Environment

Set these (e.g., in `.env`; never commit secrets):

```text
DATABASE_URL=postgresql+psycopg://localhost:5432/wealth
AGGREGATION_PROVIDER=fake          # "fake" (default for dev/test) or "plaid"
JWT_SECRET=<random-long-string>
# Only when AGGREGATION_PROVIDER=plaid:
PLAID_CLIENT_ID=...
PLAID_SECRET=...
PLAID_ENV=sandbox
```

## Setup

```bash
uv sync                              # resolve deps (R9 gate: must succeed on Python 3.14)
uv run python -c "import fastapi, sqlalchemy, pandas, numpy, streamlit, mcp"   # import smoke test
uv run alembic upgrade head          # apply migrations
```

## Run

```bash
# Backend API (Backend Architect)
uv run uvicorn wealth_assistant.api.app:app --reload --port 8000

# MCP server (MCP Engineer) — read-only portfolio tools
uv run python -m wealth_assistant.mcp.server

# Streamlit UI (Streamlit Engineer)
uv run streamlit run src/wealth_assistant/ui/app.py
```

## Tests (QA Engineer — written first, must pass)

```bash
uv run pytest                        # all
uv run pytest tests/unit             # analytics & Money/FX vs known-correct values
uv run pytest tests/contract         # API/MCP outputs vs openapi.yaml
uv run pytest tests/integration      # full flows over the fake provider
uv run pytest --cov=wealth_assistant --cov-report=term-missing
```

## Validation scenarios (map to spec acceptance criteria)

Run against `AGGREGATION_PROVIDER=fake` (seeded with two accounts, overlapping holdings, multi-currency).

### US1 — Link & consolidate (P1, MVP)
1. Register + log in (`POST /auth/register`, `POST /auth/login`) → receive token.
2. Link first account (`POST /connections/link-token` → `POST /connections`).
3. `GET /portfolio` → total value equals the fake's expected total **to the cent** (SC-002); holdings
   listed with quantity + value.
4. Link the second account → the security held in both accounts appears **once**, consolidated, with a
   per-account breakdown (FR-004); total = sum of both accounts.
5. `POST /connections/{id}/refresh` → `last_updated` advances.
6. `DELETE /connections/{id}` → its holdings disappear; total recalculates.
   - Negative: simulate provider outage on refresh → `409`, portfolio `stale=true`, last-known values
     retained (FR-012, SC-008).

### US2 — Allocation & performance (P2)
1. `GET /portfolio/allocation?by=asset_class` → slice `weight_pct` values **sum to 100** (SC-004); a
   holding with `sector=null` appears under "Unclassified".
2. With ≥2 daily snapshots present, `GET /portfolio/performance?period=1M` → `return_pct` and
   `gain_loss` match an independent hand calculation for the same window (SC-005).

### US3 — Risk & insights (P3)
1. `GET /portfolio/risk` → a holding above the 20% threshold is `flagged`; `hhi` present.
2. With ≥30 daily snapshots, `annualized_volatility_pct` is populated; otherwise it is `null` with an
   "insufficient history" indication; `diversification.summary` reads in plain language.

### MCP parity
- Call `get_portfolio`, `get_allocation`, `get_performance`, `get_risk` → outputs validate against the
  same OpenAPI component schemas as the REST responses.

## Definition of Done (per constitution)

Tests written-first and green · coverage gate met · contracts honored (REST + MCP + provider port) ·
money exact with currency · structured logs with correlation IDs · no silently incorrect totals.
