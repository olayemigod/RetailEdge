# RIR2F3F25 — Expense EdgeSuite Ownership Correction

## Goal

Correct the ownership classification for RetailEdge-owned expense entities before further MVP hardening.

RetailEdge Cashier Expense and RetailEdge Expense Category are product-owned operational/master entities. Their normal user experience must stay inside EdgeSuite UI even though Frappe DocTypes remain the persistence and validation layer.

## Correction to F3F23

This slice supersedes the F3F23 routing classification that treated Cashier Expense and Expense Category as Native Desk-only detail links.

The corrected contract is:

- Cashier Expense → EdgeSuite Expense Register owner.
- Expense Category → EdgeSuite RetailEdge Setup owner.
- Cashier/User detail → native only as an explicit advanced capability gated by final `can_use_native_desk`.

The F3F23 review mutation and read-scope behavior remain valid and unchanged.

## Final Navigation

When the permission-aware `expense-register` Page is available in the Expenses group, final master composition removes the peer `RetailEdge Cashier Expense` DocType route. This follows the same ownership pattern already used for Professional Selling, Professional Purchasing and Purchase Register.

The underlying Cashier Expense DocType is not renamed or removed and remains the system of record.

Expense Category remains a setup-managed RetailEdge entity under the EdgeSuite Setup owner.

## Scope

- `retailedge/master_experience.py`
- `retailedge/public/js/expense_review/ExpenseReviewReport.vue`
- historical F3F23 source-contract assertion reconciliation
- focused F3F25 contract tests

## Safety

This slice does not change Cashier Expense accounting, posting, review, or Branch scope.

It does not:

- mutate submitted documents;
- alter Expense Category validation;
- change Company/Branch authority;
- change Daily Sales Audit inclusion decisions;
- introduce a duplicate expense ledger;
- change ERPNext/Frappe DocType persistence.

## Follow-on

The next expense ownership slices must complete the owner surfaces themselves:

1. Expense Register — EdgeSuite guided create and record detail continuation with no routine native Cashier Expense form.
2. RetailEdge Setup — EdgeSuite Expense Category management with smart Company → Expense Account / Cost Center filtering and backend validation.

Native forms may remain only as deliberate advanced compatibility for users whose final access grants Native Desk.
