# E16 C8A — Pre-Sale Customer Credit Visibility

## Goal

Show sales users the same customer credit exposure ERPNext evaluates before they commit a Sales Order or Sales Invoice, without creating a second credit ledger, override workflow or submission rule.

## Business value

RetailEdge already gives users guided Sales Order and Sales Invoice creation, while ERPNext can later stop submission because a customer has crossed a company credit limit or overdue-billing threshold. C8A moves that information earlier in the workflow so the user can see the risk before building a new sale.

## ERPNext source of truth

C8A must reuse ERPNext v16 credit helpers from `erpnext.selling.doctype.customer.customer`:

- `get_credit_limit(customer, company)`;
- `get_customer_outstanding(customer, company, ignore_outstanding_sales_order=...)`;
- `get_overdue_billing_threshold(customer, company)`;
- `get_customer_overdue_amount(customer, company)`.

ERPNext remains authoritative for:

- Customer / Customer Group credit-limit configuration;
- the `bypass_credit_limit_check` Sales Order setting;
- company-wide credit exposure;
- overdue-billing threshold enforcement;
- Credit Controller / overdue-bypass roles;
- all Sales Order / Sales Invoice submission validation.

## Scope

### C8A backend

Create one read-only, permission-aware endpoint for one Customer + Company at a time.

It returns:

- Company and Customer;
- company currency;
- configured credit limit;
- current ERPNext credit exposure using the native helper;
- remaining credit (`credit_limit - exposure`) when a positive limit exists;
- whether the configured limit is currently crossed;
- Customer Credit Limit `bypass_credit_limit_check` value for this Company;
- configured overdue-billing threshold;
- current overdue amount using ERPNext's native helper;
- whether the overdue threshold is crossed;
- Customer frozen/disabled flags;
- source-of-truth metadata.

### C8A EdgeSuite UI

Add one reusable `CustomerCreditSummary` EdgeSuite-compatible component and show it in the **New Sales Order** and **New Sales Invoice** guided forms after a Customer is selected.

The panel must:

- load only for the selected Customer + Company;
- clear immediately when Customer changes/clears;
- show loading/error/unavailable states without blocking draft preparation;
- show credit limit, current exposure and remaining credit;
- show overdue amount/threshold where configured;
- clearly label crossed conditions as ERPNext credit-control warnings;
- state that final submission remains governed by ERPNext;
- never provide an override/bypass button.

C8A does not need to evaluate source-document conversion modes yet. Native ERPNext mapping/submission remains authoritative for those flows.

## Out of Scope

- no new credit-limit master or Customer credit fields;
- no RetailEdge credit ledger or exposure calculation;
- no arbitrary RetailEdge risk score or 80%/90% warning threshold;
- no credit-limit edits from the panel;
- no Credit Controller approval workflow;
- no email/notification workflow;
- no bypass of ERPNext checks;
- no auto-submit;
- no mutation of submitted Sales Orders or Sales Invoices;
- no branch-specific reinterpretation of company-level ERPNext credit limits;
- no company-wide customer-credit list in C8A.

## Permission and context rules

1. Customer and Company must both exist and be readable by the current user.
2. The endpoint is available only when the user can read the standard ERPNext `Customer Credit Balance` report or otherwise has the relevant Sales/Accounts report access contract.
3. Customer search remains the existing permission-aware Professional Selling search.
4. Credit exposure is company-level because that is ERPNext's enforcement basis. Selecting a RetailEdge Branch must not make the panel claim branch-only credit exposure.
5. Do not use `ignore_permissions=True`.

## Safety rules

- Read only.
- No `frappe.db.commit()`.
- No `.save()`, `.insert()` or `.submit()`.
- No direct GL/Payment Ledger query owned by RetailEdge; call ERPNext helpers instead.
- Do not recalculate Sales Order / Delivery Note exposure independently.
- Do not invent a credit decision separate from ERPNext's configured limits.

## Files to inspect / change

- `retailedge/customer_credit_visibility.py` — new read-only adapter.
- `retailedge/public/js/professional_selling/CustomerCreditSummary.vue` — new EdgeSuite-compatible presentation component.
- `retailedge/public/js/professional_selling/ProfessionalSalesOrderDialog.vue` — load/show selected-customer credit context.
- `retailedge/public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue` — load/show selected-customer credit context.
- focused backend and source/UI contract tests.

Do not broadly rewrite Professional Selling.

## Tests required

Backend:

1. read permission required for Customer + Company;
2. native ERPNext helpers are called with the selected Customer + Company;
3. Sales Order bypass flag controls the native `ignore_outstanding_sales_order` argument;
4. remaining credit and crossed flags are simple derivations from native values;
5. no configured limit is reported as `No Limit`, not as zero available credit;
6. overdue threshold crossing uses ERPNext overdue helper values;
7. frozen/disabled Customer state is surfaced;
8. no writes, direct GL/PLE query or permission bypass.

UI/source contract:

1. reusable component uses only governed EdgeSuite/runtime-compatible markup;
2. Sales Order and Sales Invoice load the credit endpoint after Customer selection;
3. changing/clearing Customer clears stale credit data;
4. no override/bypass action is rendered;
5. existing pricing refresh, Branch cascade and draft-first save behavior remain present;
6. conversion modes remain unchanged.

## Acceptance

Freeze one exact C8A head and require:

- RetailEdge Theme Compatibility green;
- Linters / pre-commit / Semgrep / vulnerable dependency audit green;
- clean Frappe v16 standalone CI green including full RetailEdge tests;
- governed EdgeSuite UI Candidate Compatibility green including build/migrate/full tests.

Manual/browser QA remains deferred to the consolidated QA branch.
