# Implementation Plan: Portfolio Tracking & Analytics

**Branch**: `001-portfolio-analytics` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-portfolio-analytics/spec.md`

## Summary

Build the MVP of the Wealth AIssistant: an individual retail investor securely links external
brokerage/bank accounts through an account-aggregation provider, the system consolidates holdings
into a single deduplicated portfolio, and exposes allocation, performance, and risk analytics. The
build is delivered in three phases mapped to the spec's user stories (US1 link+consolidate → US2
allocation+performance → US3 risk), with each domain owned by a single specialized agent and
integrated through committed contracts (REST/OpenAPI, MCP tool schemas, an aggregation provider port,
and typed analytics models).

## Technical Context

**Language/Version**: Python 3.14 (managed with `uv`)

**Primary Dependencies**:
- Backend API: FastAPI + Pydantic v2 (Backend Architect)
- Persistence: SQLAlchemy 2.0 + Alembic migrations (Database Engineer)
- Analytics: pandas + numpy over `Decimal`-backed inputs (Quant Analyst)
- Aggregation: provider port + Plaid adapter (sandbox) + in-memory fake (Backend Architect)
- AI tool surface: MCP Python SDK (`mcp`) exposing read-only portfolio tools (MCP Engineer)
- UI: Streamlit (Streamlit Engineer)
- Auth: Argon2 password hashing (`argon2-cffi`) + signed session tokens (PyJWT)
- Scheduling: APScheduler — weekly (Tuesday) price-snapshot background job (Backend Architect)
- Privacy: data export + account deletion (cascading erasure); encryption-at-rest for PII & credentials
- Cross-cutting: `structlog` structured logging; `httpx` for outbound provider calls

**Storage**: PostgreSQL (monetary/quantity columns as `NUMERIC`; never floating point)

**Testing**: pytest + pytest-cov; `respx` for HTTP provider mocking; schema validation of API
responses against the OpenAPI contract; fake aggregation provider for deterministic integration tests

**Target Platform**: Linux server (FastAPI backend + MCP server); Streamlit app served to the investor's browser

**Project Type**: Web application (Streamlit frontend + FastAPI backend) plus a read-only MCP server

**Performance Goals**: Consolidated portfolio of up to ~500 holdings renders in < 2 s; backend read
endpoints p95 < 500 ms (excluding external provider latency)

**Constraints**: Exact decimal money with explicit currency on every amount; strictly read-only
external data (no money movement/trading); per-investor data isolation; analytics deterministic for
fixed inputs (clock, prices, and FX injected and recorded); performance history is forward-only (from
link date); personal data & credentials encrypted at rest; investor data exportable and fully erasable
on account deletion

**Scale/Scope**: Individual retail investors; MVP scope = US1–US3 only

**Open items resolved in research.md**: Python 3.14 library compatibility, aggregation provider
selection, return-calculation method, volatility & concentration definitions, FX source.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Specialized Agent Ownership | Every source directory has exactly one owning agent (see ownership map below); cross-cutting dirs ratified once | ✅ PASS |
| II. Contract-First Integration | OpenAPI (REST), MCP tool schemas, aggregation provider port, and Pydantic/SQLAlchemy models authored before dependent code | ✅ PASS |
| III. Phased Incremental Delivery | Phases map 1:1 to independently testable user stories US1/US2/US3, each with a QA gate | ✅ PASS |
| IV. Test-First Quality (NON-NEGOTIABLE) | Contract + integration + unit tests written before implementation; financial logic asserted against known-correct values | ✅ PASS |
| V. Financial Data Integrity | `Money` value object backed by `Decimal`; `NUMERIC` storage; explicit currency/unit; boundary validation; injected clock/prices/FX | ✅ PASS |
| VI. Observability & Reproducibility | `structlog` with correlation IDs across all layers; analytics reproducible from recorded snapshots; explicit error states, no silent failure | ✅ PASS |

**Result**: No violations. Complexity Tracking left empty.

**Layering enforced** (one-directional, per constitution): `ui → api → services → {analytics, persistence, aggregation}`; UI never touches the database or performs financial math.

## Project Structure

### Documentation (this feature)

```text
specs/001-portfolio-analytics/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── openapi.yaml          # REST API contract (Backend ↔ UI)
│   └── internal-contracts.md # MCP tool schemas + aggregation provider port
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/wealth_assistant/
├── domain/            # SHARED (ratified once): Money/Currency value objects, enums, errors
├── analytics/         # Quant Analyst: pure functions — consolidation, allocation, performance, risk
├── persistence/       # Database Engineer: SQLAlchemy models, repositories, session/unit-of-work
├── aggregation/       # Backend Architect: provider Port + Plaid adapter + in-memory fake
├── scheduler/         # Backend Architect: weekly (Tuesday) snapshot job + scheduler bootstrap
├── services/          # Backend Architect: application services (orchestration, no I/O details)
├── api/               # Backend Architect: FastAPI app, routers, Pydantic request/response schemas
├── mcp/               # MCP Engineer: read-only MCP server projecting service-layer reads as tools
├── ui/                # Streamlit Engineer: Streamlit app (consumes REST API only)
├── config.py          # SHARED: settings (env-driven)
└── observability.py   # SHARED: structlog config, correlation-id middleware

migrations/            # Database Engineer: Alembic environment + versions
tests/
├── contract/          # QA Engineer: API responses vs OpenAPI; MCP tool schemas; provider port
├── integration/       # QA Engineer: end-to-end flows over the fake aggregation provider
└── unit/              # QA Engineer: analytics & domain (Money/FX) against known-correct values
```

**Structure Decision**: Web-application layout. Each top-level package under `src/wealth_assistant`
is owned by exactly one agent role (ownership map below); `domain/`, `config.py`, and
`observability.py` are shared and any change to them is a ratified cross-cutting decision.

### Agent → Directory Ownership Map (Principle I)

| Agent | Owns | May depend on (read contracts of) |
|-------|------|-----------------------------------|
| Backend Architect | `api/`, `services/`, `aggregation/`, `scheduler/` | `domain`, `persistence`, `analytics`, aggregation port |
| Quant Analyst | `analytics/` | `domain` only (pure functions) |
| Database Engineer | `persistence/`, `migrations/` | `domain` |
| MCP Engineer | `mcp/` | `services` (read methods), `domain` |
| Streamlit Engineer | `ui/` | REST API (OpenAPI) only |
| QA Engineer | `tests/` | all contracts |
| (Shared / ratified) | `domain/`, `config.py`, `observability.py` | — |

## Phasing (maps to /speckit-tasks)

- **Phase Setup**: project scaffolding (packages above), `uv` deps, lint/format, structlog,
  `Money`/`Currency` domain value objects, Postgres + Alembic baseline. *(Shared + Database Engineer)*
- **Phase Foundational**: auth (register/login + session), connection & account persistence,
  aggregation provider port + fake + Plaid sandbox adapter, base error model, encryption-at-rest for
  PII/credentials, account export + deletion (cascading erasure), and the weekly (Tuesday) snapshot
  scheduler. **Blocks all stories.**
- **Phase US1 (P1) — MVP**: link account → import holdings → consolidated, deduplicated portfolio view;
  refresh + last-updated; unlink. REST endpoints + Streamlit portfolio page + MCP `get_portfolio`.
- **Phase US2 (P2)**: allocation (asset class / sector / account) + performance (return, gain/loss) over
  periods; portfolio snapshots for history. Analytics modules + endpoints + UI + MCP tools.
- **Phase US3 (P3)**: risk (concentration, volatility, diversification) + plain-language insights.
- **Phase Polish**: docs, quickstart validation, performance pass on large portfolios.

Each phase ends at a QA gate (acceptance scenarios pass, tests green, coverage gate met, no regressions,
contracts honored) before the next begins.

## Complexity Tracking

> No constitution violations. No entries required.
