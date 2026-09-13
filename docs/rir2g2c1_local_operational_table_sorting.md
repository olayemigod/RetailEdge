# RIR2G2C1 — Local Operational Table Sorting

## Goal

Make RetailEdge-owned raw operational tables sortable without creating misleading page-local sorting for server-paginated datasets.

This checkpoint does not modify shared EdgeSuite UI report components or EdgeReportShell-backed report providers. Those remain RIR2G2C2 because their governed provider runtime requires server sorting.

## Governed shared finding

EdgeSuite UI 1.1.0 commit `e40ea4d7dc000d17443a0571c1e246b61bfd3e1d` already provides:

- sortable `EdgeReportTable` headers;
- `sort-change` emission;
- provider `sort` normalization;
- server sorting strategy for paginated providers.

RetailEdge EdgeReportShell consumers currently do not wire that contract. They are not patched in C1.

## Scope

C1 owns three RetailEdge-local raw table areas:

1. Business Expenses queue;
2. Payment Management raw tables;
3. Professional Purchasing direct Purchase Invoice draft queue.

## Business Expenses — server-paginated sorting

Business Expenses is paginated on the server. Sorting only the currently loaded page is prohibited.

### Backend

`get_business_expenses` may accept an optional sort payload.

Allowed fields only:

- `expense_date`
- `expense_category`
- `payee_name`
- `branch`
- `expense_status`
- `ledger_status`
- `amount`
- `modified`
- `name`

Allowed directions only: `asc`, `desc`.

Unknown field/direction must fail closed to the existing default order, not be interpolated.

Default order remains:

`expense_date desc, modified desc, name desc`

A user-selected sort must use a stable server order with deterministic tie-breaks. No raw browser string may become SQL/order_by syntax.

The response should echo the normalized sort (or null/default) so UI state can remain authoritative.

### UI

- Date, Expense, Payee, Branch, Status, Ledger and Amount headers are sortable.
- action/row-click behavior remains unchanged.
- sort cycles: unsorted/default → ascending → descending → default.
- changing sort resets to page 1 and reloads from the server.
- pagination and filters remain unchanged.

## Payment Management — bounded in-memory sorting

The existing Payment Management datasets are bounded operational payloads and may be sorted client-side without changing accounting truth.

Tables:

1. Draft Payments Awaiting Submission;
2. Mixed Settlement eligible advances;
3. Customer Advances.

Requirements:

- preserve server order until a user selects a sort;
- deterministic ascending/descending/local default cycle;
- numeric values sort numerically;
- ISO date values sort chronologically;
- text sorts case-insensitively with numeric awareness;
- empty values sort last;
- action/editable allocation columns are not sortable;
- sorting eligible advances must not alter allocation values or Payment Entry identity.

## Professional Purchasing direct Purchase Invoice queue

The G2B direct Purchase Invoice queue is bounded to 20 rows in the UI.

- preserve server `modified desc` ordering by default;
- sortable columns: Purchase Invoice, Date, Supplier, Branch, Mode, Total;
- Action is not sortable;
- local sorting is limited to the explicitly bounded current queue and does not alter completion eligibility or server truth;
- completion refresh retains current sort state while sorting the new returned rows.

## Safety

C1 must not:

- change ERPNext permissions;
- change payment/purchase/expense workflow or posting;
- mutate documents while sorting;
- introduce `ignore_permissions`;
- manually commit;
- interpolate untrusted order_by values;
- change shared EdgeSuite UI runtime;
- alter EdgeReportShell report providers.

## Tests Required

1. Business Expense sort field allowlist exists.
2. Business Expense directions are only asc/desc.
3. invalid sort falls back to exact historical default.
4. valid sort produces deterministic allowlisted order_by.
5. Business Expense UI sends sort to backend and resets to page 1.
6. all visible Business Expense data headers are sortable; no action column is introduced.
7. Payment Management owns separate sort state for draft payments, settlement advances and customer advances.
8. each Payment Management table renders sorted computed rows.
9. numeric/date/text comparison is deterministic and empty-last.
10. settlement Apply column remains non-sortable and allocation map remains identity-keyed.
11. Professional Purchasing owns bounded draft-invoice sort state and computed sorted rows.
12. its Action column remains non-sortable.
13. default state preserves backend order.
14. no accounting/stock/workflow mutation is introduced.
15. existing G2B purchase completion and G2A native containment remain intact.

## Out of Scope

- EdgeReportShell-backed report sorting;
- shared EdgeSuite UI changes;
- Business Hub redesign;
- report expansion;
- table virtualization;
- new backend indexes;
- browser/persona QA.

## Freeze Rule

Freeze only when Theme, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
