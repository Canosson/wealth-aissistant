# Feature Specification: Portfolio Tracking & Analytics

**Feature Branch**: `001-portfolio-analytics`

**Created**: 2026-06-12

**Status**: Draft

**Input**: User description: "A wealth assistant for individual retail investors that securely links their external brokerage and bank accounts, consolidates holdings into a single portfolio view, and provides allocation, performance, and risk analytics."

## Clarifications

### Session 2026-06-12

- Q: Where does historical data for performance (returns over periods) come from? → A: Forward-only — performance history begins when accounts are linked and accrues from recorded snapshots going forward; longer periods show "insufficient history" until enough history exists.
- Q: What is the data refresh cadence? → A: A scheduled price snapshot runs weekly on Tuesdays (background process) in addition to investor on-demand refresh; full holdings refresh remains on-demand.
- Q: What compliance & data-handling posture applies? → A: Privacy-by-design — investors can export their data and delete their account (cascading erasure of all personal data and linked-account authorizations); personal data and credentials are encrypted at rest.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Link accounts and see a consolidated portfolio (Priority: P1)

An individual investor securely connects one or more of their external brokerage and bank
accounts. The assistant imports their current holdings and shows a single consolidated view:
total portfolio value plus a list of every holding with its quantity and current market value.

**Why this priority**: This is the foundational value of the product — "see everything I own in
one place." Without it, no analytics are possible. It is the smallest slice that is independently
useful: an investor with scattered accounts immediately gains a unified net-worth-of-investments view.

**Independent Test**: Link at least one supported account, confirm the imported holdings and total
value match the source institution (within rounding), and confirm a second linked account's holdings
are merged into the same consolidated total.

**Acceptance Scenarios**:

1. **Given** a signed-in investor with no linked accounts, **When** they link a supported brokerage
   account and authorize access, **Then** the account's holdings appear in the portfolio with a
   correct total value that matches the source institution.
2. **Given** an investor with one linked account, **When** they link a second account, **Then** the
   consolidated portfolio total equals the sum of both accounts and holdings of the same security
   across accounts are shown consistently.
3. **Given** an investor with linked accounts, **When** they request a data refresh, **Then** holdings
   and values update to the latest available data and a "last updated" time is shown.
4. **Given** an investor with linked accounts, **When** they unlink an account, **Then** its holdings
   are removed from the consolidated portfolio and the total is recalculated.

---

### User Story 2 - Portfolio allocation and performance analytics (Priority: P2)

The investor views how their portfolio is allocated (e.g., by asset class, sector, and account) and
how it has performed over time (total return and gain/loss over selectable periods).

**Why this priority**: Once holdings are consolidated, allocation and performance are the insights
investors most want. It builds directly on US1 but is independently demonstrable.

**Independent Test**: With at least two holdings of different asset classes linked, confirm the
allocation breakdown sums to 100% and that a selected-period return is computed and displayed.

**Acceptance Scenarios**:

1. **Given** a consolidated portfolio, **When** the investor opens allocation, **Then** they see
   breakdowns (by asset class, sector, and account) whose percentages sum to 100%.
2. **Given** a portfolio with history accrued since the accounts were linked, **When** the investor
   selects a time period covered by that history, **Then** they see total return and absolute
   gain/loss for that period; periods longer than the available history show "insufficient history".
3. **Given** a holding with no available classification, **When** allocation is shown, **Then** it is
   grouped under an explicit "Unclassified" bucket rather than being dropped.

---

### User Story 3 - Risk and diversification insights (Priority: P3)

The investor views risk and diversification measures for their portfolio, such as concentration in
any single holding, diversification across asset classes, and volatility, with plain-language insights.

**Why this priority**: Risk insights deepen the product's advisory value but are not required for the
core "track and analyze" MVP. They build on US1/US2 and remain independently testable.

**Independent Test**: With a portfolio containing a dominant holding, confirm the concentration metric
correctly flags it and that at least one diversification/volatility measure is displayed.

**Acceptance Scenarios**:

1. **Given** a portfolio where one holding exceeds a high concentration threshold, **When** risk is
   shown, **Then** the concentration is reported and the holding is highlighted.
2. **Given** a portfolio with sufficient history, **When** the investor opens risk, **Then** a
   volatility measure and a diversification summary are displayed with a plain-language explanation.

---

### Edge Cases

- **Linking failures**: institution credentials are invalid, access is revoked, or additional
  verification (e.g., multi-factor) is required mid-flow — the investor is told clearly and can retry.
- **Stale or failed refresh**: a refresh cannot reach an institution — the last known values and their
  age are shown, with a clear indication that data is stale.
- **Unsupported institution or account type**: linking is attempted for something not supported — the
  investor is informed without a confusing failure.
- **Missing market price** for a held security — the holding is shown with an explicit "price
  unavailable" state and excluded from totals it would distort, rather than counted as zero silently.
- **Multiple currencies** across accounts — values are converted to the investor's single reporting
  currency, with the conversion basis disclosed.
- **Duplicate / overlapping holdings** of the same security across accounts — consolidated correctly
  without double counting.
- **Empty portfolio** (no holdings yet) — a clear empty state instead of misleading zeros or errors.
- **Insufficient history** — a recently linked investor requesting a period longer than the history
  accrued since linking sees an explicit "insufficient history" state, not a misleading zero return.
- **Very large portfolios** (hundreds of holdings) — remain usable and readable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let an investor securely link one or more external brokerage and bank
  accounts by authorizing access through an account-aggregation flow.
- **FR-002**: System MUST import current holdings (security, quantity, and value) and account balances
  from each linked account.
- **FR-003**: System MUST present a consolidated portfolio view combining all linked accounts, showing
  total value and a per-holding list with quantity and current value.
- **FR-004**: System MUST consolidate holdings of the same security held across multiple accounts
  without double counting, while still allowing a per-account breakdown.
- **FR-005**: System MUST allow the investor to refresh data on demand and MUST display when the data
  was last updated.
- **FR-006**: System MUST allow the investor to unlink an account, after which its holdings are removed
  from the consolidated portfolio and totals are recalculated.
- **FR-007**: System MUST display allocation breakdowns of the portfolio by asset class, by sector, and
  by account, with percentages that sum to 100%.
- **FR-008**: System MUST compute and display portfolio performance (total return and absolute
  gain/loss) over investor-selectable time periods, using history accrued from when accounts were
  linked; periods exceeding the available history MUST be reported as "insufficient history".
- **FR-009**: System MUST compute and display risk and diversification measures, including
  single-holding concentration and a volatility measure, with plain-language explanations.
- **FR-010**: System MUST convert values from accounts denominated in other currencies into the
  investor's single reporting currency and disclose the conversion basis.
- **FR-011**: System MUST represent monetary amounts exactly (no rounding drift) and MUST show the
  currency for every displayed amount.
- **FR-012**: System MUST handle linking, refresh, and pricing failures gracefully, showing clear
  status (including data staleness) without silently producing incorrect totals.
- **FR-013**: System MUST require each investor to authenticate before accessing any financial data,
  and MUST scope all data strictly to the authenticated investor.
- **FR-014**: System MUST treat all imported account data as read-only (no ability to move money or
  place trades) for this feature.
- **FR-015**: System MUST keep an investor's linked-account credentials/authorizations protected such
  that they are never exposed back to the investor or to other users.
- **FR-016**: System MUST capture a portfolio value snapshot on a scheduled weekly basis (Tuesdays) via
  a background process, in addition to on-demand refreshes, to build performance and risk history.
- **FR-017**: System MUST let an investor export all of their personal and portfolio data in a
  portable, machine-readable format.
- **FR-018**: System MUST let an investor delete their account, cascading to erase all of their
  personal data, holdings, snapshots, and linked-account authorizations.
- **FR-019**: System MUST encrypt personal data and linked-account credentials at rest.

### Key Entities *(include if feature involves data)*

- **Investor**: The authenticated individual who owns the portfolio; has a single reporting currency.
- **Linked Account Connection**: An authorized link to an external institution; has a status
  (active, needs re-authorization, error) and a last-synced time.
- **Account**: A specific account at an institution (e.g., brokerage, cash); belongs to a connection.
- **Holding (Position)**: A quantity of a specific security within an account, with current value.
- **Security (Instrument)**: An investable instrument with attributes such as name, asset class, and
  sector classification.
- **Price**: The market value of a security at a point in time, used to value holdings.
- **Portfolio Snapshot**: A recorded point-in-time portfolio value (and the prices/rates used) that
  builds performance and risk history forward from when accounts were linked.
- **Portfolio**: The consolidated, deduplicated aggregate of all holdings across the investor's accounts.
- **Analytics Result**: A computed allocation, performance, or risk output derived from the portfolio
  and snapshot history, tied to the inputs and time period it was computed from.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new investor can link their first account and see their consolidated holdings in under
  5 minutes from sign-in.
- **SC-002**: The consolidated portfolio total matches the sum of linked-account values from the source
  institutions to the cent (no rounding drift).
- **SC-003**: After a successful refresh, displayed holdings reflect the latest available source data,
  and the "last updated" time is always visible.
- **SC-004**: Allocation breakdowns sum to exactly 100% for any non-empty portfolio.
- **SC-005**: For a portfolio with a known history, the reported period return matches an independent
  manual calculation for the same period.
- **SC-006**: At least 90% of investors can complete account linking on the first attempt without
  external help.
- **SC-007**: A portfolio of up to several hundred holdings loads and is navigable without the investor
  perceiving noticeable delay.
- **SC-008**: When a data source is unavailable, the investor always sees correct staleness information
  rather than a silently wrong total (0% incidence of silently incorrect totals in testing).
- **SC-009**: After an investor deletes their account, 100% of their personal data, holdings, snapshots,
  and linked-account authorizations are erased and no longer retrievable.

## Assumptions

- **Read-only scope**: This feature only reads and analyzes data; moving money and placing trades are
  explicitly out of scope.
- **Single investor per portfolio**: The product targets an individual retail investor; multi-user,
  household sharing, and advisor/multi-client management are out of scope for this feature.
- **Account access via aggregation**: Linking uses a third-party account-aggregation capability; the
  specific provider is an implementation decision made during planning.
- **Single reporting currency**: Each investor has one reporting currency; all values are converted to it.
- **Authentication exists**: Each investor signs in to a personal, secured account before any financial
  data is shown; the exact authentication method is decided during planning.
- **Performance history is forward-only**: History begins when accounts are linked and accrues from
  recorded snapshots; no historical backfill from the provider is assumed for the MVP.
- **Refresh cadence**: A scheduled weekly snapshot runs on Tuesdays in addition to on-demand refresh;
  real-time intraday pricing is not assumed for the MVP.
- **Privacy-by-design**: Data export and account deletion (cascading erasure) and encryption-at-rest of
  personal data and credentials are in scope; broader formal certifications (e.g., SOC2, data
  residency) are out of scope for the MVP.
- **Benchmark comparison** (e.g., vs. a market index) is out of scope for this feature and may be a
  later enhancement.
