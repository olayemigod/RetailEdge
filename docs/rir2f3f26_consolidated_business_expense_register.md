# RIR2F3F26 — Consolidated Business Expense Register

## Goal

Make Expense Register useful to owners, managers and finance/control roles as a consolidated view of business spending, not only Cashier/POS counter expenses.

RetailEdge must still preserve the source document and ERPNext General Ledger as accounting truth. The register is a read model only.

## Business Contract

Privileged RetailEdge/finance readers receive **Consolidated business expenses** as the default Expense Register view.

The consolidated dataset combines:

1. RetailEdge Cashier Expense records, including their existing draft/review/posting states.
2. Posted expense-account General Ledger lines whose source voucher is:
   - Purchase Invoice — Supplier / Business;
   - Expense Claim — Employee Expense, when that DocType is installed;
   - Journal Entry — Accounting Adjustment.

The accounting query deliberately excludes Sales Invoice, POS Invoice, Delivery Note, Stock Entry and other vouchers that would pull COGS, stock valuation or unrelated accounting movement into operational expense viewing.

No duplicate expense ledger is created.

## Double-count Protection

If a RetailEdge Cashier Expense already points to an accounting posting through its `posting_reference_type` and `posting_reference`, matching GL rows are excluded from the accounting half of the consolidated dataset.

The Cashier Expense remains the operational source row; its accounting document remains the ledger source of truth.

## Branch Safety

The existing operational Branch scope remains authoritative.

- Restricted readers see only their permitted Branch union.
- Explicit unauthorised Branch filters fail closed.
- Accounting rows use supported source-voucher `retailedge_branch` attribution.
- If an accounting source has no safely attributed Branch, it cannot match a restricted Branch predicate.
- Unrestricted owners/managers using blank Branch retain company-wide visibility, including unattributed accounting adjustments.
- Therefore unattributed accounting rows are company-wide only.

This follows the same fail-closed principle already used by Cash Movement.

## Frontline Compatibility

Cashier-only users keep the existing self-scoped Cashier Expense view.

They are not granted the consolidated GL-derived view merely because the Expense Register Page is accessible.

The consolidated view is explicitly role-gated and must also pass Company and Branch access rules.

## UI

Eligible users receive two modes:

- Consolidated business expenses;
- Cashier / POS expenses only.

The consolidated mode also exposes a Source filter:

- Cashier / POS;
- Supplier / Business;
- Employee Expense;
- Accounting Adjustment.

Rows show Date, Branch, Cashier where applicable, Category, Amount, Status, Source Type, Source Reference, Expense Account, Cost Center and Description.

Native ERPNext forms are not made the normal owner by this slice.

## Accounting Safety

This slice is read-only.

It does not:

- create or mutate GL Entry;
- create or submit Purchase Invoice, Expense Claim or Journal Entry;
- post Cashier Expense;
- alter outstanding balances;
- alter Payment Ledger Entry;
- change stock valuation or COGS;
- change Branch attribution;
- change Expense Category validation;
- mutate submitted accounting documents.

ERPNext/Frappe source documents and General Ledger remain authoritative.

## Dashboard Boundary

This slice changes Expense Register only. Existing Expenses Dashboard internal calls do not opt into `view_mode=consolidated` yet, so its established calculations are not silently changed.

A later bounded slice may move Expenses Dashboard and budget intelligence onto the consolidated dataset after its source/category semantics are separately validated.

## Tests Required

- privileged versus cashier-only view capability;
- explicit consolidated mode routing;
- source-voucher allow-list;
- expense-account root filter;
- Cashier Expense posting-reference deduplication;
- Branch fail-closed behavior;
- UI view/source filters;
- no accounting mutation.

## Freeze Rule

Freeze F3F26 only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and governed EdgeSuite UI Candidate Compatibility all pass on one exact SHA.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.
