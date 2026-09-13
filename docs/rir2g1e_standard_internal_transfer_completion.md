# RIR2G1E — Standard Internal Transfer Completion

## Goal

Close the remaining ordinary EdgeSuite cash-movement dead end by allowing standard Cash Deposit and Cash/Bank Transfer Payment Entry drafts to complete inside EdgeSuite without recreating ERPNext accounting logic.

RIR2G1E owns **completion only**. Existing draft creation remains in:

- `retailedge.cash_custody.create_cash_deposit_draft`;
- `retailedge.guided_cash_transfer.create_simple_cash_transfer_draft`.

ERPNext Payment Entry remains the accounting source of truth.

## Business Boundary

Supported standard drafts:

1. **RetailEdge Cash Deposit**
   - Payment Entry;
   - `payment_type = "Internal Transfer"`;
   - `retailedge_cash_custody_type = "Cash Deposit"`;
   - active cashier/POS shift attribution remains present;
   - Cash posting account → approved company Bank posting account;
   - company currency only.

2. **Cash / Bank Transfer**
   - Payment Entry;
   - `payment_type = "Internal Transfer"`;
   - no RetailEdge custody type;
   - Bank/Cash posting account → different Bank/Cash posting account;
   - company currency only.

No other Payment Entry type is admitted.

## Standard Eligibility

The exact draft must:

- be a readable draft Payment Entry;
- belong to a readable Company;
- pass current operational Branch authority;
- remain an Internal Transfer;
- have no party/party type;
- have no allocation/reference child rows;
- have no deductions;
- have no exchange difference;
- not use separate party-account advances;
- use two different readable enabled non-group posting accounts from the same Company;
- use only Bank/Cash accounts;
- use Company currency on both sides;
- have positive equal paid/received amounts;
- include Reference No when either account is a Bank account.

Anything outside that shape is Advanced ERPNext.

## Cash Deposit Specific Rules

A marked RetailEdge Cash Deposit must additionally:

- retain `retailedge_cashier`;
- retain `retailedge_pos_opening_shift`;
- use a Cash source account;
- use a Bank destination account;
- retain Branch attribution required by the current operational scope;
- retain an approved ERPNext company Bank Account destination;
- remain within available cashier shift cash.

Preview may show the current custody snapshot but does not replace final custody enforcement.

The existing Payment Entry `before_submit` hook:

`retailedge.cash_custody.validate_cash_deposit_before_submit`

remains the authoritative submit-time custody check. It serializes the POS opening shift, rechecks the approved Bank Account destination, and rejects an amount that no longer fits available cash.

RIR2G1E must not duplicate or bypass that hook.

## Preview

Completion preview must be persistence-free and expose:

- Payment Entry and immutable `modified` snapshot;
- transfer kind: Cash Deposit or Cash / Bank Transfer;
- Company and Branch;
- From/To accounts and account types;
- amount/currency;
- current cashier/shift/custody information for a Cash Deposit;
- standard-shape blockers;
- Frappe Workflow readiness;
- whether direct native submit is available.

Preview must not save, insert, submit, commit, create GL rows or mutate custody/source documents.

## No Active Workflow

Direct submit requires:

1. row lock of the exact Payment Entry;
2. immutable snapshot stale check;
3. Company/Branch revalidation;
4. account/currency/amount/standard-shape revalidation;
5. Cash Deposit metadata/custody-context revalidation when applicable;
6. submit permission;
7. confirmation that no active Frappe Workflow owns the document.

RetailEdge then calls only native `doc.submit()`.

ERPNext and existing hooks own:

- Payment Entry validation;
- GL / Payment Ledger posting;
- account balances;
- submit status;
- Cash Deposit custody serialization/recheck.

## Active Frappe Workflow

When a Frappe Workflow owns Payment Entry:

- direct submit fails closed;
- only Frappe-returned `available_actions` are rendered;
- progression delegates through the shared F3F27 workflow bridge;
- immutable `modified` and expected workflow state are supplied;
- EdgeSuite never assigns `docstatus` or `workflow_state`.

Any workflow action that submits the Payment Entry still triggers normal ERPNext hooks, including Cash Deposit `before_submit`.

## UI Ownership

Business Hub must use one shared internal-transfer completion dialog after:

- Deposit Cash draft save;
- Cash / Bank Transfer draft save.

The ordinary EdgeSuite path must not stop at a generic “saved as Draft” notice.

Advanced ERPNext remains available only when Native Desk capability exists.

## Out of Scope

- Customer receipt;
- Supplier payment;
- Payment Entry Pay;
- party allocations;
- Payment Reconciliation;
- deductions/write-offs;
- multi-currency;
- exchange differences;
- Journal Entry;
- bank matching/reconciliation;
- editing submitted Payment Entries;
- cashier shift closing mechanics;
- new schema/custom fields/migrations;
- manual browser/persona acceptance.

## Tests Required

Backend:

1. service accepts Payment Entry only;
2. preview is persistence-free;
3. only draft Internal Transfer is supported;
4. party, references, deductions, exchange difference and party-advance shapes fail closed;
5. From/To accounts must differ;
6. accounts are readable, enabled, non-group, same Company and Bank/Cash only;
7. both account currencies must equal Company currency;
8. paid/received amounts are positive and equal;
9. Bank involvement requires Reference No;
10. current operational Branch authority is revalidated;
11. restricted blank Branch fails closed;
12. Cash Deposit requires cashier/opening-shift attribution;
13. Cash Deposit requires Cash → Bank;
14. Cash Deposit bank destination and current custody are inspected without bypassing submit hook;
15. direct submit row-locks/stale-checks/revalidates and calls only `doc.submit()`;
16. active Workflow blocks direct submit;
17. workflow action row-locks/stale-checks/revalidates and delegates through F3F27;
18. no direct GL/Payment Ledger creation, `ignore_permissions`, manual DB commit or direct status assignment.

UI:

19. Deposit Cash save opens shared internal-transfer completion review;
20. Cash / Bank Transfer save opens the same review;
21. active Workflow displays only server-returned actions;
22. successful completion refreshes Business Hub;
23. Advanced ERPNext is Native-Desk-capability-gated;
24. customer/supplier payment paths remain unchanged.

Regression:

25. Cash Deposit draft creation remains draft-only;
26. Cash / Bank Transfer draft creation remains draft-only;
27. existing Cash Deposit before-submit hook remains installed;
28. Cash Movement continues to report posted GL truth only;
29. RIR2G1D and existing payment tests remain green.

## Safety Rules

- no direct GL Entry or Payment Ledger Entry creation;
- no manual account balance mutation;
- no direct `docstatus` / workflow-state assignment;
- no submitted document mutation;
- no `ignore_permissions`;
- no manual DB commit;
- no schema migration.

## Freeze Rule

RIR2G1E may freeze only when all four governed exact-head gates pass on one SHA:

1. RetailEdge Theme Compatibility;
2. Linters / Semgrep / vulnerable dependency audit;
3. clean Frappe v16 CI;
4. EdgeSuite UI Candidate Compatibility.

After freeze, RIR2G1 must perform one final Phase-2 journey reconciliation before declaring Core Operational Workflows code-complete.
