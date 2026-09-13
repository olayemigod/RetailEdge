# RIR2G2G4 — Stock Movement Native Detail Containment

## Goal

Keep Stock Movement History fully usable for EdgeSuite-only users without exposing raw ERPNext/Frappe Form or Report/DocType routes, while preserving native detail links for authorised Native Desk users.

## Current gap

The Stock Movement History page is EdgeSuite-owned, but:

- Item codes are always rendered as links to the native Item Form;
- Voucher numbers are always rendered as links to their native source document Form;
- `openDoc()` always routes directly to Native Desk;
- shell navigation can route Report/DocType targets if stale or tampered items reach the page;
- the page already loads the shared RetailEdge navigation context but does not retain `access.can_use_native_desk`.

For EdgeSuite-only users this creates visible links that either expose Native Desk or lead into an experience the product composition intentionally hides.

## Required contract

- Default Native Desk capability is false.
- Read capability from `navigation.access.can_use_native_desk`.
- Item code remains visible for all users.
- Voucher number/type remain visible for all users.
- Item and Voucher are clickable native Form links only when Native Desk is allowed.
- EdgeSuite-only users see the same Item/Voucher identity as non-clickable text.
- `openDoc()` must fail closed when Native Desk is unavailable.
- Shell navigation must fail closed before Report/DocType routing when Native Desk is unavailable.
- Page and approved URL navigation remain unchanged.

## Safety rules

- Do not change Stock Ledger calculations, opening balances, running balances or Stock Reconciliation treatment.
- Do not change Company/Branch/Warehouse filtering or Branch Assignment precedence.
- Do not change ERPNext roles, permissions or desk access.
- Do not remove source-document identity from the movement table.
- Do not mutate stock/accounting documents.
- Do not change shared EdgeSuite UI runtime.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests required

- Native Desk defaults closed.
- Capability is sourced from shared navigation access.
- Item/Voucher links are capability-gated and preserve plain-text identity.
- `openDoc()` fails closed without Native Desk.
- shell Report/DocType routing fails closed without Native Desk.
- existing stock movement accounting and filter contracts remain unchanged.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
