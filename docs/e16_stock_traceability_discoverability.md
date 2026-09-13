# E16 C14A — Batch & Serial Traceability Discoverability

## Goal

Close a genuine RetailEdge stock-operations discoverability gap for businesses that manage expiry-sensitive, batch-controlled, warranty-tracked, or individually serialized inventory, while leaving ERPNext as the sole stock and traceability authority.

## Audit result

RetailEdge already exposes Products, Stock Locations, Stock Movement History, Stock Position, Stock Balance, Stock Transfers, Stock Count, Reorder Requests, Stock Ledger, Projected Stock and Stock Ageing.

ERPNext v16 already owns the traceability lifecycle:

- `Batch` stores batch identity, item, manufacturing date, expiry date, current batch quantity, supplier/source evidence and batch-wise valuation state. The native Batch form also owns stock-level display, Stock Ledger drill-through, batch movement and batch splitting.
- `Serial No` stores serial identity, item, batch, warehouse, status, customer, company, warranty/AMC state and source-document evidence.
- buying, selling, stock movement, Stock Ledger and Serial and Batch Bundle remain ERPNext stock truth.

Therefore RetailEdge must not create another batch/serial ledger, expiry state, movement engine or serialized-stock workflow.

## Scope

Add two native DocType destinations to the existing `Stock` EdgeSuite navigation group:

1. **Batches** → ERPNext `Batch`
2. **Serial Numbers** → ERPNext `Serial No`

Place them after `Stock Locations` and before RetailEdge stock reports so operational traceability sits beside the Item/Warehouse masters that govern it.

The existing `_can_open_target` DocType path must remain the visibility authority, so each link appears only when the current user has native ERPNext `read` permission for that DocType.

## Explicitly out of scope

- no RetailEdge Batch or Serial Number DocType;
- no custom expiry ledger, serial ledger, stock valuation or quantity reconstruction;
- no RetailEdge wrapper around batch Move/Split/Recalculate actions;
- no direct Stock Ledger Entry or Serial and Batch Bundle writes;
- no submission/cancellation wrapper;
- no `ignore_permissions` or manual commit;
- no custom batch/serial creation dialog;
- no duplicate batch-expiry or available-serial report in this slice;
- do not expose the internal `Serial and Batch Bundle` DocType as a business navigation destination.

## Report navigation boundary

ERPNext v16 already contains native reports such as `Batch Item Expiry Status`, `Available Batch Report` and `Available Serial No`.

RetailEdge's current generic navigation resolver checks Report/Page target existence but does not independently enforce the report's role list before returning navigation metadata. C14A must not widen scope by changing that global resolver or add new report links that could be visible before Frappe performs its native route-level permission check.

A later bounded audit may harden generic Report navigation permission handling first, then decide whether these reports should be promoted.

## Safety rules

- ERPNext remains source of truth for stock, batches, serials, expiry dates, warehouses and valuation.
- Reuse the existing `NAVIGATION_GROUPS` and `_can_open_target` permission-aware DocType path.
- Do not add hard-coded RetailEdge role gates that are broader than native DocType permission.
- Preserve multi-app coexistence and neutral user-facing labels.
- Do not alter existing Stock navigation targets or their order except for inserting the two approved traceability links.
- Manual QA remains deferred until cumulative implementation is reconciled into the consolidated QA branch.

## Tests required

Focused source-contract tests must prove:

- `Batches` and `Serial Numbers` exist exactly once in the Stock navigation group and target native `Batch` / `Serial No` DocTypes;
- both use the existing DocType read-permission path;
- neither appears in another business group;
- `Serial and Batch Bundle` is not exposed;
- RetailEdge adds no Batch/Serial creation/posting wrapper, stock-ledger write, permission bypass or manual commit for this slice;
- the approved Stock navigation order is preserved.

## Expected delivery boundary

C14A is complete when the two native destinations are discoverable through permission-aware EdgeSuite navigation, focused tests pass, cumulative diff is bounded, and exact-head Theme/Linters/clean Frappe v16 CI/EdgeSuite candidate validation is green.
