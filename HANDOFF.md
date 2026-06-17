# HANDOFF — wealth-aissistent

**Date**: 2026-06-17 | **Feature**: `001-portfolio-analytics` | **Branch**: `main`

## Current state

**All 59 spec tasks (T001–T059) are complete.** 135 tests passing (7 skipped — Plaid tests auto-skip when `AGGREGATION_PROVIDER=fake`), coverage 86% (gate 80%).
All 3 P0 correctness items are done. All P1 and P2 items are now done except dogfood (P1 #7) and re-enabling the snapshot job (P1 #8).

### Spec-Kit pipeline + implementation (complete)

| Phase | Tasks | Status |
|-------|-------|--------|
| Constitution / specify / clarify / plan / tasks | spec artifacts | ✅ |
| Phase 1 Setup | T001–T006 | ✅ |
| Phase 2 Foundational (domain, persistence, auth, aggregation, privacy, scheduler) | T007–T029 | ✅ |
| Phase 3 US1 — link + consolidated portfolio (MVP) | T030–T038 | ✅ |
| Phase 4 US2 — allocation + performance | T039–T047 | ✅ |
| Phase 5 US3 — risk + diversification | T048–T053 | ✅ |
| Phase 6 Polish (MCP contract tests, perf pass, coverage gate, doc sync) | T054–T059 | ✅ |

### Council verdict (2026-06-13)

Four-voice review (Architect / Skeptic / Pragmatist / Critic), unanimous on the essentials:

- **Solid kernel**: clean `ui → api → services → {analytics, persistence, aggregation}` layering;
  pure-`Decimal` analytics tested against hand-computed values; contract-first surfaces.
- **Critical defect found**: the snapshot pipeline wrote placeholder values
  (`price_amount=0`, `fx_rate=1`) and `net_external_flow` is hardwired to `0` — so period
  returns count deposits as gains. Historical snapshots built from placeholders are unrecoverable.
- **Premise check**: "scalable" is a phantom requirement for a single-user app — pagination,
  rate-limiting-at-scale, p95 tuning all deferred until a second user exists.
- **Coverage caution**: the 80% average previously masked 0% modules on the production path
  (snapshot service, scheduler, MCP server, Plaid adapter). Watch per-module coverage, not the total.

### P0 work completed (2026-06-13)

| Item | What was done | Files |
|------|--------------|-------|
| Disable snapshot job | New `snapshot_job_enabled` setting (default **False**); `register_jobs()` early-returns with a logged warning until the pipeline is validated. Env: `SNAPSHOT_JOB_ENABLED=true` to enable. | `config.py`, `scheduler/app.py` |
| Fix snapshot placeholders | `ConsolidatedHolding` now retains `price_amount`/`price_currency`/`fx_rate` used at valuation; `SnapshotService` freezes those real inputs into `SnapshotHolding` (no migration needed — columns existed). Invariant tested: `value == quantity × price × fx` on every row. | `analytics/consolidation.py`, `services/snapshot_service.py`, `tests/integration/test_snapshot_service.py` (9 tests, TDD red→green) |
| Net external flows ledger | New `CashFlow` model + `cash_flows` table (signed NUMERIC amount in reporting currency, `occurred_on` date, CASCADE delete). `CashFlowRepository.net_between()` sums flows for any date window. `SnapshotRepository.get_latest_before()` finds the prior snapshot. `SnapshotService` now queries flows between snapshots and writes the real `net_external_flow_amount` (no longer hardwired to 0). Migration `002_cash_flows.py`. 13 new tests, TDD red→green. | `persistence/models.py`, `persistence/repositories.py`, `services/snapshot_service.py`, `migrations/versions/002_cash_flows.py`, `tests/integration/test_cash_flows.py` |

### P1/P2 work completed (2026-06-13)

| Item | What was done | Files |
|------|--------------|-------|
| Docker stack (P2 #9) | `Dockerfile` (Python 3.14 + uv, multi-stage), `docker-compose.yml` (`db` Postgres 16 + `app` + one-shot `migrate`/`test` services), `.dockerignore`, `.env.example`, `scripts/initdb/01-create-test-db.sql` (creates `wealth_test`). | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `scripts/initdb/` |
| Suite on real Postgres (P1 #5) | `conftest.py` honors `TEST_DATABASE_URL` (default still in-memory SQLite). **All tests pass against Postgres 16** via `docker compose run --rm test`. | `tests/conftest.py` |
| Postgres-only migration bug fixed | Migration 001 created enum types twice → `DuplicateObject` on Postgres. Columns now use `postgresql.ENUM(name=..., create_type=False)`. | `migrations/versions/001_initial_tables.py` |

### P1/P2 work completed (2026-06-17)

| Item | What was done | Files |
|------|--------------|-------|
| Security hardening (P2 #11) | Enforce 32-byte JWT secret; `_ALLOW_MISSING_ENCRYPTION_KEY` gate; rate-limit auth endpoints. | `config.py`, auth routes |
| MCP contract validation (P1 #6) | All 27 contract tests pass. Confirmed 4 tools exposed (`get_portfolio`, `get_allocation`, `get_performance`, `get_risk`) match spec exactly. Fixed: `insufficient_history` was emitted by `get_risk` but missing from the OpenAPI `Risk` component schema. **Note**: MCP server cannot cold-boot without Postgres + `JWT_SECRET` (module-level engine init in `db.py`). Live `tools/list` call requires `docker compose up app`. | `specs/001-portfolio-analytics/contracts/openapi.yaml` |
| Plaid sandbox end-to-end (P1 #4) | First real execution of `plaid_adapter.py` against live Plaid sandbox API. All 5 methods exercised: `create_link_token`, `exchange_public_token`, `fetch_accounts` (12 accounts returned), `fetch_holdings` (13 holdings returned), error path. 7 integration tests written (TDD), auto-skip when `AGGREGATION_PROVIDER != plaid`. | `tests/integration/test_plaid_adapter.py` |
| GitHub repo + CI (P2 #10) | Repo created at `github.com/Canosson/wealth-aissistant`. `.github/workflows/ci.yml`: Postgres 16 service, uv, Alembic migrations, ruff, pytest with 80% overall gate, per-module coverage floors (`snapshot_service ≥75%`, `scheduler/app ≥60%`); `mcp/server`, `scheduler/jobs`, `plaid_adapter` tracked without hard floor until live tests land. | `.github/workflows/ci.yml` |

## ⚠️ Inputs needed from you

| # | What's needed | Why / blocks |
|---|---------------|--------------|
| C | *(P2/P3 — not yet)* **Deployment target decision** | Needed only when going past local: host (Fly/Railway/Render/VPS), domain, secrets store. No action now. |

All other blockers from the previous HANDOFF (Plaid creds, GitHub repo) are resolved.

## What's next — backlog (priority order)

### P1 — Reality check

7. **Dogfood**: one real human (you), two weeks, using the fake or Plaid sandbox provider. Boot with `docker compose up app`, register, link accounts, watch the portfolio endpoint respond.
8. **Re-enable the snapshot job** (`SNAPSHOT_JOB_ENABLED=true` in `.env`) once dogfood validates the pipeline. First snapshot will freeze real prices and FX. Verify `value == qty × price × fx` on every `SnapshotHolding` row after it runs.

### P2 — Ops floor (before any public URL)

- Add `PLAID_CLIENT_ID` + `PLAID_SECRET` to GitHub repo secrets if you want the 7 Plaid tests to run in CI (they currently skip).
- Raise per-module coverage floors in `ci.yml` as tests improve: `mcp/server` (currently 0%), `scheduler/jobs` (currently 55%), `plaid_adapter` (0% in normal suite).

### P3 — Deferred until a second user exists

Token refresh/revocation, pagination, endpoint p95 measurement, TWR/IRR returns, benchmarks,
daily snapshot cadence.

## Key decisions to carry forward

| Decision | Detail |
|----------|--------|
| Money type | `Money(amount: Decimal, currency: str)` — never float; `NUMERIC(20,4)` in DB |
| Snapshots | Weekly, Tuesdays via APScheduler; forward-only; **job disabled by default** (`snapshot_job_enabled`) until pipeline validated |
| Snapshot reproducibility | `SnapshotHolding` freezes real `price_amount`, `price_currency`, `fx_rate`; invariant `value == qty × price × fx` |
| Volatility | Annualized with √52 (weekly returns); `volatility_min_weeks` config (default 30) |
| Privacy | `GET /me/export` + `DELETE /me` with cascading `ON DELETE CASCADE` |
| Aggregation | Port pattern — `fake` adapter for tests (deterministic, offline); `plaid` sandbox for dev |
| Auth | Argon2id passwords + signed JWTs (`HS256`, 8 h expiry) |
| Encryption | AES-256 key via `ENCRYPTION_KEY` env var for PII + provider access tokens |
| Concentration flag | ≥20% weight (configurable via `CONCENTRATION_THRESHOLD_PCT`) |
| MCP field names | Tool outputs match OpenAPI components exactly: `concentration`, `annualized_volatility_pct`, nested `diversification`, Money objects |
| Cash flows | `CashFlow` table — signed `amount NUMERIC(20,4)` in investor's reporting currency (+ = deposit, − = withdrawal), `occurred_on DATE`. `SnapshotService` sums flows between prior snapshot and today via `CashFlowRepository.net_between()`. Migration: `002_cash_flows.py`. |
| MCP server boot | Requires `JWT_SECRET` + running Postgres (module-level engine init in `db.py`). Use `docker compose up app` for local boot. |

## How to verify current state

### Host-side (fast, in-memory SQLite — default dev loop)

```bash
uv run pytest                                                 # 135 passed, 7 skipped
uv run pytest --cov=wealth_assistant                         # 86% (gate 80%)
uv run pytest tests/contract/ -v                             # 27 passed — MCP + REST contracts
uv run pytest tests/integration/test_snapshot_service.py -v  # 9 passed — P0 placeholder fix
uv run pytest tests/integration/test_cash_flows.py -v        # 13 passed — P0 flows ledger
uv run ruff check src/ tests/
```

### Plaid sandbox (requires credentials in .env)

```bash
AGGREGATION_PROVIDER=plaid uv run pytest tests/integration/test_plaid_adapter.py -v  # 7 passed
```

### Real Postgres (via docker-compose)

```bash
colima start                                          # one-time per boot
docker compose run --rm --build migrate               # alembic upgrade head → rev 002
docker compose run --rm --build test                  # 135 passed against Postgres 16
docker compose up app                                 # API on :8000
```

Notes: `docker compose down` keeps the `pgdata` volume; `down -v` wipes it.

### CI

```
github.com/Canosson/wealth-aissistant/actions         # triggers on every push/PR to main
```

## Cost context

Planning pipeline (Opus 4.8): ~$81 · Implementation phases 1–6 (Sonnet 4.6): ~$21+ ·
Council review + P0 fixes (Sonnet 4.6): ~$9 · Docker/Postgres setup + migration fix (Opus 4.8):
~$6 · Security + MCP + Plaid + CI (Sonnet 4.6): ~$4. Continue on Sonnet 4.6 for P1–P2 work; reserve Opus for design/debugging.

## Spec artifacts index

```
specs/001-portfolio-analytics/
├── spec.md                    # 19 FRs, 3 user stories, 9 SCs
├── plan.md                    # tech stack, phasing, agent ownership plan
├── research.md                # 9 decisions — R5/R6 updated to weekly √52
├── data-model.md              # 9 entities + cross-cutting notes (cascade, crypto, cadence)
├── quickstart.md              # run guide + validation scenarios
├── tasks.md                   # 59/59 tasks ✅
├── checklists/requirements.md # 16/16 ✅
└── contracts/
    ├── openapi.yaml           # REST contract incl. /me/export + DELETE /me; Risk schema updated
    └── internal-contracts.md  # MCP tool schemas + AggregationProvider port
migrations/versions/
├── 001_initial_tables.py      # all 9 original entities — enum cols use create_type=False (Postgres fix)
└── 002_cash_flows.py          # cash_flows table (P0 flows ledger)
.github/workflows/ci.yml         # CI: Postgres 16 + ruff + pytest + per-module coverage floors
.specify/memory/constitution.md  # 6 principles — read before implementing
HANDOFF.md                       # this file
```
