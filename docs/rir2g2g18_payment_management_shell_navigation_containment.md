# RIR2G2G18 — Payment Management Shell Navigation Containment

## Goal

Close the remaining Payment Management shell-level Native Desk escape without changing its EdgeSuite payment, advance, settlement or draft-review workflows.

## Scope

- Payment Management EdgeAppShell navigation only
- Retained shell DocType and Query Report routes

## Required contract

- Payment Management continues to use the existing authoritative `navigation.access.can_use_native_desk` capability already loaded by the page.
- Shell DocType/Report navigation fails closed for EdgeSuite-only users.
- EdgeSuite Page routes and approved URL behavior remain unchanged.
- Existing native Payment Entry and Sales Invoice detail handlers remain independently capability-gated.
- Payment draft review, customer advances, invoice settlement, receipt draft creation and EdgeSuite-owned payment workflows remain unchanged.

## Safety

- No payment allocation, reconciliation, Payment Entry creation, Sales Invoice outstanding, customer advance, Company/Branch scope, permission, role or server API changes.
- No submitted-document mutation, auto-submit, `ignore_permissions`, direct GL write or manual database commit.
- No shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
