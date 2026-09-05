# Pre-reporting Customer Advance Register read-scope contract

## Business goal

The Customer Advance Register must not broaden a restricted blank Branch into all open Customer advances for the selected Company. Its Script Report execution must enforce the current reader's Company/Branch reporting scope before reading authoritative Payment Entry state.

## B4B25 scope

This slice hardens only `RetailEdge Customer Advance Register` and its bounded, permission-aware read of submitted Receive Payment Entries with unapplied value. It does not create or update Payment Entries, allocate advances, run Payment Reconciliation, alter invoices, reconstruct historical wallets, or change any accounting workflow.

## Read-scope contract

- Company remains mandatory and both Payment Entry read permission and current-reader Company permission are checked before scope resolution.
- Explicit Branch is revalidated through `validate_report_scope` and applied as a scalar predicate.
- Restricted blank single-Branch scope is applied as a scalar predicate.
- Restricted blank multi-Branch scope is applied as an `IN` predicate over the authoritative allowed Branches.
- Restricted-zero, invalid explicit Branch and denied Company scope stop before the Payment Entry query.
- An unexpected restricted-empty scope cannot remove the Branch predicate.
- Restricted reads fail closed if Payment Entry has no usable Branch attribution field.
- Unrestricted global and compatible unrestricted legacy readers preserve the existing Company-wide blank-Branch register.
- Customer/date filters, submitted Receive/Customer/open-advance criteria, result calculations and the 2,000-row bound remain unchanged.
- Unattributed Payment Entries are excluded from restricted reads rather than treated as Company-wide.

## Preserved accounting and candidate invariants

ERPNext Payment Entry `unallocated_amount` remains the sole current-open advance truth. No balance table, provenance reconstruction, document mutation or reconciliation behavior is introduced.

The separate banking invariant remains untouched:

`selected report row candidate == batch job locked candidate == Bank Match Review candidate == confirmation candidate`

The report does not import or call candidate discovery, scoring, locking, review, confirmation or reconciliation code. Payment Management navigation, Business Hub and reconciled QA composition remain unchanged.

## Deferred manual QA

Browser/persona validation remains part of the reconciled manual QA pass. Verify the report as unrestricted owner, unrestricted legacy manager, restricted single-Branch user, restricted multi-Branch user, restricted-zero user, Company-denied user and invalid explicit-Branch user. Confirm rows change only by scope, unattributed rows do not leak into restricted views, and no Payment Entry, invoice or reconciliation state is modified.
