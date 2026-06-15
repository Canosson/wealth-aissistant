# Internal Contracts: MCP Tools & Aggregation Provider Port

**Feature**: `001-portfolio-analytics` | **Date**: 2026-06-12

Two internal contracts that must be committed before their dependent code (Principle II).

---

## 1. MCP Tool Surface (owned by MCP Engineer — `src/wealth_assistant/mcp/`)

A **read-only** MCP server projecting service-layer read methods. Every tool requires an authenticated
investor context (a session token passed by the host); tools never mutate state and never expose
provider credentials. Tool outputs mirror the corresponding REST response schemas in `openapi.yaml`.

| Tool | Input | Output (mirrors OpenAPI schema) | Maps to |
|------|-------|----------------------------------|---------|
| `get_portfolio` | `{}` | `Portfolio` | US1 / `GET /portfolio` |
| `get_allocation` | `{ "by": "asset_class" \| "sector" \| "account" }` | `Allocation` | US2 / `GET /portfolio/allocation` |
| `get_performance` | `{ "period": "1M" \| "3M" \| "6M" \| "1Y" \| "YTD" \| "ALL" }` | `Performance` | US2 / `GET /portfolio/performance` |
| `get_risk` | `{}` | `Risk` | US3 / `GET /portfolio/risk` |

Rules:
- Tools call the **same service methods** the REST API uses — no business logic in the MCP layer.
- Money fields are exact-decimal strings with a currency, identical to the REST contract.
- Errors are returned as structured tool errors carrying `code` + `message` (+ `correlation_id`).
- Contract test (QA): each tool's declared output schema must validate against the OpenAPI component
  of the same name.

---

## 2. Aggregation Provider Port (owned by Backend Architect — `src/wealth_assistant/aggregation/`)

The single seam between the system and any external account-aggregation vendor. Service code depends
only on this port; concrete adapters (`plaid`, `fake`) implement it. All money/quantity values crossing
the port are exact decimals with explicit currency.

```text
Port: AggregationProvider

  create_link_token(investor_id: UUID) -> LinkToken
      # Begin a linking session. LinkToken = { link_token: str }

  exchange_public_token(public_token: str) -> ProviderConnection
      # Complete linking. Returns connection handle + institution.
      # ProviderConnection = {
      #   provider_item_id: str,
      #   institution_name: str,
      #   access_ref: opaque   # secret handle; stored encrypted, never returned to clients
      # }

  fetch_accounts(connection: ProviderConnection) -> list[ProviderAccount]
      # ProviderAccount = {
      #   provider_account_id: str, name: str, type: "brokerage"|"cash"|"other",
      #   currency: str(ISO-4217), cash_balance: Decimal|None
      # }

  fetch_holdings(connection: ProviderConnection) -> list[ProviderHolding]
      # ProviderHolding = {
      #   provider_account_id: str,
      #   security: { symbol: str|None, name: str, asset_class: str, sector: str|None, currency: str },
      #   quantity: Decimal, cost_basis: Decimal|None, price: Decimal|None, as_of: date
      # }
```

### Error contract (raised by adapters, handled by services)

| Exception | Meaning | Service reaction |
|-----------|---------|------------------|
| `ProviderAuthError` | credentials revoked / MFA required | set connection `needs_reauth`, surface clear retry message |
| `ProviderUnavailableError` | transient outage / timeout | keep last-known data, mark portfolio `stale`, `409` on refresh |
| `ProviderUnsupportedError` | institution/account not supported | inform investor, no partial corruption |

### Determinism & testing (Principle V/VI)

- The **fake** adapter returns fixed, seeded data → integration tests are fully deterministic and
  offline.
- The **Plaid** adapter targets the **sandbox** environment for dev/test; real credentials are
  config-only and never committed.
- `as_of`, prices, and FX used in a sync are persisted (see `PortfolioSnapshot`) so any analytics
  result can be reproduced from recorded inputs.
