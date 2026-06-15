# Research: Portfolio Tracking & Analytics

**Feature**: `001-portfolio-analytics` | **Date**: 2026-06-12

Consolidated decisions resolving the "Open items" from `plan.md`. Each item: Decision / Rationale /
Alternatives considered.

## R1. Account aggregation provider

- **Decision**: Abstract aggregation behind an internal **Aggregation Provider port**
  (`src/wealth_assistant/aggregation/port.py`) with two adapters: **Plaid** (sandbox for dev/test,
  Investments product for holdings) and an **in-memory fake** for deterministic tests.
- **Rationale**: Plaid is the most widely supported retail brokerage/bank aggregator with an
  Investments/holdings product and a free sandbox. The port keeps Plaid out of the service/analytics
  layers (Principle I/II) and lets every test run against the fake — no network, fully deterministic
  (Principle V/VI). Switching/adding providers later is a new adapter, not a rewrite.
- **Alternatives**: Direct Plaid SDK calls in services (rejected — couples business logic to a vendor,
  breaks testability); MX or Yodlee (viable alternates, kept possible via the port); file-import-only
  (rejected — user explicitly chose connected accounts).

## R2. Money & quantity representation

- **Decision**: A `Money` value object wrapping `decimal.Decimal` + an ISO-4217 `Currency`; quantities
  as `Decimal`. Stored in Postgres as `NUMERIC(20, 8)` (quantities) / `NUMERIC(20, 4)` (money). All
  arithmetic on `Money` requires matching currency or raises.
- **Rationale**: Directly satisfies Principle V (exact decimal math, explicit currency, reject mixed
  units). `NUMERIC` preserves exactness end-to-end; binary float is prohibited for currency.
- **Alternatives**: `float`/`double` (rejected — rounding drift); integer minor-units (works but loses
  precision for fractional shares and FX; `Decimal` is simpler and exact); the `py-moneyed` library
  (good, but a tiny in-house value object keeps the shared domain dependency-free and fully owned).

## R3. Currency / FX conversion

- **Decision**: Convert all amounts to the investor's single **reporting currency** using a recorded
  daily FX rate captured at read/snapshot time. FX rates are fetched from the aggregation provider's
  returned currencies where available, else an FX rate source (configurable port), and **persisted
  with the snapshot** so analytics are reproducible.
- **Rationale**: Principle V/VI — every converted value must disclose its basis and be reproducible.
  Persisting the rate with the snapshot makes historical analytics deterministic.
- **Alternatives**: Live per-request FX (rejected — non-reproducible, non-deterministic tests);
  ignoring multi-currency (rejected — spec edge case requires it).

## R4. Performance / return calculation

- **Decision**: MVP uses **simple period return** from daily **PortfolioSnapshot** values:
  `return = (end_value − start_value − net_external_flows) / start_value`, with net external flows
  (deposits/withdrawals) subtracted to avoid counting contributions as gains. Absolute gain/loss =
  `end_value − start_value − net_external_flows`.
- **Rationale**: Deterministic, explainable, and verifiable against a hand calculation (SC-005). Daily
  snapshots are the minimum durable history needed and double as the reproducibility record (R6).
- **Alternatives**: Time-Weighted Return (TWR) and Money-Weighted/IRR (more accurate across flows) —
  **deferred** to a later enhancement; documented as the upgrade path. Computing return live from
  transactions (rejected for MVP — heavier, provider transaction coverage varies).

## R5. Risk & concentration metrics

- **Decision**:
  - **Concentration**: per-holding weight = holding value / portfolio value; flag any holding whose
    weight ≥ **20%** (configurable). Also report a Herfindahl-Hirschman Index (sum of squared weights)
    as an overall concentration score.
  - **Volatility**: annualized standard deviation of **weekly** portfolio returns derived from
    snapshots (`stdev(weekly_returns) × sqrt(52)`), shown only when ≥ 4 weekly snapshots exist;
    otherwise an explicit "insufficient history" state. Uses weekly cadence because the scheduler
    runs every Tuesday (FR-016) — see R6.
  - **Diversification**: count and weight of distinct asset classes / sectors (uses US2 allocation).
- **Rationale**: Standard, well-understood measures that are deterministic from recorded snapshots and
  explainable in plain language (FR-009, US3). Thresholds configurable per Principle VI auditability.
  Weekly cadence was chosen because the snapshot job runs weekly; `sqrt(52)` is the correct
  annualization factor for weekly returns (vs `sqrt(252)` for daily returns).
- **Alternatives**: Beta vs a benchmark, VaR, Sharpe ratio (richer but require benchmark/risk-free
  inputs and more history) — deferred; benchmark comparison already out of scope per spec Assumptions.

## R6. Reproducibility model

- **Decision**: Persist a **weekly PortfolioSnapshot** per investor (scheduled every **Tuesday** by
  APScheduler, FR-016) capturing total value, per-holding values, prices, and FX rates used.
  Analytics read from snapshots, not live provider calls.
- **Rationale**: Principle VI — every analytics result is reproducible from recorded inputs; also gives
  the history US2/US3 need. Snapshots are created on connection refresh and on the weekly schedule.
  The weekly cadence aligns the annualization factor with R5: `σ_weekly × sqrt(52)`.
- **Alternatives**: Daily snapshots (would require `sqrt(252)` for volatility; deferred to a future
  enhancement if finer-grained history is needed). Recompute from live data each time (rejected —
  non-reproducible, no history).

## R7. Authentication

- **Decision**: Email + password (**Argon2id** hashing via `argon2-cffi`); backend issues a signed,
  expiring **session token (JWT)**; every API request and MCP tool call is scoped to the authenticated
  investor. Streamlit holds the token in session state.
- **Rationale**: Standard, supports the spec's per-investor isolation (FR-013) and future multi-user
  growth without rework; no third-party identity dependency for the MVP.
- **Alternatives**: OAuth/social login (heavier, unneeded for MVP); no auth / single-user (rejected —
  financial data isolation is required).

## R8. MCP tool surface

- **Decision**: A read-only MCP server (`src/wealth_assistant/mcp/`) exposing tools that **project the
  existing service-layer read methods**: `get_portfolio`, `get_allocation`, `get_performance`,
  `get_risk`. No business logic lives in the MCP layer; it calls services and scopes to an investor.
- **Rationale**: Engages the MCP Engineer role, sets up the future conversational AI advisor, and maps
  1:1 to delivered US1–US3 reads (no speculative scope; YAGNI-compliant since each tool surfaces an
  already-built service method).
- **Alternatives**: Defer MCP entirely (possible, but the role and AI-assistant positioning justify a
  thin read-only surface now); write-capable tools (rejected — feature is read-only, FR-014).

## R9. Python 3.14 library compatibility (RISK)

- **Decision**: Target Python 3.14 per the constitution. Treat **3.14 wheel availability** for
  FastAPI, SQLAlchemy 2.0, pandas, numpy, Streamlit, `mcp`, `argon2-cffi`, and `psycopg` as a
  **Setup-phase verification gate**: `uv sync` must resolve and the full import smoke test must pass
  before Foundational work begins.
- **Rationale**: 3.14 is recent; native-extension wheels (numpy/pandas/argon2/psycopg) are the main
  risk. Verifying at Setup fails fast (Principle III/IV) rather than mid-build.
- **Alternatives**: Pin to 3.12/3.13 (would contradict the constitution — not chosen; if a hard
  blocker appears, it becomes a constitution amendment decision, not a silent downgrade).

## Summary of resolved unknowns

| Open item (plan.md) | Resolution |
|---------------------|------------|
| Aggregation provider | Provider port + Plaid (sandbox) + fake — R1 |
| Return method | Simple snapshot-based period return; TWR/IRR deferred — R4 |
| Volatility & concentration | Annualized stdev of weekly returns (×√52); ≥20% weight flag + HHI — R5 |
| FX source | Daily rate, persisted with snapshot, via configurable source — R3 |
| Python 3.14 compatibility | Setup-phase verification gate — R9 |

All NEEDS CLARIFICATION items resolved. Ready for Phase 1 design.
