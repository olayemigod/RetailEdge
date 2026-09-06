# E16 C22 — Stock & Accounting Integrity Review

## Goal

Give RetailEdge accounting and stock-control users an EdgeSuite review surface for ERPNext stock-versus-accounting mismatches without creating a second valuation or reconciliation engine.

C22 is an **exception review and investigation** capability. ERPNext remains the authority for Stock Ledger Entry, GL Entry, stock valuation, perpetual inventory, reposting, and corrective accounting/stock workflows.

## Authoritative ERPNext source

C22 must delegate mismatch calculation to ERPNext v16 `Stock and Account Value Comparison` (`erpnext.stock.report.stock_and_account_value_comparison.stock_and_account_value_comparison`). RetailEdge must not independently reproduce or reinterpret the SLE-versus-GL formula.

The current ERPNext v16 report:

- requires perpetual inventory for the Company;
- compares voucher-level Stock Ledger Entry `stock_value_difference` with stock-account GL debit-minus-credit values;
- reports only mismatches above ERPNext's own tolerance;
- supports Company, optional Stock Account, `as_on_date`, and an upstream-supported optional `from_date` lower bound;
- can identify both stock-ledger vouchers without matching account value and GL stock-account vouchers without matching Stock Ledger Entry.

## Business semantics

The review is **Company-level accounting control**, not Branch accounting.

A stock voucher can affect warehouses or accounts spanning more than one Branch. RetailEdge must not label or filter a voucher-level SLE-versus-GL difference as Branch-specific unless ERPNext provides an authoritative branch-safe reconciliation source. C22 therefore:

- does not expose a Branch filter;
- does not split or allocate differences by Branch;
- allows Company-wide review only where the user is permitted to see the whole Company scope;
- fails closed for branch-restricted users in a multi-branch Company rather than leaking company-wide values or presenting a misleading partial reconciliation.

For a Company with zero or one configured Branch, the Company-wide review may remain available when all other permission gates pass.

## C22 first-slice scope

### EdgeSuite Stock & Accounting Integrity page

Provide a dedicated EdgeSuite page, separate from Stock Position. Stock Position remains operational item/quantity/replenishment truth; C22 is an accounting-control exception surface.

Filters:

- Company — required and permission-aware;
- From Date — required for the EdgeSuite operational review;
- As On Date — required;
- Stock Account — optional, limited to Stock accounts belonging to the selected Company.

The review window must be server-validated and bounded. The first slice should permit at most 366 days per request. Users needing broader historical investigation retain the native ERPNext report as the advanced fallback.

### Rows

Preserve ERPNext-owned row semantics and values:

- Ledger ID / ledger type;
- Posting Date;
- Posting Time;
- Voucher Type;
- Voucher No;
- Stock Value;
- Account Value;
- Difference Value.

Do not calculate alternative stock value, account value, or difference in RetailEdge.

Voucher and ledger identifiers should remain clickable where the current user can open the authoritative document.

### Summary

RetailEdge may aggregate the already-returned ERPNext mismatch rows into display-only summary cards, including:

- Mismatched Vouchers;
- Absolute Difference;
- Net Difference;
- Stock-ledger-led exceptions;
- GL-led exceptions.

These summaries must not be presented as ledger balances or correction amounts. They are review summaries over the bounded mismatch result set.

### Pagination and export

- Present rows through the shared bounded EdgeSuite report provider.
- Page size must remain bounded.
- Cap returned mismatch rows; if the cap is exceeded, fail with a clear instruction to narrow the date/account scope instead of silently truncating accounting exceptions.
- Governed export must use the exact same server-built mismatch dataset and permission checks as the page.

## Permissions

C22 must enforce all of the following server-side:

1. authenticated user;
2. readable selected Company;
3. native ERPNext permission to open `Stock and Account Value Comparison`, using Frappe's query-report permission resolution rather than a browser-only role check;
4. Company-wide branch scope as defined above;
5. selected Account, when present, exists, is readable, belongs to the selected Company, and is a Stock account;
6. normal RetailEdge report export capability for export actions.

Navigation should be role-aware, but navigation visibility is not the security boundary. Backend validation remains authoritative.

## Native ERPNext advanced fallback

C22 may provide a clearly labelled route to the native `Stock and Account Value Comparison` report for users who already have permission to open it.

RetailEdge must not copy the native report's `Create Reposting Entries` action into the EdgeSuite first slice.

## Explicitly out of scope for C22 first slice

- calling ERPNext `create_reposting_entries`;
- creating, inserting, submitting, cancelling, or running `Repost Item Valuation`;
- automatic Stock Reconciliation;
- automatic Journal Entry;
- direct GL Entry writes;
- direct Stock Ledger Entry writes;
- changing submitted Purchase Receipt, Purchase Invoice, Stock Entry, Delivery Note, Sales Invoice, or other stock/accounting vouchers;
- automatic valuation-rate correction;
- branch-level allocation of SLE/GL differences;
- a parallel valuation ledger, inventory ledger, reconciliation table, or exception DocType;
- scheduled automatic correction.

ERPNext v16's native report can create and submit reposting documents. That behaviour remains an advanced native ERPNext workflow and is deliberately not invoked by RetailEdge C22.

## UI rules

- Use EdgeSuite UI (`EdgeAppShell` + shared report components).
- No `frappe.ui.Dialog`, `frappe.prompt`, `frappe.msgprint`, or classic parallel report page for the RetailEdge surface.
- Show a clear note that mismatches are ERPNext stock/accounting exceptions and that the EdgeSuite page is read-only.
- Do not expose RetailEdge/ProcessEdge branding inside accounting document truth or correction workflows.

## Implementation targets

Expected implementation areas:

- new `retailedge/stock_accounting_integrity.py` read adapter;
- new EdgeSuite page and bundle/component for `stock-accounting-integrity`;
- `retailedge/reporting_capabilities.py` capability registration;
- `retailedge/reporting_actions.py` governed export registration;
- `retailedge/edgesuite_ui.py` role-aware navigation;
- focused C22 tests for delegation, permissions, company-wide scope, bounds, export parity, UI contract, and write-path prohibition.

No custom schema/DocType or data patch is expected. Standard Page metadata requires normal `bench migrate` during deployment.

## Tests required

### Unit / contract

- Company is required and must be readable.
- From Date and As On Date are required; From Date cannot be after As On Date.
- Review window over 366 days is rejected.
- branch-restricted user in a multi-branch Company is rejected.
- single-branch Company may pass the company-wide branch-scope gate.
- optional Account must be a Stock account in the selected Company.
- native query-report permission is required.
- native ERPNext comparison function is called with the validated filters.
- RetailEdge preserves ERPNext row stock/account/difference values without recalculation.
- mismatch-result cap fails closed rather than truncating.
- summary derives only from returned mismatch rows.
- export uses the same dataset path.

### Safety/static

C22 source must not call or contain a write path for:

- `create_reposting_entries`;
- `Repost Item Valuation` creation/submission;
- `Stock Reconciliation` creation/submission;
- `Journal Entry` creation/submission;
- direct GL Entry writes;
- direct Stock Ledger Entry writes;
- `.insert(`, `.submit(`, `ignore_permissions=True`, or manual database commit in the C22 adapter.

### UI

- EdgeSuite runtime/components are required.
- Company/Account selectors cascade correctly; changing Company clears an invalid Account.
- date filters are applied server-side.
- voucher/ledger links use authoritative Frappe routes.
- native ERPNext report fallback is visible only when authorised.
- no classic dialog/prompt/msgprint dependency.
- governed export remains available only when authorised.

## Production gates

Freeze the exact implementation head only after:

1. RetailEdge Theme Compatibility passes;
2. duplicate Linters pass, including pre-commit, Semgrep, and vulnerable dependency audit;
3. duplicate clean Frappe v16 CI passes, including fresh install/migrate/build/full RetailEdge tests;
4. duplicate governed EdgeSuite UI candidate compatibility passes.

Manual/browser QA remains deferred to the cumulative RetailEdge reconciliation branch after implementation is complete.

## Things not to change

- Do not alter C21 replenishment semantics or Material Request handoff.
- Do not change ERPNext stock/accounting formulas.
- Do not weaken existing Company/Branch permissions.
- Do not modify submitted accounting or stock documents.
- Do not introduce a new E16 PR or branch.
- Do not implement automatic reposting merely because ERPNext exposes that action in its native report.
