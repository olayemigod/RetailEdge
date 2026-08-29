# R10A — Inventory Intelligence Foundation Audit

## Outcome

RetailEdge already contains the core stock, branch, cost-visibility, profitability, guided-transfer, EdgeSuite reporting, Action Centre, and follow-up contracts needed for R10. R10 should therefore be an intelligence/composition layer over these existing sources rather than a replacement stock subsystem.

No new DocType, ledger, valuation engine, reorder master, or migration is required for the R10A foundation.

## Existing Sources to Reuse

### Current stock position

Canonical RetailEdge source: `retailedge/stock_position.py`.

Reuse decisions:

- `Bin` remains the source for current stock position.
- Existing Company/Branch/Warehouse scope resolution remains authoritative for R10 current-position queries.
- Existing hard bounds remain the baseline: warehouse, Bin scan, item scope, Link results, and pagination limits.
- Existing stock status semantics — Negative, Out of Stock, Fully Reserved, Available — must not be redefined differently inside R10.
- Existing Item Group and Item filtering should be extended/reused rather than rebuilt.
- Existing cost gating is mandatory: valuation fields are added to the Bin query only when `should_hide_cost_price()` permits them.

R10 may introduce a shared internal current-position adapter, but it should delegate to/refactor the existing implementation rather than maintain a second aggregation formula.

### Historical stock movement

Canonical operational report: `RetailEdge Stock Movement History`.

Reuse decisions:

- Preserve its ERPNext `Stock Ledger Entry` semantics, opening balance handling, Stock Reconciliation handling, internal transfer interpretation, UOM conversion, and branch/warehouse validation.
- Do not use its unrestricted `limit_page_length=0` single-item history fetch as the backend for broad Inventory Intelligence scans.
- R10 historical intelligence requires a separate bounded aggregate/read service that shares the same movement semantics while enforcing explicit lookback dates, item/warehouse scope limits, and server-side aggregation.
- Internal transfers must not be counted as customer demand merely because they are outward movements from one warehouse.

### Branch and warehouse scope

Canonical sources:

- `retailedge/branch_context.py`
- `retailedge/stock_movement_filters.py`
- `get_branch_warehouses()` from Stock Movement History
- RetailEdge Branch Profile defaults where direct Warehouse→Branch attribution is unavailable.

Reuse decisions:

- Company → Branch → Warehouse is one security/scope contract across R10.
- Branch-restricted users must never gain company-wide scope from a blank Branch selection.
- Link queries remain bounded and permission-aware.
- Parent-filter changes must clear invalid child selections in the UI and the backend must reject invalid combinations.

### Cost visibility

Canonical source: `retailedge/cost_visibility.py`.

Reuse decisions:

- `should_hide_cost_price()` remains the only RetailEdge policy switch for R10 cost/valuation visibility.
- Hidden users must not receive stock value, valuation rate, capital-lock-up value, margin, or other cost-derived fields.
- Restricted fields must be excluded before database retrieval where possible, not merely hidden in Vue.
- Cost-hidden users should still receive quantity-, availability-, velocity-, cover-, reorder-, and transfer-oriented intelligence where those fields are otherwise permitted.

### Profitability

Canonical source: `retailedge/profitability_intelligence.py`.

Reuse decisions:

- R10G must consume the established item-level profitability result rather than recalculate RetailEdge margin.
- R8 already defines transactional net sales, recorded item cost, gross profit, and margin and separately reconciles to ERPNext accounting profit truth.
- Profitability integration is unavailable to cost-hidden users; R10 must degrade safely rather than fail all inventory intelligence.
- R10 must preserve the distinction between accounting profitability and transactional item-cost intelligence.

### Inventory action management

Canonical sources:

- `retailedge/action_center.py`
- `retailedge/business_control_center.py`
- `retailedge/action_follow_up.py`

Reuse decisions:

- Existing Negative Stock, Out of Stock, and Fully Reserved exceptions remain owned by the current Stock Position→Action Centre source. R10 must not duplicate them with different fingerprints or wording.
- Action Centre remains the canonical operational scope resolver.
- Business Control Centre demonstrates the correct composition pattern: consume existing Action Centre items, add only new non-duplicate domains, isolate unavailable sources, then decorate through the single Action Follow Up store.
- R10 follow-up capable exceptions must be visible through the Business Control/Action Centre composition path so `update_action_follow_up()` can re-resolve the fingerprint before persistence.
- Acknowledgement/snooze/assignment/follow-up state never resolves or changes the underlying inventory condition.

### Stock transfer execution

Canonical source: `retailedge/guided_stock_transfer.py`.

Reuse decisions:

- Transfer opportunities are advisory only.
- When a user chooses to act, R10 should prefill/open the existing Simple Stock Transfer workflow where supported.
- That workflow creates an ERPNext `Stock Entry` Material Transfer draft as the current user and never submits automatically.
- Source and target warehouses must be different, permission-valid, and in the same Company.
- Serial- or batch-managed items continue to fall back to the full native ERPNext Stock Entry form.
- R10 must never treat a cross-company movement as a normal internal transfer suggestion.

### EdgeSuite reporting UX

Canonical patterns already exist in Stock Position and R8/R9 pages.

Reuse decisions:

- Use the shared EdgeSuite report/dashboard shells.
- Use `EdgeLinkField` and shared smart query endpoints for cascades.
- Use the shared report provider/export contract rather than custom Blob/CSV generation.
- Preserve sortable tables, pagination, responsive filter grids, loading/empty/error states, and hidden native sidebar behavior.
- Guided RetailEdge workflows remain same-tab experiences; retained native ERPNext reports/forms should open in a new tab where applicable.

## R10 Metric Definitions

These definitions are the contract for the first implementation. Thresholds are inputs/configuration, not hidden magic constants.

### Current quantity

`actual_qty` = ERPNext `Bin.actual_qty` summed only across the validated warehouse scope.

### Reserved quantity

`reserved_qty` = ERPNext `Bin.reserved_qty` summed across the same validated scope.

### Available quantity

`available_qty = actual_qty - reserved_qty`.

This deliberately matches the existing RetailEdge Stock Position definition.

### Projected quantity

`projected_qty` = ERPNext `Bin.projected_qty` aggregated across the validated scope.

UI wording must say ERPNext Projected Qty or equivalent. It must not be presented as a RetailEdge demand forecast.

### Demand quantity

R10 distinguishes demand from generic stock movement.

For the first demand model:

- count only validated outward movements that represent external/customer consumption under the agreed ERPNext voucher semantics;
- exclude internal Material Transfer source-side movement;
- exclude cancellation/reversal noise according to ERPNext SLE truth;
- keep the selected lookback window explicit.

If the broad SLE query cannot distinguish a voucher safely, classify it as other outward movement instead of silently treating it as demand.

### Average daily demand

`average_daily_demand = demand_qty / lookback_days`, where `lookback_days > 0`.

This is historical observed demand, not a forecast.

### Stock cover

`stock_cover_days = max(available_qty, 0) / average_daily_demand` when average daily demand is greater than zero.

Rules:

- demand <= 0 → no calculable cover (`None` / Not Available), not infinite stock cover;
- available <= 0 with positive demand → 0 days cover;
- label as Estimated Cover from Historical Demand.

### Movement classification

Fast/Normal/Slow/Non-moving classifications must be based on explicit configuration passed into the classifier. R10A will not hide fixed 30/60/90/180-day assumptions inside helper code.

At minimum the classifier should consider:

- demand in the selected lookback;
- days since last demand event;
- configured slow/non-moving thresholds.

Internal transfer activity alone must not make an otherwise non-selling item look fast-moving.

### Inventory ageing

R10 must not label “days since last movement” as FIFO stock age.

Initial safe fields may include:

- days since last demand;
- days since last receipt;
- days since any stock movement.

Value-based ageing bands should not be implemented until the ERPNext v16 Stock Ageing source/algorithm is inspected and either safely reused or matched. This is a deliberate accounting/valuation safety gate for R10D.

### Reorder signal

ERPNext reorder configuration remains authoritative.

R10 should compare validated current/projected quantity to the installed ERPNext v16 Item/Warehouse reorder configuration and expose context such as:

- reorder level;
- reorder quantity;
- projected quantity;
- quantity below level;
- historical demand/cover.

The repository contains no RetailEdge-specific reorder schema. Before coding R10E, inspect the installed ERPNext v16 Item reorder child metadata/controller and do not hard-code a guessed field/table contract.

### Transfer opportunity

A transfer opportunity is an advisory pairing where:

- source and target are permission-valid non-group warehouses in the same Company;
- target is below its configured/protected stock threshold;
- source remains above its protected threshold after the proposed quantity;
- the suggested quantity is bounded by both target shortfall and source surplus;
- no automatic Stock Entry is created.

The exact source-surplus/target-shortfall thresholds remain explicit configuration/inputs.

### Profitability + inventory signal

R10 may combine inventory state with R8 item rows for users allowed to see cost/profit data. Examples include high-margin stockout risk and high-value slow stock.

R10 must consume R8 margin values as-is and must not create a competing profit formula.

## Query and Performance Contract

### Current position

Use Bin through the existing bounded Stock Position source.

### Historical movement

Implement a new internal aggregate source with all of the following:

- required Company;
- validated Branch/Warehouse scope;
- explicit bounded date/lookback range;
- bounded item and warehouse scope;
- server-side aggregation where practical;
- an explicit hard row/aggregate limit and safe validation error when exceeded;
- no `ignore_permissions=True`;
- no unbounded `limit_page_length=0` broad multi-item scans.

The user-facing detailed Stock Movement History report remains available for item/warehouse drill-through and should not be rewritten merely to serve R10.

## Permission Contract

R10 must test at least:

- Administrator/System Manager;
- RetailEdge/Stock management roles;
- branch-restricted users;
- users without cost visibility;
- users without access to one of the candidate transfer warehouses;
- users without owner-level profitability capability.

Blank Branch handling must remain fail-closed for branch-restricted multi-branch users wherever an aggregate surface could otherwise widen scope.

## Follow-up Integration Decision

Do not create an `Inventory Follow Up` DocType.

New R10 exception families should be composed into the existing Business Control/Action Centre item stream, then decorated by `RetailEdge Action Follow Up`.

Before R10H implementation, extend the re-resolution tests so an R10 fingerprint cannot be acknowledged/assigned after it leaves the current user's permission-aware inventory scope.

## Migration and Backward Compatibility

R10A requires no schema patch and no migration.

Existing pages/reports remain valid:

- Stock Position remains the current position detail surface.
- RetailEdge Stock Movement History remains the detailed movement/audit surface.
- Simple Stock Transfer remains the transfer execution path.
- Action Centre/Business Control remain the management exception/follow-up surfaces.
- Profitability Intelligence remains the R8 source for item profitability.

R10 will add intelligence around these contracts without replacing them.

## First Implementation Sequence

1. Add pure, tested shared metric helpers for average daily demand, stock cover, threshold classification, reorder comparison, and transfer quantity calculation.
2. Add a permission-aware inventory scope adapter that reuses Stock Position/branch contracts instead of duplicating them.
3. Implement bounded historical demand aggregation with internal transfers excluded from demand.
4. Build the R10 Inventory Intelligence backend dataset and summary contracts.
5. Build the EdgeSuite Inventory Intelligence Centre page on the existing report/dashboard shell.
6. Add R10 exception composition without duplicating Negative/Out-of-Stock/Fully-Reserved Action Centre signals.
7. Only then add ERPNext-reorder integration after inspecting the installed v16 schema.
8. Gate true/value-based ageing on confirmed ERPNext Stock Ageing semantics.
9. Add profitability composition for permitted users.
10. Add guided transfer prefill/drill-through.

## Tests Required Before R10B UI

- pure metric boundary tests;
- zero-demand and zero/negative-availability cover tests;
- transfer source-surplus preservation tests;
- internal-transfer-excluded-from-demand tests;
- branch-restricted blank-scope fail-closed tests;
- cost-hidden response contains no cost/value/margin fields;
- hard scan-limit tests;
- Action Centre duplicate prevention tests;
- follow-up fingerprint re-resolution tests;
- Guided Stock Transfer remains draft-only and same-company.

## R10A Decision

Proceed with shared metric helpers and their tests next. Do not create new persistence, UI, or migration until those definitions are covered by tests.