# E16 C11A — Native Payment Reconciliation Discoverability

## Goal

Make ERPNext's native Payment Reconciliation tool discoverable from the RetailEdge EdgeSuite navigation so authorised accounting users can safely apply customer credits/advances and supplier debits against open invoices without introducing a RetailEdge shadow ledger or reconciliation engine.

## Business context

C9A introduced a guided Sales Return / Credit Note handoff that creates a draft return through ERPNext's native Sales Invoice return mapper. Once a submitted Credit Note exists, ERPNext already owns the accounting treatment for leaving the credit unapplied, reconciling it against another invoice, or creating a Payment Entry for a refund.

RetailEdge Advanced Payment Management currently focuses on submitted Payment Entry advances. It must not be expanded into a parallel customer-credit ledger merely to cover Sales Return Credit Notes.

## Native ERPNext authority

ERPNext v16 Payment Reconciliation is the authoritative allocation surface. Its server logic:

- reads unreconciled Payment Ledger entries;
- includes submitted Sales/Purchase return invoices as debit/credit notes;
- applies allocations through ERPNext reconciliation mechanics;
- preserves accounting dimensions and Payment Ledger authority;
- remains permissioned to Accounts User / Accounts Manager by the native DocType.

ERPNext's submitted Sales Invoice form also exposes the standard Payment action whenever outstanding amount is non-zero, including return Credit Notes, so refund Payment Entry creation remains native ERPNext responsibility.

## Scope

Add one permission-aware navigation item under the existing EdgeSuite **Money** group:

- Label: `Payment Reconciliation`
- Target type: `DocType`
- Target: `Payment Reconciliation`
- Placement: immediately after `Payments`

Use the existing EdgeSuite navigation permission resolver. For DocType targets, `_can_open_target` already checks existence and read permission via `_has_permission_cached(target, "read", permission_cache)`.

Add a focused source contract test proving the item is present once, placed in the intended Money group, uses the native DocType target, and continues to rely on the existing read-permission path.

## Out of scope

Do not add:

- a RetailEdge customer-credit wallet or ledger;
- a new reconciliation DocType;
- a custom allocation/reconciliation API;
- a custom Credit Note refund API;
- direct Payment Ledger, GL Entry, Sales Invoice outstanding, or Stock Ledger mutations;
- automatic submission of Payment Entry or accounting documents;
- `ignore_permissions` or manual database commits;
- a new EdgeSuite page/dialog that wraps the native Payment Reconciliation form;
- role hard-coding broader than ERPNext's own DocType permissions;
- changes to existing Advanced Payment Management behaviour.

## Safety rules

1. ERPNext remains the source of truth for invoices, Credit Notes, Payment Entries, Payment Ledger and reconciliation.
2. Submitted Sales Invoices/Credit Notes are not mutated by RetailEdge.
3. Native Payment Reconciliation remains the only allocation authority for this handoff.
4. Native Payment Entry remains the refund/payment authority.
5. Navigation visibility must remain permission-aware through existing EdgeSuite target filtering.
6. No new frontend runtime is introduced; this is a native DocType handoff from the existing EdgeSuite shell.
7. Preserve multi-app coexistence and existing navigation semantics.

## Files expected to change

- `retailedge/edgesuite_ui.py`
- `retailedge/tests/test_payment_reconciliation_navigation_contract.py`

This contract document is also added for auditability.

## Tests required

Focused contract tests must verify:

- `Payment Reconciliation` appears exactly once in the Money group;
- it appears immediately after `Payments` and before `Bank Transactions`;
- target type is `DocType` and target is `Payment Reconciliation`;
- DocType targets continue to pass through `_has_permission_cached(..., "read", ...)`;
- RetailEdge does not introduce custom reconciliation/refund/posting methods or direct accounting writes in the navigation implementation.

After implementation, freeze the exact head and run the standard RetailEdge validation gates: Theme Compatibility, Linters, clean Frappe v16 CI, and EdgeSuite UI Candidate Compatibility.
