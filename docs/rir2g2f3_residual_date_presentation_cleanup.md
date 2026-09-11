# RIR2G2F3 — Residual Date Presentation Cleanup

## Goal

Close the remaining confirmed raw date-display leaks found by the repository-wide RetailEdge Vue audit after G2F1 and G2F2.

## Scope

Only these eight components are in scope:

1. Cash Flow Outlook — visible As-of date.
2. Customer Receivables — visible ageing/balance date.
3. Expense Overview — MTD/YTD ranges, period anchor description and recent expense dates.
4. Professional Purchasing RFQ Preview — item schedule date.
5. Professional Sales Invoice — Loyalty Programme validity dates.
6. Purchase Reporting — Supplier Payables as-of/ageing dates.
7. Business Hub Simple Payment — customer and supplier review posting dates.
8. Stock & Accounting Integrity — visible scope range.

## Required behavior

- User-visible Date values use Frappe user-date formatting.
- Raw ISO values remain unchanged for HTML date inputs, API/filter payloads, sorting, row keys and persistence.
- Existing Datetime presentation remains unchanged.
- Empty/optional dates preserve the existing contextual fallback text.
- No backend API or report calculation changes are required.

## Safety rules

- No accounting, stock, valuation, payment, workflow or posting semantics change.
- No date arithmetic, period boundaries or timezone behavior change.
- No permission or Branch-scope change.
- No backend API/schema change.
- No shared EdgeSuite UI runtime change.
- No submitted-document mutation.
- No `ignore_permissions` or manual database commits.
- Do not reopen frozen G2A–G2F2 contracts.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests required

- every scoped raw-date presentation location is replaced with a Frappe-backed formatter;
- native `type="date"` controls retain ISO values;
- backend/API/filter references remain unchanged;
- existing G2F1/G2F2 contracts remain green.

## Freeze rule

Freeze only when Theme, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.