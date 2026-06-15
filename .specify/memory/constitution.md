<!--
SYNC IMPACT REPORT
==================
Version change: (uninitialized template) → 1.0.0
Bump rationale: First ratification — placeholders replaced with concrete,
project-specific governance for a multi-agent, phased build.

Principles defined (all new):
  I.   Specialized Agent Ownership
  II.  Contract-First Integration
  III. Phased Incremental Delivery
  IV.  Test-First Quality (NON-NEGOTIABLE)
  V.   Financial Data Integrity
  VI.  Observability & Reproducibility

Sections added:
  - Technology & Architecture Constraints
  - Development Workflow & Quality Gates
  - Governance

Removed sections: none (template placeholders only)

Template/Doc sync status:
  ✅ .specify/templates/plan-template.md  — Constitution Check reads this file dynamically; aligned
  ✅ .specify/templates/spec-template.md  — generic scope; no constitution-specific constraints required
  ✅ .specify/templates/tasks-template.md — note updated to reflect mandatory test-first (Principle IV)
  ✅ CLAUDE.md — Governance pointer added referencing this constitution and agent roster

Deferred TODOs: none
-->

# Wealth AIssistant Constitution

## Core Principles

### I. Specialized Agent Ownership

Each domain of the system is owned by exactly one specialized agent role:
**Backend Architect** (application services and API layer), **Quant Analyst**
(financial models, portfolio analytics, numerical methods), **Database Engineer**
(schema, migrations, persistence, query performance), **MCP Engineer** (Model
Context Protocol servers and tool integrations), **Streamlit Engineer** (the
user-facing Streamlit application), and **QA Engineer** (test strategy, coverage,
and release verification).

Rules:
- Every change MUST be attributable to the agent role that owns the affected domain.
- An agent MUST NOT modify another domain's internals; cross-domain needs MUST be
  requested through that domain's published contract (see Principle II).
- Shared, cross-cutting decisions (naming, error model, logging format) MUST be
  ratified once and applied uniformly by all agents.

Rationale: Single-owner domains eliminate conflicting implementations and make every
change traceable, which is the foundation of consistency across a multi-agent build.

### II. Contract-First Integration

No cross-domain implementation begins before its contract exists and is agreed: HTTP/RPC
schemas for the Backend, table schemas and migrations for the Database, tool and resource
definitions for MCP servers, typed data models for analytics inputs/outputs, and component
data contracts for Streamlit.

Rules:
- Contracts (OpenAPI/JSON Schema, SQL DDL, MCP tool schemas, Pydantic/dataclass models)
  MUST be defined and committed before dependent code.
- A breaking contract change MUST bump the contract version and update all consumers in
  the same change set.
- Integration tests MUST validate behavior against the contract, not the implementation.

Rationale: Contracts are the only safe handoff mechanism between independently working
agents; they let domains evolve in parallel without breaking each other.

### III. Phased Incremental Delivery

The system is built in numbered phases. Each phase MUST deliver an independently testable,
working increment and MUST pass its quality gate before the next phase starts.

Rules:
- Each phase MUST map to one or more independently testable user stories (P1/P2/P3…).
- A phase is "done" only when its acceptance scenarios pass and the QA gate (Principle IV)
  is green.
- Later phases MUST NOT regress earlier phases; regression checks run at every phase boundary.

Rationale: Phased delivery converts a large, risky build into a sequence of verified
increments, raising reliability and making progress observable.

### IV. Test-First Quality (NON-NEGOTIABLE)

Tests are written before implementation and MUST fail first. The QA Engineer owns the test
strategy and the release gate.

Rules:
- TDD is mandatory: write test → confirm it fails → implement → make it pass → refactor.
- Financial and quantitative logic MUST have unit tests asserting against independently
  known-correct values.
- Cross-domain contracts MUST have integration/contract tests.
- A change MUST NOT merge with failing tests or below the project coverage gate.

Rationale: In a financial assistant, an undetected calculation error is a correctness
failure with real consequences; test-first is the cheapest place to catch it.

### V. Financial Data Integrity

Monetary and quantitative correctness is non-negotiable and deterministic.

Rules:
- Monetary values MUST use exact decimal arithmetic (e.g., Python `Decimal`); binary
  floating-point MUST NOT be used for currency.
- Every monetary or quantity value MUST carry an explicit currency/unit; mixed-unit
  operations MUST be rejected rather than silently coerced.
- External and user-supplied financial data MUST be validated at the system boundary
  before use.
- The same inputs MUST always produce the same outputs; non-deterministic sources (wall
  clock, market data, randomness) MUST be injected and recorded.

Rationale: Trust in a wealth assistant depends entirely on numbers being exact,
well-typed, and reproducible.

### VI. Observability & Reproducibility

Every meaningful operation is explainable after the fact.

Rules:
- Structured logging MUST be used across all domains with a shared format and correlation
  identifiers.
- Analytical results MUST be reproducible from recorded inputs, parameters, and data versions.
- Errors MUST be surfaced explicitly with actionable context; silent failure and broad
  exception swallowing are prohibited.

Rationale: Reliability is only credible when failures and results can be traced,
reproduced, and audited.

## Technology & Architecture Constraints

- **Language/Runtime**: Python 3.14; dependencies and environments managed with `uv`.
- **Backend**: Service/API layer owned by the Backend Architect.
- **Analytics**: Quantitative and portfolio logic owned by the Quant Analyst, isolated as
  testable, pure-as-possible modules.
- **Persistence**: Relational schema, migrations, and data access owned by the Database
  Engineer.
- **AI Integration**: MCP servers and tools owned by the MCP Engineer; tools expose typed
  schemas and are independently testable.
- **Frontend**: Streamlit application owned by the Streamlit Engineer; the UI consumes
  Backend/MCP contracts only — no business logic in the UI layer.
- **Quality**: Test tooling and CI gates owned by the QA Engineer.
- **Layering**: UI → Backend/MCP → Analytics/Persistence. Dependencies MUST flow in one
  direction; the UI MUST NOT access the database or perform financial calculations directly.

Specific framework choices (web framework, database engine, test runner) are decided per
feature in `/speckit-plan` and MUST be recorded in the plan's Technical Context.

## Development Workflow & Quality Gates

- **Spec-driven**: Features follow the Spec Kit flow — constitution → specify → (clarify)
  → plan → tasks → implement. This constitution governs every step.
- **Agent handoffs**: Work crossing a domain boundary MUST hand off via a committed contract
  (Principle II), never via direct edits to another agent's code.
- **Phase gate**: At each phase boundary the QA Engineer verifies that acceptance scenarios
  pass, tests are green, the coverage gate is met, no regressions exist, and contracts are
  honored. Failing any check blocks the next phase.
- **Review**: Every change is reviewed against this constitution; violations are either fixed
  or recorded in the plan's Complexity Tracking with explicit justification.
- **Definition of Done** (per task/phase): tests written-first and passing; contracts updated;
  structured logging present; financial values exact and validated; user-facing docs/quickstart
  updated where applicable.

## Governance

This constitution supersedes ad-hoc practices and conventions for the Wealth AIssistant
project. All plans, tasks, reviews, and implementations MUST verify compliance with these
principles.

- **Amendments**: Proposed as a documented change to this file including rationale and the
  migration impact on dependent templates and code. Amendments take effect once merged.
- **Versioning**: Semantic versioning of this document — MAJOR for principle removals or
  redefinitions or incompatible governance changes, MINOR for new principles/sections or
  materially expanded guidance, PATCH for clarifications and non-semantic edits.
- **Compliance review**: The QA Engineer enforces constitution compliance at every phase gate;
  unjustified complexity or contract violations block delivery.
- **Runtime guidance**: Use `CLAUDE.md` and the active `/speckit-plan` output for day-to-day
  development guidance; where any guidance conflicts with this constitution, the constitution wins.

**Version**: 1.0.0 | **Ratified**: 2026-06-12 | **Last Amended**: 2026-06-12
