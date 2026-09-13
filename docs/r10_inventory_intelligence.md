# R10 — Inventory Intelligence

## Goal

Turn ERPNext stock truth into practical RetailEdge inventory decisions for owners and managers without creating a parallel stock ledger, valuation engine, forecasting ledger, or reorder system.

R10 is a stacked RetailEdge slice. It builds on R9 Business Control & Financial Intelligence and should reuse existing EdgeSuite report/dashboard shells, RetailEdge Stock Position and Stock Movement work, profitability intelligence, Action Centre follow-up, permissions, exports, and native drill-through conventions wherever those capabilities already exist.

## Stack

- Predecessor: R9 — Business Control & Financial Intelligence / `agent/business-control-financial-intelligence`
- R10 branch: `agent/inventory-intelligence`
- R10 branch point: exact R9 head `82ad16df126a42dbff5ac180544e26b99119b124`
- Keep the R10 PR Draft while implementation is in progress.
- Automated validation may run while predecessors remain stacked.
- Manual/browser QA must wait until predecessor QA/promotion reaches R10. Before R10 QA, reconcile against the promoted predecessor and require fresh exact-head automated validation.

## Business Outcomes

R10 should answer, quickly and safely:

1. What stock do we have and what is it worth?
2. What is running out or already out of stock?
3. What is overstocked or tying down working capital?
4. What is selling quickly and may need replenishment?
5. What is slow-moving or non-moving?
6. How many days of stock cover remain based on observed demand?
7. Which branches or warehouses have shortages while another location has excess?
8. Which inventory exceptions need action now?
9. Which high-margin or strategically important items are exposed to stockout risk?
10. Where should management investigate before purchasing, transferring, discounting, or writing off stock?

## ERPNext Truth and Safety

ERPNext remains authoritative for:

- Item
- Warehouse
- Bin
- Stock Ledger Entry
- submitted stock transactions
- stock valuation and valuation rates
- batch/serial truth where applicable
- Item Reorder / reorder configuration
- stock accounting and General Ledger effects

R10 must not:

- create a second stock ledger;
- recalculate or replace ERPNext valuation truth;
- mutate submitted Stock Entries, Purchase Receipts, Delivery Notes, Sales Invoices, Purchase Invoices, or other submitted documents;
- silently create stock transfers or purchase documents from intelligence suggestions;
- invent demand history where reliable history is unavailable;
- label heuristic or historical-velocity calculations as forecasts;
- bypass permissions with `ignore_permissions` in user-facing APIs;
- expose valuation/cost information to users who fail RetailEdge cost-visibility policy.

Suggested actions must remain suggestions until a user explicitly starts an ERPNext-safe workflow.

## R10 Capability Slices

### R10A — Inventory Foundation Audit and Shared Metrics

Audit and reuse existing RetailEdge implementations before adding new surfaces:

- Stock Position
- Stock Movement History
- existing stock dashboards/reports
- EdgeSuite report and dashboard shells
- R8 profitability intelligence
- R9 Business Control Centre patterns
- Action Centre and Action Follow Up
- branch/company/warehouse filtering
- cost visibility
- export/print
- native drill-through/new-tab contract

Define one shared, tested inventory-metric service rather than duplicating calculations across pages.

### R10B — Inventory Intelligence Centre

Create an owner/manager action surface with summary cards and prioritized exceptions rather than a passive ERP dashboard.

Candidate measures:

- stock quantity
- stock value, permission gated
- items in stock
- low-stock items
- out-of-stock items
- excess/overstock candidates
- slow-moving items
- non-moving items
- stockout-risk items
- working capital in ageing/slow inventory
- transfer opportunity count

All cards must drill into the filtered underlying dataset.

### R10C — Movement Velocity and Stock Cover

Use bounded historical movement/sales evidence to derive clearly labelled intelligence such as:

- units sold/issued over selected history window
- average daily movement
- days since last outward movement
- days since last stock movement
- stock cover in days
- fast/normal/slow/non-moving classification

The history window must be explicit and configurable. Do not present stock cover as a guaranteed future forecast.

### R10D — Inventory Ageing and Capital Lock-up

Provide configurable ageing bands such as 0–30, 31–60, 61–90, 91–180, and 180+ days where the underlying ERPNext evidence supports the calculation.

Show quantity and, only when authorized, value/capital tied up.

Document the exact ageing definition. Do not imply FIFO batch age if the calculation actually measures last movement or receipt age.

### R10E — Replenishment and Stockout Risk

Reuse ERPNext reorder configuration as authoritative configuration where available.

Enhance it with contextual intelligence such as:

- current projected quantity
- reorder level
- reorder quantity
- observed movement velocity
- estimated stock cover
- recent stockout frequency where safely derivable
- open inbound supply where reliably attributable

Do not create a competing reorder master.

### R10F — Branch/Warehouse Imbalance and Transfer Opportunities

Identify cases where an item is scarce in one valid branch/warehouse context while another has materially more stock.

Requirements:

- respect company and warehouse hierarchy;
- respect branch-to-warehouse configuration;
- never suggest cross-company stock transfer as though it were an ordinary internal transfer;
- exclude disabled/inappropriate warehouses;
- make thresholds configurable;
- suggestions must open a guided/native stock-transfer workflow rather than posting automatically.

### R10G — Profitability + Inventory Intelligence

Where R8 profitability evidence is available and permission-safe, combine it with inventory facts to highlight patterns such as:

- high-margin item with stockout risk
- high-sales item with insufficient cover
- low-margin item with excess stock
- high-value slow-moving stock
- profitable item unavailable in one branch but available elsewhere

Do not duplicate R8 profit definitions. Consume the established service/contract.

### R10H — Inventory Action Centre Integration

Feed actionable inventory exceptions into the existing Action Centre/follow-up model where appropriate.

Examples:

- critical stockout
- below reorder level
- excess stock
- non-moving high-value stock
- transfer opportunity
- high-margin stockout risk

Reuse acknowledgement, assignment, snooze and follow-up. Do not invent another task state machine and do not mark the underlying inventory condition resolved merely because a follow-up record is resolved.

## Smart Filters

All inventory surfaces should use context-aware filters and backend validation.

Expected cascade:

Company → Branch → Warehouse → Item Group → Item

Rules:

- warehouses must be valid for selected company/branch context;
- item selection should respect selected Item Group where applicable;
- changing a parent filter clears invalid dependent values;
- backend APIs must reject invalid combinations even if frontend filtering is bypassed;
- permissions must be applied at query/source level, not only by hiding UI rows;
- queries must be bounded and paginated where detail sets can grow materially.

## EdgeSuite UX Contract

R10 should use the shared EdgeSuite report/dashboard architecture rather than creating a one-off visual system.

Required conventions:

- consistent filters
- sortable tables
- pagination
- loading/empty/error states
- permission-aware metrics
- shared export and print where applicable
- clickable business documents/items
- guided RetailEdge entry/action when available
- any retained native ERPNext page opens in a new tab
- no competing native/EdgeSuite navigation chrome

## Performance

Avoid broad scans of Stock Ledger Entry on every page load.

Prefer:

- Bin for current stock position where valid;
- bounded date ranges for movement calculations;
- aggregate server-side queries;
- indexed filter paths;
- pagination for detail;
- cached/derived summaries only where invalidation and accounting correctness are explicit and tested.

Do not introduce persistent derived inventory truth unless a later audited slice demonstrates that live aggregation cannot meet acceptable performance.

## Permissions

At minimum test:

- System Manager / Administrator-equivalent management access
- stock manager/user roles
- branch-restricted users
- users without cost visibility
- users lacking access to particular warehouses/items

Cost/valuation fields must not merely be hidden after retrieval. Restricted APIs should avoid fetching/returning them.

## Tests Required

### Unit

- movement classification boundaries
- stock-cover calculations including zero movement
- reorder comparisons
- ageing-band boundaries
- transfer-opportunity thresholds
- profitability/inventory classification
- cost-visibility decisions

### Integration

- Bin/SLE consistency for supported scenarios
- company/branch/warehouse filtering
- ERPNext reorder configuration reuse
- Action Centre follow-up linkage
- R8 profitability contract reuse
- no submitted-document mutation
- permission-restricted results

### Migration

- clean Frappe/ERPNext/RetailEdge install
- upgrade from predecessor stack
- idempotent patches if any schema/configuration changes are required
- optional dependency absence where applicable

### Frontend / Browser

- cascading filters
- sorting
- pagination
- drill-through
- new-tab native links
- export/print
- empty/error/loading states
- restricted-cost UI
- responsive layout

Manual/browser QA is deferred until predecessor QA/promotion reaches R10.

## Implementation Order

1. Audit existing stock/report/dashboard/action/profitability code.
2. Define shared inventory metrics and exact business definitions.
3. Add backend metric/query tests first for safety-critical calculations.
4. Build Inventory Intelligence Centre.
5. Add velocity/stock-cover intelligence.
6. Add ageing/capital-lock-up intelligence.
7. Add replenishment/stockout risk.
8. Add branch/warehouse imbalance and transfer opportunities.
9. Integrate R8 profitability signals.
10. Integrate Action Centre follow-up.
11. Complete permission/performance/migration regression suite.
12. Reconcile against promoted predecessor before manual QA.

## Out of Scope for Initial R10

- autonomous purchasing
- autonomous stock transfers
- machine-learning demand forecasting
- supplier optimization that belongs in a later procurement intelligence slice
- replacement of ERPNext Stock Balance/Stock Ledger truth
- new inventory accounting or valuation methods
- automatic write-off of dead stock

## Definition of Done

R10 is complete when RetailEdge can turn ERPNext inventory truth into fast, permission-safe, actionable inventory intelligence without compromising stock/accounting integrity, duplicating existing EdgeSuite/RetailEdge capabilities, or creating a parallel operational truth.