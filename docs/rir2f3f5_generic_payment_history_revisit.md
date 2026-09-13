# RIR2F3F5 — Generic Payment History & Revisit Ownership

## Goal
Make Payment Management the everyday EdgeSuite location for finding and revisiting permission-visible ERPNext Payment Entries without creating a second payment ledger or changing ERPNext posting behaviour.

## Context
F3F1/F3F2/F3F3 own standard customer/supplier payment review and submission. F3F4 contains native Payment Entry fallbacks for EdgeSuite-only users. The remaining prerequisite before considering retirement of the peer Payment Entry navigation item is generic payment history/revisit coverage.

## Scope
- Add a bounded, permission-aware Payment Entry history API.
- Reuse the reconciled RetailEdge operational Branch scope contract.
- Support Customer, Supplier and other permission-visible Payment Entries across Draft, Submitted and Cancelled states.
- Add Company, Branch, Party Type, Party, Payment Type, document state and posting-date filters.
- Paginate and cap server reads.
- Add a read-only detail view in Payment Management.
- For eligible draft Customer/Supplier payments, reuse the existing standard submit preview and submit services.
- Keep complex/unsupported drafts visible but classify them for Advanced ERPNext handling.
- Show native ERPNext open actions only when final access context permits Native Desk.

## Out of Scope
- No GL Entry, Payment Ledger Entry or balance reconstruction.
- No new DocType, child table, schema field, patch or migration.
- No cancellation, amendment, deletion or submitted-document mutation.
- No new payment submission engine.
- No removal of Payment Entry or Payment Reconciliation navigation in this slice.
- No generic supplier payment creation redesign.

## Branch and Permission Contract
- Use `get_operational_branch_scope()` so Branch Assignment history remains authoritative and legacy restrictions remain the compatibility fallback.
- Unrestricted users may read across the selected Company when Branch is blank.
- Restricted users with active branches may read across only those branches when Branch is blank.
- Restricted users with zero active branches fail closed.
- An explicit Branch must be validated server-side against Company and operational access.
- Use permission-aware `frappe.get_list` / document read permission; never `frappe.get_all` for user-facing payment history.

## Accounting Safety
ERPNext Payment Entry is the only source of truth. History/detail endpoints are read-only. Standard draft submission continues through the frozen F3F1/F3F2 services and native `Payment Entry.submit()`.

## Expected Files
- `retailedge/payment_history.py`
- `retailedge/public/js/payment_management/PaymentManagement.vue`
- `retailedge/tests/test_rir2f3f5_payment_history_revisit_contract.py`
- this decision document

## Freeze Gate
Freeze only when Theme Compatibility, Linters, clean Frappe v16 CI/full RetailEdge tests, and governed EdgeSuite UI Candidate Compatibility/full RetailEdge tests all pass on the exact head. Manual browser/persona QA remains separate and must not be claimed by this checkpoint.
