# HANDOFF — wealth-aissistent

**Date**: 2026-06-13 | **Feature**: `001-portfolio-analytics` | **Branch**: `main`

## Current state

**All 59 spec tasks (T001–T059) are complete.** 126 tests passing, coverage ≥80% (gate 80%).
A council review then judged the MVP *architecturally solid but not production-solid*, producing a
post-spec backlog. **All 3 P0 correctness items are done.**

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

### P0 work completed this session (2026-06-13)

| Item | What was done | Files |
|------|--------------|-------|
| Disable snapshot job | New `snapshot_job_enabled` setting (default **False**); `register_jobs()` early-returns with a logged warning until the pipeline is validated. Env: `SNAPSHOT_JOB_ENABLED=true` to enable. | `config.py`, `scheduler/app.py` |
| Fix snapshot placeholders | `ConsolidatedHolding` now retains `price_amount`/`price_currency`/`fx_rate` used at valuation; `SnapshotService` freezes those real inputs into `SnapshotHolding` (no migration needed — columns existed). Invariant tested: `value == quantity × price × fx` on every row. | `analytics/consolidation.py`, `services/snapshot_service.py`, `tests/integration/test_snapshot_service.py` (9 tests, TDD red→green) |
| Net external flows ledger | New `CashFlow` model + `cash_flows` table (signed NUMERIC amount in reporting currency, `occurred_on` date, CASCADE delete). `CashFlowRepository.net_between()` sums flows for any date window. `SnapshotRepository.get_latest_before()` finds the prior snapshot. `SnapshotService` now queries flows between snapshots and writes the real `net_external_flow_amount` (no longer hardwired to 0). Migration `002_cash_flows.py`. 13 new tests, TDD red→green. | `persistence/models.py`, `persistence/repositories.py`, `services/snapshot_service.py`, `migrations/versions/002_cash_flows.py`, `tests/integration/test_cash_flows.py` |

### P1/P2 work completed this session (2026-06-13 cont.)

| Item | What was done | Files |
|------|--------------|-------|
| Docker stack (P2 #9) | `Dockerfile` (Python 3.14 + uv, multi-stage), `docker-compose.yml` (`db` Postgres 16 + `app` + one-shot `migrate`/`test` services), `.dockerignore`, `.env.example`, `scripts/initdb/01-create-test-db.sql` (creates `wealth_test`). Runtime: colima + docker CLI installed via brew. | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `scripts/initdb/` |
| Suite on real Postgres (P1 #5) | `conftest.py` now honors `TEST_DATABASE_URL` (default still in-memory SQLite; falls back to `NullPool` for server engines). **All 126 tests pass against Postgres 16** via `docker compose run --rm test`. | `tests/conftest.py` |
| **Postgres-only migration bug fixed** | Migration 001 created each enum type explicitly *and* via `sa.Enum(create_type=True)` on the column → `DuplicateObject: type "connection_status" already exists` on `alembic upgrade`. SQLite ignored enums so it was never caught (exactly the coverage caution the council raised). Columns now use `postgresql.ENUM(name=..., create_type=False)`. `alembic upgrade head` reaches **rev 002** cleanly; verified 11 tables, 7 `ON DELETE CASCADE` FKs, NUMERIC(20,4/8/10). | `migrations/versions/001_initial_tables.py` |

## ⚠️ Inputs needed from you (address before / at start of next session)

These are the only items blocked on something Claude cannot self-serve. Everything
else in the backlog below can proceed without you.

| # | What's needed | Why / blocks | Where to get it |
|---|---------------|--------------|-----------------|
| A | **Plaid sandbox credentials**: `PLAID_CLIENT_ID` + `PLAID_SECRET` | Unblocks P1 #4 (first real Plaid run; `plaid_adapter.py` still at 0% execution). Adapter raises `RuntimeError` without them. | Plaid dashboard → Developers → **Keys** → copy `client_id` and the **Sandbox** secret. Free sandbox account at dashboard.plaid.com. Paste into `.env` (`PLAID_CLIENT_ID=…`, `PLAID_SECRET=…`, `AGGREGATION_PROVIDER=plaid`). Do **not** commit `.env`. |
| B | **A GitHub repo for this project** (decision + creation) | Unblocks P2 #10 (CI). Current `origin` = `github.com/Canosson/MusicLive.git` — wrong project; nothing for this codebase to push to. | Create an empty private repo (e.g. `wealth-aissistent`), then either you run `git remote set-url origin <url>` or tell Claude to. CI workflow file can be authored before this exists. |
| C | *(Later, P2/P3 — not yet)* **Deployment target decision** | Needed only when going past local: host (Fly/Railway/Render/VPS), domain, secrets store. | No action now — flagged so it's on your radar. |

**No docs needed for:** P1 #6 (boot MCP server), P2 #11 (security hardening), and authoring the
P2 #10 CI workflow file — Claude can do all three with zero input from you.

## What's next — backlog (priority order)

### P1 — Reality check

4. One end-to-end run against the **real Plaid sandbox** (`plaid_adapter.py` has never executed; 0%).
5. ✅ **DONE** — suite + Alembic migrations validated on real Postgres 16 (see session note above).
6. Boot the actual MCP server and validate live output (current contract tests validate
   hand-written sample JSON, not server output).
7. Dogfood: one real human, two weeks, fake or sandbox provider.
8. Re-enable the snapshot job (`SNAPSHOT_JOB_ENABLED=true`) once 3–6 are validated.

### P2 — Ops floor (before any public URL)

9. ✅ **DONE** — `.env.example`, Dockerfile, docker-compose (app + Postgres) created & validated.
10. CI: pytest on Postgres + coverage + ruff per push; add per-module coverage floors.
11. Security pass: enforce 32-byte JWT secret; make `_ALLOW_MISSING_ENCRYPTION_KEY` impossible
    outside tests; rate-limit auth endpoints.

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
| MCP field names | Tool outputs match OpenAPI components exactly: `concentration`, `annualized_volatility_pct`, nested `diversification`, Money objects (fixed in Polish) |
| Cash flows | `CashFlow` table — signed `amount NUMERIC(20,4)` in investor's reporting currency (+ = deposit, − = withdrawal), `occurred_on DATE`. `SnapshotService` sums flows between prior snapshot and today via `CashFlowRepository.net_between()`. No flows → `net_external_flow_amount = 0` (safe default). Migration: `002_cash_flows.py`. |

## How to verify current state

### Host-side (fast, in-memory SQLite — default dev loop)

```bash
uv run pytest                                             # 126 passed
uv run pytest --cov=wealth_assistant                     # ≥80% (gate 80)
uv run pytest tests/integration/test_snapshot_service.py -v  # 9 passed — P0 placeholder fix
uv run pytest tests/integration/test_cash_flows.py -v    # 13 passed — P0 flows ledger
uv run ruff check src/ tests/
```

### Real Postgres (via docker-compose)

```bash
colima start                          # one-time per boot — starts the docker VM
cp .env.example .env                  # if missing (a real .env was generated this session)
docker compose run --rm --build migrate   # alembic upgrade head → rev 002
docker compose run --rm --build test      # 126 passed against Postgres 16
docker compose up app                 # API on :8000
```

Notes: `docker` CLI needs `colima` running (`colima status` to check). The `migrate`/`test`
images are cached — pass `--build` after any code change. `docker compose down` stops containers
but keeps the `pgdata` volume; `down -v` wipes it (init script recreates `wealth_test` on next boot).

## Cost context

Planning pipeline (Opus 4.8): ~$81 · Implementation phases 1–6 (Sonnet 4.6): ~$21+ ·
Council review + P0 fixes (Sonnet 4.6): ~$9 · Docker/Postgres setup + migration fix (Opus 4.8):
~$6. Continue on Sonnet 4.6 for P1–P2 work; reserve Opus for design/debugging.

## Spec artifacts index

```
specs/001-portfolio-analytics/
├── spec.md                    # 19 FRs, 3 user stories, 9 SCs
├── plan.md                    # tech stack, phasing, agent ownership map
├── research.md                # 9 decisions — R5/R6 updated to weekly √52
├── data-model.md              # 9 entities + cross-cutting notes (cascade, crypto, cadence)
├── quickstart.md              # run guide + validation scenarios
├── tasks.md                   # 59/59 tasks ✅
├── checklists/requirements.md # 16/16 ✅
└── contracts/
    ├── openapi.yaml           # REST contract incl. /me/export + DELETE /me
    └── internal-contracts.md  # MCP tool schemas + AggregationProvider port
migrations/versions/
├── 001_initial_tables.py      # all 9 original entities — enum cols use create_type=False (Postgres fix)
└── 002_cash_flows.py          # cash_flows table (P0 flows ledger)
.specify/memory/constitution.md  # 6 principles — read before implementing
HANDOFF.md                       # this file
```
