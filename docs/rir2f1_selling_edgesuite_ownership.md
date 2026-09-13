# RIR2F1 — Selling EdgeSuite Operational Ownership

## Status

- Authoritative PR: #55
- Authoritative branch: `qa/retailedge-reconciled-20260902`
- Starting head: `6adda0ae4072e16bef1ec9b60e3f6f7afea2e028`
- Scope: Selling composition and frontend ownership only
- Reporting: remains blocked
- Purchasing, Payments and Stock ownership: explicitly deferred

## Business goal

RetailEdge must not behave as an ERPNext menu wrapper. Routine selling work should stay inside the EdgeSuite RetailEdge experience while ERPNext remains the system of record for Quotation, Sales Order, Delivery Note and Sales Invoice truth.

RIR2F1 therefore makes Professional Selling the canonical everyday RetailEdge selling surface where that Page is available and permitted.

## Pre-change leakage

Before RIR2F1:

- Professional Selling was inserted beside native Sales Invoice, Sales Order and Delivery Note routes.
- Professional Selling exposed a normal `View Records` action that opened ERPNext lists.
- recent selling rows opened native ERPNext Forms.
- guided save handlers could automatically open the returned native form route.
- child selling dialogs exposed `Open Full Form` as an ordinary footer action.
- Transaction Workspace `View Records` for Sales Invoice opened the native Sales Invoice list.

These behaviours were technically valid ERPNext fallbacks, but they contradicted the RetailEdge MVP requirement that EdgeSuite own routine operations.

## Final selling route contract

When `professional-selling` is permission-available:

- keep Transaction Workspace;
- keep Professional Selling;
- keep the configured POS runtime destination;
- keep Sales Team / target / configuration items that are outside the owned document set;
- remove Sales Invoice, Sales Order and Delivery Note as peer everyday navigation entries.

If Professional Selling is not permission-available, the existing native document routes remain as compatibility fallback so an otherwise authorised user is not stranded.

ERPNext DocTypes and permissions are not removed or changed.

## Professional Selling behaviour

Professional Selling remains responsible for guided creation of:

- Quotation;
- Sales Order;
- Delivery Note;
- Sales Invoice, including the already-supported conversion/return preparation paths.

Everyday read behaviour is now EdgeSuite-first:

- Recent replaces the normal `View Records -> ERPNext list` path.
- recent rows are read-only EdgeSuite list rows and do not act as disguised native links.
- guided saves close the dialog, refresh Professional Selling and stay inside EdgeSuite.

## Advanced Native Desk rule

The shared EdgeSuite access context remains authoritative for native Desk exposure.

`navigation.access.can_use_native_desk` controls the explicit `Advanced: Open in ERPNext` actions shown by Professional Selling.

Users without Native Desk entitlement do not receive those advanced actions. The existing EdgeSuite-only operational guard remains installed as defence-in-depth against native route escape.

The legacy child-dialog `Open Full Form` buttons are suppressed by the Professional Selling page so they are no longer part of the ordinary selling journey. Native Desk users use the explicit stage/recent advanced action instead.

## Transaction Workspace handoff

For Sales Invoice only in RIR2F1:

- guided Sales Invoice creation remains unchanged;
- `View / Manage` routes to `professional-selling` rather than `/app/sales-invoice`.

Purchase Invoice and Stock Entry behaviour in Transaction Workspace are intentionally unchanged and belong to later ownership slices.

## Safety boundaries

RIR2F1 does not change:

- submitted document immutability;
- Sales Invoice accounting or GL behaviour;
- Delivery Note stock posting or SLE behaviour;
- Quotation or Sales Order lifecycle semantics;
- taxes;
- pricing;
- Shipping Rules;
- Loyalty accounting;
- Branch Assignment authority;
- Company/Branch validation;
- Frappe permissions;
- POSNext internals;
- Professional Purchasing;
- Payment Management;
- Stock operational ownership;
- Bank Matching or Banking Readiness;
- reporting.

The existing permission-aware Professional Selling backend remains unchanged.

## Files changed

Runtime:

- `retailedge/master_experience.py`
- `retailedge/public/js/professional_selling/ProfessionalSelling.vue`
- `retailedge/public/js/transaction_workspace/TransactionWorkspace.vue`

Tests:

- `retailedge/tests/test_rir2f1_selling_edgesuite_ownership_contract.py`

Documentation:

- `docs/rir2f1_selling_edgesuite_ownership.md`
- `docs/prereporting_edgesuite_operational_surfaces.md`

## Automated acceptance

Focused coverage must prove:

1. Professional Selling replaces Sales Invoice, Sales Order and Delivery Note peer navigation when permitted.
2. the three native peers remain when Professional Selling is unavailable.
3. Transaction Workspace, POS and Sales Team entries are not removed accidentally.
4. Professional Selling no longer exposes ordinary native record-list or recent-row navigation.
5. guided saves do not automatically open returned native routes.
6. explicit advanced ERPNext actions depend on shared Native Desk access.
7. Transaction Workspace Sales Invoice read/manage routes to Professional Selling.
8. Purchase Invoice and Stock Entry paths remain unchanged in this slice.

## Manual QA required before freeze

On `retail.local`, test at least Owner/RetailEdge Manager, EdgeSuite-only Sales user and authorised Native Desk advanced user:

- Business Hub Sell composition;
- Professional Selling create flows;
- Recent record lists;
- no automatic native form after save;
- Native Desk advanced action visibility and behaviour;
- Transaction Workspace Sales Invoice View / Manage;
- no regression to Purchase Invoice or Stock Entry actions;
- light/dark representative rendering;
- browser console/network for asset/runtime errors.

RIR2F1 should not be frozen until the current exact-head automated gates are green and this focused browser QA passes.
