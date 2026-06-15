# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`wealth-aissistent` — a Python-based wealth AI assistant. Early-stage; core architecture is not yet defined.

## Commands

```bash
# Install dependencies
uv sync

# Run the app
uv run python main.py

# Add a dependency
uv add <package>
```

## Stack

- **Python 3.14** (managed via uv, see `.python-version`)
- **Entry point**: `main.py`

## Governance

This project is built under **Spec-Driven Development** (GitHub Spec Kit). The
authoritative ruleset is the constitution at `.specify/memory/constitution.md` —
read it before planning or implementing. It mandates a multi-agent, phased build
and overrides any conflicting guidance.

Agent roles (single-owner domains): **Backend Architect**, **Quant Analyst**,
**Database Engineer**, **MCP Engineer**, **Streamlit Engineer**, **QA Engineer**.

Workflow: `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` →
`/speckit-tasks` → `/speckit-implement`.

<!-- SPECKIT START -->
**Active feature**: `001-portfolio-analytics` — Portfolio Tracking & Analytics.
Read the current plan and its design artifacts for technologies, structure, and
contracts before implementing:

- Plan: `specs/001-portfolio-analytics/plan.md`
- Spec: `specs/001-portfolio-analytics/spec.md`
- Research: `specs/001-portfolio-analytics/research.md`
- Data model: `specs/001-portfolio-analytics/data-model.md`
- Contracts: `specs/001-portfolio-analytics/contracts/` (openapi.yaml, internal-contracts.md)
- Quickstart: `specs/001-portfolio-analytics/quickstart.md`

Stack chosen in the plan: FastAPI + Pydantic v2 (backend), SQLAlchemy 2.0 + Alembic
+ PostgreSQL (persistence), pandas/numpy over `Decimal` (analytics), Plaid/fake
aggregation behind a provider port, MCP Python SDK (read-only tools), Streamlit (UI),
pytest (tests). Next: `/speckit-tasks`.
<!-- SPECKIT END -->
