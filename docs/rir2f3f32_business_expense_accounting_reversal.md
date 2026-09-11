# RIR2F3F32 — Business Expense Accounting Reversal

## Goal

Provide an accounting-safe correction path for a posted direct Business Expense without cancelling, editing, or otherwise changing the original submitted accounting entry.

F3F32 uses a separate reversing accounting entry and preserves both legs as permanent audit history.

## Business boundary

This slice applies only to the direct Business Expense posting flow introduced in F3F31.

It does not change:

- Supplier credit bills / Purchase Invoice;
- Expense Claim;
- Cashier Expense;
- bank reconciliation;
- tax handling;
- accrual accounting;
- multi-currency semantics;
- partial corrections.

A Business Expense reversal is a full reversal of the original direct paid-spend posting.

## Accounting truth

The original submitted Journal Entry is never cancelled or edited by F3F32.

A reversal creates a **new submitted Journal Entry** with the inverse accounting effect:

Original posting:

- Debit Expense Account
- Credit Paid From Cash/Bank account

Reversal posting:

- Debit Paid From Cash/Bank account
- Credit Expense Account

The reversal keeps the same Company and Branch attribution. Cost Centre and Project are carried on the reversing Expense Account line when present.

RetailEdge never creates GL Entry directly, never uses `ignore_permissions`, and never manually commits the transaction.

## Reversal eligibility

A Business Expense can be reversed only when:

- the source document is submitted;
- Ledger Status is Posted;
- the original Posting Reference is a submitted Journal Entry;
- no submitted reversal already exists;
- Company and Branch remain inside current operational scope;
- the current user has an allowed accounting role;
- the current user can write the Business Expense;
- the current user has normal Journal Entry read, create and submit permissions;
- the original Journal Entry still matches the exact two-line RetailEdge direct-spend posting contract.

If an existing reversal reference is draft, cancelled, missing, or otherwise inconsistent, automatic reversal fails closed for accountant review.

## Original-posting integrity check

Before automatic reversal, RetailEdge re-reads the original submitted Journal Entry and verifies:

- Company matches the Business Expense;
- the entry has exactly two account rows;
- one row debits the Business Expense Expense Account for the full Business Expense amount;
- one row credits the Business Expense Paid From account for the same amount;
- Cost Centre matches when the Business Expense specifies one;
- Project matches when the Business Expense specifies one;
- Branch matches when the Journal Entry has the RetailEdge Branch field.

If any of those assumptions no longer hold, RetailEdge does not guess or create a compensating entry.

## Reversal date

The user must provide an explicit Reversal Posting Date.

The reversal date cannot be before the original accounting posting date. ERPNext remains authoritative for fiscal-period, frozen-accounting, and other posting-date validation.

## Mandatory reason

A reversal reason is required.

The reason is:

- stored on the Business Expense reversal audit metadata;
- included in the reversing accounting entry remark;
- shown in the EdgeSuite Business Expenses detail.

## Concurrency and idempotency

The reversal action:

1. locks the Business Expense row;
2. re-reads the current source state;
3. returns the existing submitted reversal as an idempotent success when one already exists;
4. checks the displayed `modified` value before a new reversal;
5. revalidates access and accounting structure;
6. creates and submits the new reversal;
7. updates source reversal metadata only after successful accounting submission.

Double-clicks and retried requests therefore do not create duplicate reversing entries.

## Business Expense audit metadata

F3F32 adds additive submitted-document fields:

- Reversal Reference Type
- Reversal Reference
- Reversal Posting Date
- Reversal Reason
- Reversed By
- Reversed On

Ledger Status gains **Reversed**.

For the RetailEdge fallback lifecycle, Expense Status may also become Reversed. When an active Frappe Workflow controls the document, RetailEdge does not directly write the Workflow state field.

A server-side document validation guard also blocks any later native Frappe Workflow state change once an original Posting Reference exists. This makes the posted/reversed Business Expense terminal even when a privileged user reaches the native document surface.

The original Posting Reference is never removed or replaced.

## EdgeSuite experience

The Business Expenses detail page remains the operational owner.

For an eligible posted Business Expense it exposes **Reverse Accounting**.

The action opens a controlled dialog that requires:

- Reversal Posting Date;
- Reversal Reason.

The dialog explains that the original accounting entry remains unchanged.

After reversal, the detail page shows:

- original accounting reference;
- reversal accounting reference;
- reversal date;
- reversal reason.

No routine native Journal Entry handoff is introduced.

## Expense Register

Expense Register preserves both accounting legs as first-class business context:

1. the original Business Expense appears as a positive posted expense;
2. the reversal appears as a negative **Business Expense Reversal** row.

The original row remains visible after reversal because Ledger Status Reversed does not erase historical posting truth.

Both linked Journal Entry GL expense lines are suppressed from the generic accounting half of Expense Register:

- original Posting Reference GL line is de-duplicated;
- Reversal Reference GL line is de-duplicated.

The two first-class Business Expense rows therefore net to zero while retaining audit visibility.

The existing **Business Credits / Reversals** summary naturally captures the negative reversal amount.

## Status filtering

Financial status semantics remain explicit:

- Status = Posted selects the original positive Business Expense row;
- Status = Reversed selects the negative Business Expense Reversal row;
- blank Status includes both when applicable.

The raw active Frappe Workflow state is not used as financial posting truth.

## Migration and backward compatibility

F3F32 is additive.

A normal site migration is required to install the new Business Expense reversal audit fields and the new Reversed status options.

Existing Business Expenses and accounting vouchers are not rewritten.

Existing F3F31 posted records become eligible for reversal after migration if their original posting still satisfies the exact posting contract.

## Accounting safety

F3F32 does not:

- cancel the original Journal Entry;
- edit the original Journal Entry;
- create GL Entry directly;
- use `ignore_permissions`;
- manually commit;
- clear or replace the original Posting Reference;
- automatically recreate a broken accounting reference;
- reverse only part of an expense;
- edit and repost the original Business Expense;
- introduce multi-currency conversion assumptions.

If the original posting no longer matches the strict RetailEdge posting contract, the automatic reversal is blocked for accountant review.

## Tests required

Automated contract coverage verifies:

- additive reversal metadata;
- Reversed source status support;
- row locking;
- stale-state protection;
- idempotent replay;
- mandatory reason;
- original submitted Journal Entry preservation;
- exact two-line original-posting validation;
- inverse debit/credit mapping;
- Cost Centre, Project and Branch preservation;
- reversal-date ordering;
- normal Journal Entry permissions;
- no direct GL write;
- no cancellation of the original entry;
- no manual commit;
- active Frappe Workflow state preservation;
- positive original + negative reversal Expense Register composition;
- de-duplication of both linked Journal Entry GL rows;
- EdgeSuite-controlled reversal dialog;
- migration requirement.

The governed exact-head gates remain:

1. RetailEdge Theme Compatibility
2. Linters
3. clean Frappe v16 standalone CI
4. EdgeSuite UI Candidate Compatibility

## Manual QA at consolidated RIR2E acceptance

Validate at least:

1. eligible accounts/manager user can reverse a posted Business Expense;
2. reason and posting date are mandatory;
3. reversal before original posting date is blocked;
4. original Journal Entry remains submitted and unchanged;
5. exactly one new submitted reversing Journal Entry is created;
6. double-click/retry does not create a second reversal;
7. user without Journal Entry submit permission cannot reverse;
8. restricted Branch user cannot reverse an out-of-scope Business Expense;
9. Cost Centre and Project remain on the reversing expense line;
10. Expense Register shows one positive Business Expense and one negative Business Expense Reversal;
11. neither linked Journal Entry expense GL line appears as a duplicate generic adjustment;
12. the net financial effect is zero;
13. active Frappe Workflow state remains unchanged;
14. fallback lifecycle displays Reversed;
15. a structurally changed or broken original posting fails closed.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.

## Out of scope / next boundaries

- partial reversal is out of scope;
- replacement/edit-after-reversal is out of scope;
- supplier-credit corrections remain Purchase Invoice accounting;
- Cashier Expense correction remains its own workflow;
- multi-currency reversal remains outside the direct-spend contract.

F3F32 should freeze only after all four governed exact-head gates pass.
