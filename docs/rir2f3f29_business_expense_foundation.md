# RIR2F3F29 — Business Expenses Foundation

## Goal

Create the separate **Business Expenses** operational model for non-POS company spending without merging it with Cashier Expenses or prematurely introducing accounting posting.

## Product Boundary

### Cashier Expenses

Cashier Expense remains the POS/shift-specific workflow. Its cash-availability, POS Opening Shift, cashier identity, Daily Sales Audit and existing review/posting controls are not moved into Business Expenses.

### Business Expenses

`RetailEdge Business Expense` is for non-POS direct business spending such as rent, diesel, subscriptions, local transport, office purchases and similar operating spend.

It captures:

- Company;
- Branch;
- Expense Date;
- Expense Category;
- Amount;
- Description;
- Supplier or other payee;
- receipt/reference;
- evidence attachment;
- Expense Account resolved from Expense Category;
- Paid From Cash/Bank account;
- Cost Center;
- Project;
- workflow/review status;
- future accounting posting reference.

Supplier credit bills remain Purchase Invoice. Employee reimbursement remains Expense Claim where that ERPNext/HR capability is installed. Business Expense must not replace those accounting semantics.

## Workflow Precedence

The F3F27 rule remains authoritative:

1. active Frappe Workflow for `RetailEdge Business Expense`;
2. otherwise the RetailEdge Settings fallback process;
3. no invented approval workflow outside those rules.

The settings fallback supports:

- **Approval Required** — submit, then manager/accounts approval or rejection;
- **Direct Posting** — submit moves the operational document to Approved/Pending Ledger without a separate RetailEdge approval action.

Actual accounting posting is deliberately not implemented in this foundation.

## Smart Form / Validation Contract

Backend validation is authoritative.

- Company must exist and be readable.
- Restricted Branch users:
  - one allowed Branch may auto-resolve;
  - multiple allowed Branches require an explicit Branch;
  - zero allowed Branches fail closed.
- Where RetailEdge Branch Profiles exist, a selected Branch must belong to the selected Company.
- Expense Category must be active and Company-compatible.
- Expense Account is derived from Expense Category and must be an active leaf Expense account.
- Paid From must be an active leaf Cash or Bank account in the selected Company.
- Cost Center must be a valid leaf Cost Center in the Company.
- Project, when selected, must belong to the Company.
- Supplier is required only when Payee Type is Supplier.
- Receipt/evidence becomes mandatory when the setting requires it.

The EdgeSuite UI will use filtered server searches in the next slice; frontend filtering will not be treated as authority.

## Permissions

Cashiers are intentionally not granted Business Expense operation by this DocType.

Business Expense is available to:

- RetailEdge Manager;
- RetailEdge Branch Manager;
- Accounts Manager;
- Accounts User;
- System Manager;

with RetailEdge Auditor retaining read/report access only.

## Accounting Boundary

This slice does not create Journal Entry or GL Entry.

It also does not:

- create Payment Entry;
- mutate submitted accounting documents;
- post balances;
- alter Cashier Expense accounting;
- create a second expense ledger.

The later posting slice will create an ERPNext accounting document through normal document lifecycle and permissions, link it back to Business Expense, and make Expense Register deduplicate the operational and GL representations.

## Migration / Backward Compatibility

This is additive:

- new `RetailEdge Business Expense` DocType;
- additive RetailEdge Settings fields;
- extended workflow readiness/action bridge.

Run normal `bench --site <site> migrate`.

No existing Cashier Expense, Purchase Invoice, Expense Claim, Journal Entry or settings value is renamed or deleted.

## Next Slice

Build the **Business Expenses** EdgeSuite Page with:

- list/queue;
- modern guided entry;
- Company → Branch → Category/Account cascading;
- payee/evidence capture;
- record detail;
- live workflow state/actions;
- no routine native Desk handoff.

Accounting posting remains separately gated after the page is operational.

## Tests

- separate Business Expense schema and absence of POS-specific fields;
- settings fallback process;
- Company/Branch/account validation contracts;
- active Frappe Workflow precedence;
- Business Expense fallback action bridge;
- no direct workflow/docstatus mutation;
- no accounting posting in this foundation.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.
