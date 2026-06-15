---
description: "Task list for Portfolio Tracking & Analytics"
---

# Tasks: Portfolio Tracking & Analytics

**Input**: Design documents from `/specs/001-portfolio-analytics/`

**Prerequisites**: plan.md, spec.md (required); research.md, data-model.md, contracts/, quickstart.md

**Tests**: MANDATORY for this project — constitution Principle IV (Test-First, NON-NEGOTIABLE). Test
tasks are written and MUST fail before their implementation tasks.

**Organization**: Tasks are grouped by user story (US1 P1 → US2 P2 → US3 P3) for independent delivery.
Each task notes its owning agent role (constitution Principle I).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependencies)
- **[Story]**: US1 / US2 / US3 (omitted for Setup, Foundational, Polish)
- All paths are repo-relative.

## Path Conventions

Source under `src/wealth_assistant/<package>/`; tests under `tests/{unit,integration,contract}/`;
migrations under `migrations/`. Layering: `ui → api → services → {analytics, persistence, aggregation,
scheduler}`; UI never touches DB or financial math.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding and tooling.

- [x] T001 Create package + test structure per plan.md (`src/wealth_assistant/{domain,analytics,persistence,aggregation,scheduler,services,api,mcp,ui}/`, `tests/{unit,integration,contract}/`, `migrations/`)
- [x] T002 Declare dependencies in `pyproject.toml` and run `uv sync` (FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, psycopg, pandas, numpy, Streamlit, mcp, argon2-cffi, PyJWT, httpx, structlog, APScheduler, plaid)
- [x] T003 [P] Verify Python 3.14 compatibility — `uv sync` resolves + import smoke test (research R9) in `tests/test_imports.py`
- [x] T004 [P] Configure ruff + pytest + coverage in `pyproject.toml`
- [x] T005 [P] Implement structlog config + correlation-id middleware in `src/wealth_assistant/observability.py` (Shared)
- [x] T006 [P] Implement env-driven settings in `src/wealth_assistant/config.py` (Shared)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared domain, persistence, auth, aggregation, privacy, scheduler runtime.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

### Shared domain (ratified) — tests first
- [x] T007 [P] Unit tests for Money/Currency (exact decimal; currency-mismatch raises) in `tests/unit/test_money.py`
- [x] T008 [P] Unit tests for FX conversion (recorded rate; reproducible) in `tests/unit/test_fx.py`
- [x] T009 [P] Implement `Money` + `Currency` value objects in `src/wealth_assistant/domain/money.py` (Shared)
- [x] T010 [P] Implement FX conversion + `CurrencyMismatchError` in `src/wealth_assistant/domain/fx.py` (Shared)
- [x] T011 [P] Implement base error model in `src/wealth_assistant/domain/errors.py` (Shared)

### Persistence (Database Engineer)
- [x] T012 Configure SQLAlchemy base/session/unit-of-work + Alembic env in `src/wealth_assistant/persistence/db.py`
- [x] T013 Define ORM models (Investor, LinkedAccountConnection, Account, Security, Holding, Price, FxRate, PortfolioSnapshot, SnapshotHolding) per data-model.md in `src/wealth_assistant/persistence/models.py` — `NUMERIC` money/qty, FK `ON DELETE CASCADE` for erasure
- [x] T014 Create initial Alembic migration (tables, indexes, unique constraints, cascades) in `migrations/versions/`
- [x] T015 [P] Implement repositories (investor, connection, account, holding, price, snapshot) in `src/wealth_assistant/persistence/repositories.py`
- [x] T016 [P] Implement encryption-at-rest for PII + linked-account credentials in `src/wealth_assistant/persistence/crypto.py` (FR-019)

### Auth (Backend Architect)
- [x] T017 [P] Contract test `POST /auth/register`, `POST /auth/login` vs `contracts/openapi.yaml` in `tests/contract/test_auth_contract.py`
- [x] T018 Implement auth service (Argon2id hashing, JWT issue/verify) in `src/wealth_assistant/services/auth_service.py`
- [x] T019 Implement auth routes + session dependency (investor scoping, FR-013) in `src/wealth_assistant/api/routes_auth.py`

### Aggregation (Backend Architect)
- [x] T020 [P] Define `AggregationProvider` port + DTOs per `contracts/internal-contracts.md` in `src/wealth_assistant/aggregation/port.py`
- [x] T021 [P] Implement in-memory fake provider (seeded: 2 accounts, overlapping holdings, multi-currency) in `src/wealth_assistant/aggregation/fake.py`
- [x] T022 [P] Implement Plaid sandbox adapter in `src/wealth_assistant/aggregation/plaid_adapter.py`
- [x] T023 Implement config-driven provider factory (fake|plaid) in `src/wealth_assistant/aggregation/factory.py`

### Privacy / account lifecycle (Backend Architect)
- [x] T024 Add `GET /me/export` + `DELETE /me` to `contracts/openapi.yaml`, then contract test in `tests/contract/test_privacy_contract.py`
- [x] T025 Implement data export + account deletion (cascading erasure) in `src/wealth_assistant/services/account_service.py` (FR-017, FR-018)
- [x] T026 Implement `GET /me/export` + `DELETE /me` routes in `src/wealth_assistant/api/routes_account.py`
- [x] T027 [P] Integration test: account deletion erases all investor data (SC-009) in `tests/integration/test_account_deletion.py`

### App + scheduler runtime
- [x] T028 Implement FastAPI app factory + middleware (structlog/correlation, error handler) in `src/wealth_assistant/api/app.py`
- [x] T029 [P] Implement APScheduler bootstrap/runner in `src/wealth_assistant/scheduler/app.py` (weekly job registered in US2)

**Checkpoint**: Foundation ready — user stories can begin.

---

## Phase 3: User Story 1 — Link accounts & consolidated portfolio (P1) 🎯 MVP

**Goal**: Link external accounts and view a single deduplicated portfolio with correct total.

**Independent Test**: Link 2 fake accounts → consolidated total matches expected to the cent (SC-002);
overlapping security shown once with per-account breakdown; refresh updates `last_updated`; unlink
recalculates.

### Tests first ⚠️ (write, ensure FAIL, then implement)
- [x] T030 [P] [US1] Contract tests for `/connections/*` and `GET /portfolio` vs `contracts/openapi.yaml` in `tests/contract/test_portfolio_contract.py`
- [x] T031 [P] [US1] Unit tests: consolidation/dedup + missing-price handling against known values in `tests/unit/test_consolidation.py`
- [x] T032 [P] [US1] Integration test: link 2 fake accounts → total to the cent, dedup, refresh, unlink, provider-outage staleness (SC-008) in `tests/integration/test_us1_portfolio.py`

### Implementation
- [x] T033 [P] [US1] Implement portfolio consolidation (dedup, valuation via Price+FxRate, price-unavailable exclusion) in `src/wealth_assistant/analytics/consolidation.py` (Quant Analyst)
- [x] T034 [US1] Implement connection service (link-token, exchange, list, unlink, refresh→import holdings/accounts) in `src/wealth_assistant/services/connection_service.py` (Backend Architect)
- [x] T035 [US1] Implement portfolio service (read consolidated portfolio + `last_updated` + `stale`) in `src/wealth_assistant/services/portfolio_service.py` (Backend Architect)
- [x] T036 [US1] Implement connection + portfolio routes in `src/wealth_assistant/api/routes_portfolio.py` (Backend Architect)
- [x] T037 [P] [US1] Implement MCP `get_portfolio` tool in `src/wealth_assistant/mcp/server.py` (MCP Engineer)
- [x] T038 [P] [US1] Implement Streamlit login + link + consolidated portfolio page in `src/wealth_assistant/ui/app.py` (Streamlit Engineer)

**Checkpoint**: US1 fully functional and independently testable (MVP).

---

## Phase 4: User Story 2 — Allocation & performance analytics (P2)

**Goal**: Show allocation breakdowns (sum to 100%) and period return/gain-loss from accrued history.

**Independent Test**: Allocation by asset_class sums to 100% with an "Unclassified" bucket (SC-004);
period return matches a hand calculation (SC-005); periods beyond history show "insufficient history".

### Tests first ⚠️
- [x] T039 [P] [US2] Unit tests: allocation sums to 100% + Unclassified; period return vs hand calc; insufficient-history in `tests/unit/test_allocation_performance.py`
- [x] T040 [P] [US2] Integration test: allocation + performance over accrued snapshots in `tests/integration/test_us2_analytics.py`

### Implementation
- [x] T041 [P] [US2] Implement allocation analytics (asset_class/sector/account, Unclassified, weights→100%) in `src/wealth_assistant/analytics/allocation.py` (Quant Analyst)
- [x] T042 [P] [US2] Implement performance analytics (simple period return + gain/loss from snapshots & net flows; insufficient-history) in `src/wealth_assistant/analytics/performance.py` (Quant Analyst)
- [x] T043 [US2] Implement snapshot service (value portfolio → write PortfolioSnapshot + SnapshotHolding, record prices/FX) in `src/wealth_assistant/services/snapshot_service.py` (Backend Architect)
- [x] T044 [US2] Implement weekly (Tuesday) snapshot job + register with scheduler (FR-016) in `src/wealth_assistant/scheduler/jobs.py` (Backend Architect)
- [x] T045 [US2] Add `GET /portfolio/allocation` + `GET /portfolio/performance` routes in `src/wealth_assistant/api/routes_portfolio.py` (Backend Architect)
- [x] T046 [P] [US2] Implement MCP `get_allocation` + `get_performance` tools in `src/wealth_assistant/mcp/server.py` (MCP Engineer)
- [x] T047 [P] [US2] Streamlit allocation + performance views in `src/wealth_assistant/ui/app.py` (Streamlit Engineer)

**Checkpoint**: US1 + US2 both independently functional.

---

## Phase 5: User Story 3 — Risk & diversification insights (P3)

**Goal**: Show concentration (≥20% flag) + HHI, annualized volatility (weekly history), diversification.

**Independent Test**: A dominant holding is flagged; HHI present; volatility populated with sufficient
weekly history else "insufficient history"; plain-language diversification summary shown.

### Tests first ⚠️
- [x] T048 [P] [US3] Unit tests: concentration ≥20% flag + HHI; annualized volatility (weekly, √52) with ≥N-week threshold; insufficient-history in `tests/unit/test_risk.py`
- [x] T049 [P] [US3] Integration test: risk endpoint flags dominant holding + diversification summary in `tests/integration/test_us3_risk.py`

### Implementation
- [x] T050 [P] [US3] Implement risk analytics (concentration, HHI, annualized weekly volatility, diversification) in `src/wealth_assistant/analytics/risk.py` (Quant Analyst)
- [x] T051 [US3] Add `GET /portfolio/risk` route in `src/wealth_assistant/api/routes_portfolio.py` (Backend Architect)
- [x] T052 [P] [US3] Implement MCP `get_risk` tool in `src/wealth_assistant/mcp/server.py` (MCP Engineer)
- [x] T053 [P] [US3] Streamlit risk/insights view in `src/wealth_assistant/ui/app.py` (Streamlit Engineer)

**Checkpoint**: All user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T054 [P] MCP contract test: all tool outputs validate vs OpenAPI components in `tests/contract/test_mcp_contract.py` (QA Engineer)
- [X] T055 Performance pass: portfolio of ~500 holdings renders < 2 s (SC-007)
- [X] T056 Coverage gate (≥ project threshold) + structured-logging/no-silent-failure audit (QA Engineer)
- [X] T057 [P] Run quickstart.md validation end-to-end against the fake provider
- [X] T058 [P] Sync `data-model.md` (cascade erasure, encryption-at-rest, weekly snapshot cadence) and confirm `contracts/openapi.yaml` export/delete endpoints — close the clarify-step artifact lag
- [X] T059 [P] Update `research.md` R5/R6 for weekly snapshot cadence (annualize volatility with √52)

---

## Dependencies & Execution Order

- **Setup (P1)** → no deps.
- **Foundational (P2)** → depends on Setup; **blocks all user stories**. Within it: domain (T007–T011)
  before persistence (T012–T016) before auth/aggregation/privacy; scheduler runner (T029) standalone.
- **US1 (P3)** → depends on Foundational only. MVP.
- **US2 (P4)** → depends on Foundational; consumes US1 portfolio valuation (T033/T035) for snapshots
  (T043) and the weekly job (T044).
- **US3 (P5)** → depends on Foundational; consumes snapshot history from US2 for volatility.
- **Polish (P6)** → after desired stories complete.

### Within each story
Tests written first and FAIL → models → analytics (pure) → services → routes → MCP/UI.

## Parallel Opportunities

- Setup: T003–T006 in parallel.
- Foundational: T007/T008 (tests); T009/T010/T011 (domain); T015/T016; T020/T021/T022 (aggregation).
- US1: T030/T031/T032 (tests) parallel; then T033 (analytics) ∥ start; T037 (MCP) ∥ T038 (UI).
- US2: T039/T040 (tests); T041 ∥ T042 (analytics); T046 (MCP) ∥ T047 (UI).
- US3: T048/T049 (tests); T052 (MCP) ∥ T053 (UI).
- Different agents (Backend/Quant/DB/MCP/Streamlit/QA) work their owned directories in parallel once
  Foundational completes.

## Implementation Strategy

- **MVP** = Phase 1 + Phase 2 + Phase 3 (US1). Stop, validate US1 independently, demo.
- **Incremental**: add US2, then US3, each validated at its checkpoint without regressing prior stories.
- **Phase gate** (QA Engineer): acceptance scenarios pass, tests green, coverage met, no regressions,
  contracts honored — before advancing.
