# RetailEdge EdgeSuite UI Control Reports — Phase 3

## Business goal

Improve the readability and actionability of RetailEdge control reports without changing ERPNext accounting truth or introducing operational write actions.

This phase extends the shared EdgeSuite Query Report adapter introduced in the earlier report migration. Native Frappe filters, tables, links, export, print, refresh and permission behaviour remain authoritative.

## Reports migrated

### 1. RetailEdge Invoice Payment Audit

The EdgeSuite surface highlights:

- invoice count;
- missing payment rows;
- payment-account mismatches;
- high-risk invoices;
- recommendations for missing evidence and account exceptions.

The underlying invoice-payment audit query and calculations are unchanged. The report does not update Sales Invoices, Payment Entries, payment rows, verification status or ledger records.

### 2. RetailEdge Cash Shift Verification

The EdgeSuite surface highlights:

- expected cash;
- actual closing cash;
- signed native cash variance;
- exception count;
- missing opening or closing shifts;
- shortages and overages;
- eligible cash invoices not yet reflected as cash verified by shift.

The report remains a read-only view of Daily Sales Audit and invoice-verification evidence. It does not create or edit POS shifts, daily audits, invoices or payments.

The existing native Cash Variance summary calculation is preserved. EdgeSuite recommendations use absolute and row-level exception evidence so shortages and overages cannot hide each other in the guidance layer.

### 3. RetailEdge Unmatched Bank Transactions

The EdgeSuite surface highlights:

- total unmatched transactions;
- transactions with suggested candidates;
- transactions without candidates;
- unresolved canonical account context;
- aged transactions without candidates;
- candidate blockers.

This phase does not create a Bank Match Review, confirm a match, reconcile a Bank Transaction, create a Payment Entry or Journal Entry, or change reconciliation status.

## Shared behaviour

Each migrated report:

- registers with `retailedge_report_edgeui.js`;
- receives an EdgeSuite business header and status;
- renders selected native summary cards;
- shows recommendations based on returned read-only rows;
- shows a useful empty state;
- preserves the native Frappe Query Report table;
- preserves refresh, filters, links, export and print;
- falls back to the native Frappe summary if the shared runtime cannot mount.

## Safety boundaries

This phase adds no whitelisted write endpoint and performs no document mutation.

The following remain out of scope:

- Cashier Expense form migration;
- bank-match review creation or confirmation;
- Bank Transaction reconciliation;
- Payment Entry or Journal Entry creation;
- Sales Invoice mutation;
- POS shift mutation;
- Daily Sales Audit workflow actions;
- stock or GL posting.

## Files changed

- `retailedge/retailedge/report/retailedge_invoice_payment_audit/retailedge_invoice_payment_audit.py`
- `retailedge/retailedge/report/retailedge_invoice_payment_audit/retailedge_invoice_payment_audit.js`
- `retailedge/retailedge/report/retailedge_cash_shift_verification/retailedge_cash_shift_verification.py`
- `retailedge/retailedge/report/retailedge_cash_shift_verification/retailedge_cash_shift_verification.js`
- `retailedge/retailedge/report/retailedge_unmatched_bank_transactions/retailedge_unmatched_bank_transactions.py`
- `retailedge/retailedge/report/retailedge_unmatched_bank_transactions/retailedge_unmatched_bank_transactions.js`
- `retailedge/tests/test_retailedge_report_edgeui.py`

## Migration and backward compatibility

No DocType field, database patch or migration is introduced.

Existing report names, routes, filters, columns and native links remain stable. If EdgeSuite UI fails to load, users retain the normal Frappe Query Report summary and table.

## Automated tests required

The focused report tests cover:

- shared adapter attachment for all migrated reports;
- native filter preservation;
- KPI selection;
- payment-exception recommendations;
- cash-shift exception and sync recommendations;
- unmatched-bank account, ageing, candidate and blocker recommendations;
- explicit absence of document write operations.

Full build, migration and Frappe test execution still depend on the RetailEdge repository secret `EDGESUITE_UI_TOKEN` being able to read `olayemigod/processedge-edge-suite-ui`.

## Manual QA gate

After clean CI passes, verify with real permitted data:

1. all existing filters and automatic refresh behaviour;
2. native DataTable links and drill-downs;
3. summary values against the previous native report;
4. recommendations for each exception type;
5. empty-state and native fallback behaviour;
6. export and print;
7. desktop and mobile layout;
8. branch, company and role permissions.
