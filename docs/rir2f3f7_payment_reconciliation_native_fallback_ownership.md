# RIR2 F3F7 — Payment Reconciliation Native Fallback Ownership

## Business goal

Keep everyday RetailEdge payment operations inside EdgeSuite while preserving ERPNext Payment Reconciliation as the accounting-authoritative advanced workflow for permitted accounting users.

## Ownership decision

- `Money > Payments` remains EdgeSuite-owned through `payment-management`.
- `Money > Bank Matching` remains EdgeSuite-owned through `bank-matching-reconciliation`.
- ERPNext `Payment Reconciliation` is not rebuilt in RetailEdge in this slice.
- ERPNext `Payment Reconciliation` remains available only as an explicit native fallback when the user both:
  - has an accounting-capable RetailEdge role (`Accounts User`, `Accounts Manager`, or `System Manager`); and
  - is allowed to use native Desk by the shared EdgeSuite access context.

Payment Reconciliation is an accounting allocation/reallocation operation. ERPNext remains the source of accounting truth.

## Scope

1. Mark the `Payment Reconciliation` navigation item as a native fallback.
2. Reuse the existing `FINANCE_TRANSFER_ROLES` accounting role set.
3. Pass `can_use_native_desk` into RetailEdge navigation filtering, matching the existing quick-action fallback pattern.
4. Suppress navigation items marked `native_fallback` when native Desk is disabled.
5. Remove internal navigation metadata such as `mode` before returning navigation context to the UI.
6. Add focused contract coverage.

## Out of scope

- Reimplementing ERPNext Payment Reconciliation in EdgeSuite.
- Changing Payment Entry creation, review, submission, allocation, GL posting, Payment Ledger behavior, or cancellation semantics.
- Changing Bank Matching or bank statement import workflows.
- Changing Payment Orders.
- Globally hiding every ERPNext DocType link in RetailEdge navigation.
- Schema changes, patches, migrations, or CoreEdge dependencies.

## Safety rules

- Submitted accounting documents must not be mutated.
- ERPNext permissions remain authoritative in addition to RetailEdge navigation filtering.
- Frontend visibility is not treated as accounting authorization.
- Existing EdgeSuite-only access rules are reused; F3F7 does not introduce a parallel access model.
- Unmarked navigation entries retain their existing behavior.

## Required validation

- Payment Reconciliation remains a native ERPNext DocType target.
- It is hidden from EdgeSuite-only users even if they otherwise have DocType read permission.
- It is visible only when native Desk is enabled and the user has an allowed accounting role and ERPNext read permission.
- `Money > Payments` remains `Page -> payment-management`.
- `Money > Bank Matching` remains `Page -> bank-matching-reconciliation`.
- Payment Orders remain unchanged.
- All four governed PR gates must pass on the exact final head before F3F7 is frozen.

Manual browser/persona QA is separate and must not be claimed unless actually executed.
