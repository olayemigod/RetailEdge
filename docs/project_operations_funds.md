# RetailEdge Project Operations & Project Funds

## Stack dependency

This work is intentionally stacked on PR #42 (`agent/advanced-payment-management`).

Predecessor head at branch creation:

`2795da2c4d0f9cadff6eec4cb14d157a64f7ccf1`

Do not retarget this branch to `version-16` until PR #42 and its predecessor stack have been merged or explicitly reconciled.

## Business goal

Provide an EdgeSuite operational view for project-based businesses while preserving ERPNext as the source of truth for project, accounting, purchasing, stock and payment records.

RetailEdge must support:

- project operational summary;
- project customer/company context;
- project receipts;
- project cash funds position;
- ERPNext billing/cost/margin visibility;
- project expenses/purchases/stock links and later guided workflows;
- project portfolio and financial reporting.

## Source-of-truth contract

RetailEdge does not create a project wallet or independent project ledger.

Authoritative sources are:

- ERPNext `Project` for project identity, customer, company, dates, costing, billing and gross-margin totals;
- ERPNext `Payment Entry.project` for project-attributed receipts and payments;
- ERPNext Sales Invoice / Sales Order for project revenue and billing;
- ERPNext Purchase Invoice / Expense Claim / Journal Entry / Stock Entry and their native Project accounting dimensions for costs and operational postings;
- ERPNext GL / Payment Ledger / Stock Ledger for accounting and stock truth.

Submitted accounting documents are not mutated by RetailEdge.

## Implemented foundation

### `retailedge.project_operations.get_project_funds_context`

Returns a permission-aware project snapshot containing:

- Project status, dates and completion;
- ERPNext Project estimated cost;
- Sales Order value;
- billed amount;
- purchase cost;
- consumed material cost;
- timesheet costing;
- ERPNext gross margin;
- submitted project-linked customer receipts;
- submitted project-linked outgoing Payment Entries;
- cash funds received;
- cash funds paid out;
- cash funds position;
- unapplied project receipt amount.

Branch-scoped requests fail closed if RetailEdge Payment Entry branch attribution is unavailable.

### `retailedge.project_receipts.create_project_receipt_draft`

Creates a standard draft ERPNext Payment Entry with:

- `payment_type = Receive`;
- Project Customer;
- Project Company;
- native `project` accounting dimension;
- Project default Cost Center where configured;
- RetailEdge Branch attribution where requested;
- company-currency validation;
- Mode of Payment account resolution.

The receipt is never auto-submitted. ERPNext remains responsible for review, validation, submission and later invoice allocation/reconciliation.

## Safety rules

- No custom Project Funds balance DocType.
- No direct GL Entry write.
- No direct Sales Invoice outstanding mutation.
- No submitted Payment Entry mutation outside ERPNext reconciliation mechanisms.
- Project Customer and Project Company cannot be silently replaced by guided receipt input.
- Branch-scoped flows fail closed without branch attribution.
- Multi-currency cases fall back to native ERPNext forms until explicitly covered.
- Queries are bounded.

## Next work in this same PR

1. EdgeSuite Project Operations page.
2. Governed navigation and Project entry point.
3. Project transaction timeline from native ERPNext documents.
4. Guided project expense routing using the correct native ERPNext source document instead of a custom expense ledger.
5. Project Funds / Project Portfolio reporting.
6. Focused UI/source contract tests.
7. CI, migration and manual browser/accounting QA.
