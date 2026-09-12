# RIR2G2G28 — Customer Receivables Context-Aware Customer Option Scope

## Goal

Make the Customer Receivables Customer selector show only customers with current outstanding receivable evidence inside the authorised Company/operational Branch and selected Customer Group.

## Gap

The Customer Receivables dataset is already permission-aware and Branch-scoped over submitted, non-return Sales Invoices, then keeps only positive current outstanding balances.

Its Customer selector currently searches the whole Customer master and the active page sends only Company. This allows irrelevant customers with no receivable in the current business scope to be selected and allows stale Customer values after Branch or Customer Group changes.

## Required contract

### Scope authority
- Reuse the existing Customer Receivables Sales Invoice access and operational Branch authority.
- Company is required.
- Explicit Branch is validated through the existing receivables Branch contract.
- Restricted blank Branch uses the existing single-branch / permitted-union / restricted-zero semantics.
- Missing Sales Invoice Branch attribution continues to fail closed for restricted readers.

### Customer evidence
- Customer candidates originate only from permission-aware submitted Sales Invoices with:
  - selected Company;
  - non-return invoices;
  - current `outstanding_amount > 0`;
  - authorised Branch scope;
  - selected Customer Group when supplied.
- Search may match invoice Customer ID or Customer Name.
- Candidate Customer masters are rechecked through permission-aware Customer reads before returning Link options.
- Search remains bounded.

### Frontend cascade
- Option search passes Company, Branch and Customer Group.
- Selecting a new Company clears Branch and Customer.
- Selecting a new Branch clears Customer.
- Clearing Branch may retain Customer because the scope broadens.
- Selecting or clearing Customer Group clears Customer and its display label.

## Out of scope

- Current-outstanding calculation, ageing buckets, collections enrichment, Payment Request/Dunning flows, report pagination/export or native-detail containment.
- Historical/as-of balance reconstruction.
- Customer Group option narrowing.
- Sales Invoice, Customer, accounting or payment mutations.

## Safety

- No submitted-document mutation.
- No `ignore_permissions`.
- No manual commit.
- Existing receivables read authority remains authoritative.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
