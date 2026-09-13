# RIR2G2G29 — Purchase Reporting Context-Aware Supplier Option Scope

## Goal

Make Purchase Reporting Supplier selection follow the same authorised Purchase Invoice context as the active Purchase Register or Supplier Payables report.

## Gap

Purchase Reporting currently searches the whole Supplier master. The page has Company, Branch, Supplier Group and report-specific period/balance filters, so irrelevant or stale Suppliers can remain selectable.

## Required contract

### Scope authority
- Reuse the existing Purchase Reporting `_assert_report_access` and `_invoice_branch_scope` authority.
- Company is required.
- Explicit/restricted blank Branch semantics remain unchanged and fail closed when Purchase Invoice Branch attribution is unavailable.

### Purchase Register Supplier evidence
- Candidate Suppliers originate from permission-aware submitted Purchase Invoices in:
  - selected Company;
  - authorised Branch scope;
  - selected From/To period;
  - selected Supplier Group when supplied;
  - selected invoice kind and status when supplied.
- Purchases and Returns follow the existing `is_return` meanings.

### Supplier Payables evidence
- Candidate Suppliers originate from permission-aware submitted non-return Purchase Invoices:
  - selected Company;
  - authorised Branch scope;
  - posting date up to the current As Of date;
  - current `outstanding_amount > 0`;
  - selected Supplier Group/status when supplied.
- This mirrors the visible current-payables contract rather than showing fully settled historical suppliers.

### Master recheck and bounds
- Supplier candidates are rechecked through permission-aware Supplier master reads.
- Search may match Supplier ID or Supplier Name.
- Search is bounded.

### Frontend cascade
- Option search passes Company, Branch, Supplier Group, report type, From/To dates, As Of date, invoice kind and status.
- Company change clears Branch, Warehouse and Supplier.
- New Branch selection clears Supplier.
- Clearing Branch may retain Supplier because scope broadens.
- Supplier Group select/clear clears Supplier.
- Purchase Register date changes clear Supplier.
- If Warehouse selection resolves a different Branch, Supplier is cleared before using the new Branch context.

## Out of scope

- Purchase Register calculations, returns signing, Supplier Payables ageing/current-outstanding calculations, item/warehouse filtering, report export/pagination, payment creation or native-detail containment.
- Supplier Group option narrowing.
- Purchase Invoice/Supplier/accounting mutation.

## Safety

- No submitted-document mutation.
- No `ignore_permissions`.
- No manual commit.
- Existing Purchase Reporting read authority remains authoritative.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
