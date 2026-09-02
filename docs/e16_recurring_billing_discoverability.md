# E16 C12A — Native Recurring Billing Discoverability

## Goal

Make ERPNext's native recurring billing capability discoverable from RetailEdge without creating a second subscription engine, scheduler, invoice generator, or accounting model.

## Business context

RetailEdge already supports normal selling, invoicing, receivables, payments, customer collaboration and collections. A genuine remaining operational gap is recurring customer billing for use cases such as retainers, maintenance, repeat service contracts, memberships, recurring supplies and other periodic billing arrangements.

ERPNext v16 already provides this through native `Subscription` and `Subscription Plan` DocTypes. RetailEdge should expose those authoritative forms rather than reimplementing recurring billing.

## Native ERPNext authority

### Subscription Plan

ERPNext `Subscription Plan` owns:

- the Item to bill;
- currency;
- fixed-rate, price-list or monthly-rate pricing;
- billing interval and interval count;
- optional payment gateway;
- cost center/accounting dimensions.

### Subscription

ERPNext `Subscription` owns:

- Customer or Supplier party context;
- Company;
- start/end dates and trial period;
- recurring plans;
- calendar-month alignment;
- invoice-generation timing;
- payment due days;
- tax templates and discounts;
- grace/unpaid/cancel/completed status handling;
- generation of native Sales Invoices for Customers and Purchase Invoices for Suppliers.

ERPNext creates the invoice itself, saves it, and only submits it when the Subscription's native `submit_invoice` flag is enabled. When that flag is disabled, the generated invoice remains draft. RetailEdge must not override or silently change this native setting.

## Scope

Add two permission-aware native DocType navigation entries to the existing EdgeSuite **Money** group, immediately after `Payment Reconciliation` and before `Bank Transactions`:

1. `Subscriptions` → DocType `Subscription`
2. `Subscription Plans` → DocType `Subscription Plan`

The Money group is used because the native Subscription model can generate either customer Sales Invoices or supplier Purchase Invoices; placing it only under Customers or Sell would misrepresent that native scope.

Use the existing EdgeSuite navigation permission resolver. DocType entries remain visible only when the DocType exists and the current user has native read permission through `_has_permission_cached(target, "read", permission_cache)`.

Add a focused source contract test proving placement, uniqueness, native targets and continued permission-aware routing.

## Out of scope

Do not add:

- a RetailEdge Subscription DocType;
- a RetailEdge recurring-invoice scheduler;
- custom recurring invoice generation code;
- automatic Payment Entry creation or collection;
- custom subscription status logic;
- custom grace-period or cancellation logic;
- direct Sales Invoice, Purchase Invoice, GL Entry, Payment Ledger or Stock Ledger writes;
- a new EdgeSuite page or dialog wrapping the native Subscription form;
- hard-coded roles broader than ERPNext's own DocType permissions;
- logic that forces generated invoices to draft or submitted state;
- changes to ERPNext's native `submit_invoice` setting;
- changes to Professional Selling, Advanced Payment Management, Project Operations or existing invoice workflows.

## Safety rules

1. ERPNext remains source of truth for Subscription, Subscription Plan and generated accounting documents.
2. RetailEdge only provides discoverability; it does not generate or submit recurring invoices.
3. Native ERPNext permissions govern access.
4. Native `submit_invoice` configuration remains explicit and authoritative. RetailEdge must not silently enable or disable it.
5. Existing submitted accounting documents must not be mutated by RetailEdge.
6. No manual database commit, `ignore_permissions`, direct GL/SLE/Payment Ledger writes or shadow ledgers.
7. Preserve multi-app coexistence and current EdgeSuite navigation behaviour.

## Files expected to change

- `retailedge/edgesuite_ui.py`
- `retailedge/tests/test_recurring_billing_navigation_contract.py`

This contract document is also added for auditability.

## Tests required

Focused contract tests must verify:

- `Subscriptions` and `Subscription Plans` each appear exactly once in the Money group;
- order is `Payment Reconciliation` → `Subscriptions` → `Subscription Plans` → `Bank Transactions`;
- both use `target_type: DocType` with the correct ERPNext targets;
- DocType navigation continues through `_has_permission_cached(..., "read", ...)`;
- RetailEdge navigation code does not introduce recurring invoice generation, submission, scheduler or accounting-write methods.

After implementation, freeze the exact head and run the standard RetailEdge validation gates: Theme Compatibility, Linters, clean Frappe v16 CI, and EdgeSuite UI Candidate Compatibility.
