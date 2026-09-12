# RIR2G2G15 — Operating Context and Setup Native Fallback Containment

## Goal

Keep operating-context, Branch Setup, Branch Assignment and EdgeSuite-owned setup management available while making retained native administrator forms explicit and unavailable to EdgeSuite-only users.

## Scope

- Operating Context
- RetailEdge Setup
- Branch Setup
- Branch Assignments
- Native setup/master record and full-form fallbacks

## Required contract

- All four pages read `navigation.access.can_use_native_desk` from the authoritative Business Hub context.
- Shell DocType/Report navigation fails closed for EdgeSuite-only users.
- Operating-context switching remains unchanged.
- Expense Category management, Branch Setup editing, Branch Assignment creation/transfer and the setup-to-operating-context transitions remain in EdgeSuite.
- Setup resources backed only by native DocTypes are disabled and labelled as advanced when Native Desk is unavailable.
- Branch Setup and Branch Assignment full-form actions are disabled and labelled as advanced without Native Desk.
- Every native resource/create/full-form handler independently fails closed.
- Existing permissions and server-side validation remain authoritative.

## Safety

- No operating-context, branch-scope, assignment-history or controlled-reassignment behavior changes.
- No setup data model, permission, role or server API changes.
- No shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
