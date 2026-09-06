# E16 C27 — C24–C26 EdgeSuite Visual Completion

## Goal

Complete the product-facing visual layer for the C24 Warranty & After-sales, C25 Sales Team / Targets / Commissions, and C26 Budgeting & Cost Control slices without replacing ERPNext as source of truth.

## Delivered

Three primary EdgeSuite control pages are added:

- Service & Warranty
- Sales Team, Targets & Commissions
- Budgeting & Cost Control

Each page uses the shared EdgeSuite shell, shows only permission-available native capabilities, previews a bounded set of recent permitted ERPNext records, and keeps native documents/reports as authoritative create, edit, submit, lifecycle and advanced-report handoffs.

## Safety

This slice does not add a warranty/service lifecycle, commission or payout engine, budget ledger, budget enforcement engine, accounting write, stock write, submitted-document mutation, manual commit, `ignore_permissions`, schema change, migration, or data patch.

The read service uses native DocType read/create permission checks, permission-aware `frappe.get_list`, and native `get_report_doc` access for reports. The UI never inserts or submits documents server-side.

## Backward compatibility

Existing C24–C26 native navigation targets remain present as fallback destinations. The new EdgeSuite page is added before those targets so everyday users receive a consistent RetailEdge experience while advanced ERPNext access remains available.

## Validation

Required before freeze:

- focused visual-workspace contract tests
- existing C24, C25 and C26 contracts
- RetailEdge Theme Compatibility
- Linters / pre-commit / Semgrep / dependency audit
- clean Frappe v16 standalone CI and full RetailEdge tests
- governed EdgeSuite UI candidate compatibility and full RetailEdge tests

Manual browser QA remains deferred to the consolidated QA line.
