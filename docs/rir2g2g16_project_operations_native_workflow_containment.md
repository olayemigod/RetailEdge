# RIR2G2G16 — Project Operations Native Workflow Containment

## Goal

Keep Project Operations intelligence and EdgeSuite project context available while making retained ERPNext Project, Task, Budget, Payment Entry, project-spend and native report workflows explicit advanced fallbacks that are unavailable to EdgeSuite-only users.

## Scope

- Project Operations
- Project / Task / Budget native detail and create actions
- Project Financial Control native Query Report
- Project Spend & Materials native-entry handoff
- Project Receipt draft handoff
- Project transaction timeline and project-linked Payment Entry detail
- Shell DocType / Report navigation

## Required contract

- Project Operations reads `navigation.access.can_use_native_desk` from the authoritative Business Hub context.
- Shell DocType/Report navigation fails closed for EdgeSuite-only users.
- Project, Task, Budget, timeline and Payment Entry identities remain visible for permitted users.
- Native detail links render only for Native-Desk-capable users.
- Header actions that require native ERPNext forms/reports are disabled and labelled as advanced when Native Desk is unavailable.
- Project Spend & Materials remains an explicit advanced native-entry workflow and fails closed without Native Desk.
- Project Receipt remains unchanged for Native-Desk-capable users; because its current completion path is a native Payment Entry draft review, the action is treated as advanced and fails closed without Native Desk.
- Every native form/report/create handler independently fails closed.
- Authorised Native Desk users retain the existing ERPNext routes and draft semantics.

## Safety

- No Project, Task, Budget, Payment Entry, Purchase Invoice, Expense Claim, Stock Entry or accounting data-model changes.
- No project-funds, project-cost, margin, cash-in/out, task, milestone, budget or timeline calculation changes.
- No Company/Branch scope, project search, branch search, permission, role or server API changes.
- No document auto-submit, submitted-document mutation, `ignore_permissions`, direct GL/SLE write or manual database commit.
- No shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
