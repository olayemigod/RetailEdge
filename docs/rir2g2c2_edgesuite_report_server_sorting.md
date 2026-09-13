# RIR2G2C2 — EdgeReportShell Server Sorting Propagation

## Goal

Complete the governed EdgeSuite report sorting contract across RetailEdge EdgeReportShell consumers without changing the shared EdgeSuite UI runtime or sorting only the currently visible page.

## Evidence

The governed EdgeSuite UI 1.1.0 candidate at `e40ea4d7dc000d17443a0571c1e246b61bfd3e1d` already provides:

- sortable EdgeReportTable headers;
- EdgeReportShell `sort` state and `sort-change` events;
- normalized `{field, direction}` sort payloads;
- `sorting_strategy = "server"` for paginated and bounded-paginated providers;
- provider forwarding of normalized sort into `loadPage`.

RetailEdge report consumers currently call provider `.load()` without sort, and provider adapters call backend endpoints without sort.

## Scope

C2 covers the existing EdgeReportShell operational reports:

- Cash Flow Outlook;
- Cash Movement;
- Cash Shift Verification;
- Customer Receivables;
- Daily Sales Audit;
- Expense Register;
- Expense Review;
- Purchase Register;
- Supplier Payables;
- Sales by Item;
- Sales Invoice Register;
- Stock & Accounting Integrity;
- Stock Position.

## Consumer contract

Each report page must:

1. own explicit report sort state;
2. pass it to EdgeReportShell;
3. handle `sort-change`;
4. reset to page 1 when sort changes;
5. pass sort to provider `.load()`;
6. accept normalized sort echoed by the provider/backend;
7. preserve historical backend order when no sort is selected.

No report may sort only its visible page.

## Provider contract

Each RetailEdge paginated/bounded provider adapter must accept the governed `sort` argument from EdgeSuite UI and forward it to its backend endpoint.

Provider adapters must not trust or interpolate raw field/direction values. Backend allowlists remain authoritative.

## Backend contract

Every endpoint must use an explicit report-specific allowlist.

- Directions: `asc` and `desc` only.
- Unknown fields or directions preserve the historical default order.
- Materialized bounded datasets may be sorted only after permission/company/branch filtering and before pagination.
- Query-level datasets must apply allowlisted ordering in the query/get_list before pagination.
- Stable tie-breaking must be deterministic where the underlying query requires it.
- The response echoes normalized sort or null.

Enrichment-only/action fields that are not stable backend data fields must be marked non-sortable or excluded from the backend allowlist.

## Safety

C2 must not:

- modify shared EdgeSuite UI runtime;
- change ERPNext permissions, roles, workflows or document lifecycle;
- alter accounting, GL, Payment Ledger, Stock Ledger or valuation truth;
- change Branch-scope semantics;
- introduce `ignore_permissions`;
- add manual DB commits;
- interpolate browser-provided order strings;
- expand report datasets or reporting scope.

## Tests Required

1. shared report sort helper rejects unknown fields/directions;
2. materialized sorting is stable, typed and empty-last;
3. every C2 provider adapter accepts and forwards `sort`;
4. every C2 EdgeReportShell consumer binds sort and handles `sort-change`;
5. sort change resets pagination before reload;
6. each backend endpoint declares/uses an explicit allowlist;
7. Cash Movement query sorting occurs before SQL LIMIT/OFFSET;
8. Expense Register query sorting occurs before get_list pagination;
9. bounded materialized reports sort before _page_response;
10. action/enrichment-only columns cannot produce unsupported backend sort;
11. historical no-sort ordering remains unchanged;
12. G2C1 local sorting, G2B purchase completion and G2A native containment remain intact.

## Out of Scope

- new report features or columns;
- new indexes;
- table virtualization;
- shared EdgeSuite UI changes;
- browser/persona QA;
- export-order redesign beyond preserving current export behaviour.

## Freeze Rule

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI, and EdgeSuite UI Candidate Compatibility all pass on one exact head.
