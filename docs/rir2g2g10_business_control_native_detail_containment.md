# RIR2G2G10 — Business Control Centre Native Detail Containment

## Goal

Preserve Business Control Centre management truth, lazy financial details and follow-up controls while containing retained native ERPNext workflow and invoice-detail routes for EdgeSuite-only users.

## Ownership finding

Business Control Centre composes Action Centre exceptions with R9 financial signals. It is a management read/control surface, not a replacement accounting ledger. EdgeSuite Pages remain ordinary resolution paths; DocType/Query Report workflows and invoice detail forms are deliberate Advanced Native Desk handoffs.

## Current gap

- Control-row workflow actions did not consume Native Desk capability.
- `openWorkflow()` routed retained DocType/Report targets without a defensive check.
- Shell DocType/Report navigation was unguarded at page level.
- Receivables and supplier-obligation detail rows opened Sales Invoice and Purchase Invoice forms without a capability check.

## Required contract

- Read `navigation.access.can_use_native_desk` from the authoritative Business Hub context.
- Pass the resolved capability into control rows and lazy owner-detail panels.
- Keep all management figures, document identities, priorities and follow-up controls visible.
- Disable and label retained native workflow actions as advanced for EdgeSuite-only users.
- Disable native invoice-detail drill-through while preserving the invoice number and business context.
- Fail closed inside workflow, shell-navigation and invoice-detail handlers.
- Preserve all behavior for authorised Native Desk users.

## Safety rules

- No accounting, stock, payment, budget, receivable, payable or action-follow-up calculation changes.
- No Company/Branch scope, role or permission changes.
- No report/export/print changes.
- No submitted-document mutation.
- No shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
