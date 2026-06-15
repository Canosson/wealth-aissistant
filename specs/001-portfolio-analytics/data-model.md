# Data Model: Portfolio Tracking & Analytics

**Feature**: `001-portfolio-analytics` | **Date**: 2026-06-12 | **Updated**: 2026-06-13

Owned by the **Database Engineer** (`persistence/`, `migrations/`). Money/quantity columns are
`NUMERIC` (never float). Every monetary value carries an ISO-4217 currency. Timestamps are stored in
UTC; date-only fields use ISO `YYYY-MM-DD`. All investor-scoped tables enforce `investor_id` isolation.

## Cross-Cutting Implementation Notes

- **Cascade erasure** (`FR-018`): All child tables (`LinkedAccountConnection`, `Account`, `Holding`,
  `Price`, `FxRate`, `PortfolioSnapshot`, `SnapshotHolding`) carry `ON DELETE CASCADE` on their
  `investor_id` FK so that deleting an `Investor` row removes all associated data atomically.
- **Encryption at rest** (`FR-019`): PII fields (email) and linked-account access tokens/credentials
  are encrypted with AES-256-GCM before storage (`persistence/crypto.py`). The encryption key is
  injected via the `ENCRYPTION_KEY` environment variable and never committed.
- **Weekly snapshot cadence** (`FR-016`): The scheduled job (`scheduler/jobs.py`) runs every
  **Tuesday** via APScheduler. Volatility is therefore annualized from **weekly returns** using
  `σ_weekly × √52` (not daily × √252). See R5/R6 in `research.md`.

## Shared value objects (`domain/`, ratified)

- **Currency**: ISO-4217 alphabetic code (e.g., `USD`, `EUR`). Validated against a known set.
- **Money**: `{ amount: Decimal, currency: Currency }`. Arithmetic requires equal currency or raises
  `CurrencyMismatchError`. Persisted as two columns: `*_amount NUMERIC(20,4)` + `*_currency CHAR(3)`.

## Entities

### Investor
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| email | text, unique, not null | login identity |
| password_hash | text, not null | Argon2id |
| reporting_currency | CHAR(3), not null | single reporting currency |
| created_at | timestamptz, not null | |

Validation: email unique & well-formed; `reporting_currency` is a known Currency.

### LinkedAccountConnection
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| investor_id | UUID (FK → Investor) | isolation key |
| provider | text, not null | e.g. `plaid`, `fake` |
| provider_item_id | text, not null | provider's connection handle |
| institution_name | text | display |
| status | enum, not null | see state machine below |
| last_synced_at | timestamptz, null | null until first sync |
| error_detail | text, null | populated when status = `error`/`needs_reauth` |

Unique: (`investor_id`, `provider`, `provider_item_id`). Provider credentials/access tokens are
**never** stored in plaintext and **never** returned by the API (FR-015).

**Status state machine**:
`pending → active` (first successful sync) · `active → needs_reauth` (auth revoked/MFA) ·
`active → error` (sync failure) · `needs_reauth → active` / `error → active` (recovery) ·
any → `unlinked` (investor removes; holdings purged).

### Account
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| connection_id | UUID (FK → LinkedAccountConnection) | |
| provider_account_id | text, not null | |
| name | text | display |
| type | enum | `brokerage`, `cash`, `other` |
| currency | CHAR(3) | native account currency |
| cash_balance_amount | NUMERIC(20,4), null | with `cash_balance_currency` |

Unique: (`connection_id`, `provider_account_id`).

### Security (Instrument)
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| symbol | text, null | ticker/identifier when available |
| name | text | |
| asset_class | enum | `equity`, `etf`, `fund`, `fixed_income`, `cash`, `crypto`, `other`, `unclassified` |
| sector | text, null | `null` → grouped as "Unclassified" in allocation |
| currency | CHAR(3) | quote currency |

Dedup key for consolidation (FR-004): prefer a stable instrument identifier (symbol + currency); same
security across accounts maps to one Security row.

### Holding (Position)
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| account_id | UUID (FK → Account) | |
| security_id | UUID (FK → Security) | |
| quantity | NUMERIC(20,8), not null | fractional shares supported |
| cost_basis_amount | NUMERIC(20,4), null | optional, with currency |
| as_of | timestamptz, not null | source data timestamp |

Unique: (`account_id`, `security_id`). Value = quantity × latest Price (computed, not stored on row).

### Price
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| security_id | UUID (FK → Security) | |
| price_amount | NUMERIC(20,4), not null | with `price_currency` |
| as_of | date, not null | daily close |

Unique: (`security_id`, `as_of`). Missing price → holding shown as "price unavailable" and excluded
from totals it would distort (FR-012), never counted as zero.

### FxRate
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| base_currency | CHAR(3) | |
| quote_currency | CHAR(3) | |
| rate | NUMERIC(20,10), not null | base→quote |
| as_of | date, not null | |

Unique: (`base_currency`, `quote_currency`, `as_of`). Recorded so conversions are reproducible (R3).

### PortfolioSnapshot  *(reproducibility + history — R6)*
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| investor_id | UUID (FK → Investor) | |
| as_of | date, not null | |
| total_value_amount | NUMERIC(20,4), not null | in reporting currency, with currency |
| net_external_flow_amount | NUMERIC(20,4), not null default 0 | deposits − withdrawals that day |

Unique: (`investor_id`, `as_of`). Children below freeze the inputs used.

### SnapshotHolding *(child of PortfolioSnapshot)*
| Field | Type | Notes |
|-------|------|-------|
| snapshot_id | UUID (FK → PortfolioSnapshot) | |
| security_id | UUID (FK → Security) | |
| quantity | NUMERIC(20,8) | as of snapshot |
| price_amount | NUMERIC(20,4) | price used (+currency) |
| fx_rate | NUMERIC(20,10) | rate used to reach reporting currency |
| value_amount | NUMERIC(20,4) | computed value in reporting currency |

## Relationships

```text
Investor 1───* LinkedAccountConnection 1───* Account 1───* Holding *───1 Security 1───* Price
Investor 1───* PortfolioSnapshot 1───* SnapshotHolding *───1 Security
Security/Currency conversions resolved via FxRate (by date)
```

## Derived (not stored) — owned by `analytics/` (Quant Analyst)

- **Portfolio**: consolidated, deduplicated holdings across an investor's accounts + total value
  (reporting currency). Pure function of Holdings + Prices + FxRates.
- **Allocation**: weights by asset_class / sector / account; sums to 100% (FR-007); `null` sector →
  "Unclassified".
- **Performance**: period return & gain/loss from two PortfolioSnapshots and net flows (R4).
- **Risk**: per-holding concentration (≥20% flag) + HHI; annualized volatility from ≥30 daily
  snapshots; diversification summary (R5).

## Validation rules (from requirements)

- Reject mixed-currency arithmetic (Principle V); convert via recorded FxRate only.
- Allocation weights MUST sum to exactly 100% for non-empty portfolios (SC-004).
- All investor-scoped reads MUST filter by `investor_id` (FR-013).
- Holdings of the same Security across accounts consolidate without double counting (FR-004), with a
  retained per-account breakdown.
