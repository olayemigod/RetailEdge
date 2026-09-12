# RIR2G2G17 — Stock & Accounting Integrity Native Detail Containment

## Goal

Preserve the EdgeSuite Stock & Accounting Integrity control surface and ERPNext-derived mismatch truth while containing retained native voucher, ledger and advanced-report drill-through for EdgeSuite-only users.

## Scope

- Stock & Accounting Integrity EdgeSuite report
- Voucher and ledger-row native detail drill-through
- ERPNext Stock and Account Value Comparison advanced report handoff
- Shell DocType / Report navigation

## Required contract

- Stock & Accounting Integrity reads `navigation.access.can_use_native_desk` from the authoritative Business Hub context.
- Shell DocType/Report navigation fails closed for EdgeSuite-only users.
- Voucher, ledger, difference and accounting-control identity/value remain visible for every permitted user.
- Voucher and ledger columns are clickable only when Native Desk is available.
- Native ERPNext advanced-report availability continues to respect the existing backend `can_open_native_report` permission signal.
- When the backend allows the native report but Native Desk is unavailable, the action remains visibly classified as an advanced workflow but disabled.
- Native voucher/ledger/report handlers independently fail closed without Native Desk.
- Native-Desk-capable users retain the existing ERPNext detail/report routes.

## Safety

- No Stock Ledger Entry, GL Entry, voucher, valuation, comparison-report or mismatch calculation changes.
- No Company-wide scope, date/account filter, pagination, sorting, export, summary, permission, role or server API changes.
- No correction/reposting document creation, submitted-document mutation, direct GL/SLE write, `ignore_permissions` or manual database commit.
- No shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
