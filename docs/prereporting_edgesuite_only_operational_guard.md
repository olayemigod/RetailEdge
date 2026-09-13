# RetailEdge B2B1 — EdgeSuite-Only Operational Guard

## Goal

Prevent an `EdgeSuite Only` RetailEdge user from being pushed into native ERPNext Desk while using the already-promoted everyday Professional Selling and Payment Management workspaces.

This slice is presentation/routing hardening only. It does not change ERPNext permissions, Frappe role `desk_access`, accounting logic, document lifecycle rules, or submitted documents.

## Existing authority preserved

ERPNext remains the system of record for Quotations, Sales Orders, Delivery Notes, Sales Invoices, Payment Entries and Payment Reconciliation. RetailEdge continues to use the existing permission-aware server APIs and guided draft/reconciliation services.

`Native Desk + EdgeSuite` users retain the existing native fallbacks and record-opening behaviour.

## EdgeSuite Only behaviour

The product-local compiled asset `retailedge_edgesuite_only_operational_guard.bundle.js` reads the shared boot contract:

- `frappe.boot.edgesuite_ui_access.mode == "edgesuite_only"`

The guard is a Frappe lazy-load bundle so it participates in the normal asset build/manifest contract.

When, and only when, the current Frappe route is a configured operational EdgeSuite Page, the guard:

- blocks configured native ERPNext Form/List routes;
- blocks configured `/app/<doctype>` native URLs opened in a new tab;
- hides known native-only buttons such as `View Records`, `Open Full Form`, `Payment Entries`, and `Open Draft Payment` where present;
- neutralizes clickable record rows/links that only open the same native records;
- silently blocks automatic post-save redirects to native Desk so a successful guided save does not produce a misleading access warning;
- shows an explanatory notice for explicit user-triggered blocked native actions.

The guard is inactive on all other RetailEdge Pages and for users whose boot mode is not `edgesuite_only`.

## Professional Selling

Configured native targets:

- Quotation
- Sales Order
- Delivery Note
- Sales Invoice

Guided creation, conversion and recent-record loading remain unchanged. Native record/list opens are treated as advanced fallbacks for restricted users.

## Payment Management

Configured native targets:

- Payment Entry
- Sales Invoice
- Payment Reconciliation

Customer advance application, mixed settlement, draft receipt creation and ERPNext reconciliation authority remain unchanged. Native accounting forms remain advanced fallbacks.

A restricted user who reaches a case that genuinely requires advanced native accounting—for example a non-company-currency settlement explicitly delegated to native ERPNext—must hand the case to an authorised advanced user. This slice does not weaken accounting controls to make such cases available to everyday users.

## Safety boundaries

This slice must not:

- change `desk_access` on any Role;
- add or remove ERPNext permissions;
- use `ignore_permissions`;
- create a parallel receivables, payment or selling ledger;
- mutate submitted Sales Invoices, Payment Entries, Delivery Notes or other accounting/stock documents;
- bypass Payment Reconciliation;
- change company/branch permission enforcement;
- make Stock Movement History primary before its separate parity/browser gate.

## Validation

Required exact-head gates:

1. RetailEdge Theme Compatibility
2. Linters / pre-commit / Semgrep / dependency audit
3. Clean Frappe v16 install + migrate + full RetailEdge tests
4. EdgeSuite UI candidate compatibility

Focused contract coverage verifies boot-mode gating, current-route scoping, bounded native targets, compiled bundle loading, Page-controller integration, and absence of permission/accounting rewrites.

## Manual QA deferred

No browser QA claim is made by this checkpoint. Final persona QA should include at least:

- EdgeSuite-only salesperson creating and reviewing selling drafts without entering native Desk;
- EdgeSuite-only cashier/accounts operator recording advances and settlements without entering native Desk;
- advanced user confirming native fallbacks still work;
- navigation away from the guarded Pages confirming native routing is no longer intercepted.
