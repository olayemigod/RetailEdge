# RIR2F3F31 — Business Expense Accounting Posting + Expense Register De-duplication

## Goal

Complete the direct Business Expense lifecycle by adding a separately gated EdgeSuite **Post to Accounts** action after approval, while preserving ERPNext Journal Entry and GL Entry as the accounting truth.

The slice also makes a posted Business Expense a first-class row in the consolidated Expense Register and suppresses the linked Journal Entry expense line so the same spend is not shown twice.

## Business boundary

- Business Expense is for direct non-POS spend that has already been paid from a Cash or Bank account.
- Supplier credit bills remain Purchase Invoice.
- Employee reimbursements remain Expense Claim where installed.
- Cashier Expenses remain their separate POS/shift workflow.
- Generic/manual Journal Entries remain Accounting Adjustment rows in Expense Register unless they are explicitly linked to a Business Expense.
- No submitted accounting document is mutated.

This slice does not turn Business Expense into a supplier-payables or employee-reimbursement workflow.

## Posting eligibility

The accounting action is available only when all of the following are true:

- Business Expenses are enabled.
- Business Expense accounting posting is enabled.
- the configured posting document type is Journal Entry;
- the Business Expense is submitted;
- when no active Frappe Workflow exists, Expense Status is Approved/Pending Ledger and Ledger Status is Pending Ledger;
- when an active Frappe Workflow exists, the document is in the configured **Workflow State Allowed for Accounting Posting**, and that state is a submitted (`doc_status = 1`) state of the active Workflow;
- amount is greater than zero;
- Company and Branch remain inside the current user's operational scope;
- Expense Account remains an active leaf Expense account in the Company;
- Paid From remains an active leaf Cash or Bank account in the Company;
- Cost Centre and Project remain valid for the Company when supplied;
- both posting accounts use the Company's default currency;
- the user has an allowed Business Expense posting role;
- the user has write permission on the Business Expense;
- the user has normal ERPNext Journal Entry read, create and submit permissions;
- no unresolved accounting reference is already linked.

The foreign-currency guard is intentional. Business Expense currently stores an amount in Company currency and does not capture exchange-rate semantics. A multi-currency posting therefore fails closed rather than inventing an exchange rate.

## Active Frappe Workflow posting gate

Frappe Workflow remains authoritative. The RetailEdge fallback statuses are evaluated only when no active Workflow exists.

When an active Workflow controls `RetailEdge Business Expense`, RetailEdge Settings must name the exact **Workflow State Allowed for Accounting Posting**. The configured state must belong to that active Workflow and must have `doc_status = 1`. Posting is blocked if the setting is blank, stale, belongs to another Workflow, or the document is in a different state.

The Settings Link field is filtered to submitted states from the active Business Expense Workflow, and the same relationship is revalidated server-side.

Accounting finalisation updates ledger/posting metadata but never directly writes the active Workflow state field.

## Concurrency and idempotency

Posting acquires a database row lock on the Business Expense before re-reading its state.

The server then checks any existing posting reference before the stale-version check:

- if the same Business Expense already points to a submitted Journal Entry, a repeated request returns that existing result as idempotent and creates nothing;
- if a reference exists but is missing, cancelled, draft, or not a Journal Entry, posting is blocked for accounting review;
- if there is no submitted reference, the displayed `modified` value must still match before posting continues.

This protects double-click, retry, concurrent-request, and stale-screen cases.

No manual database commit is used.

## ERPNext Journal Entry mapping

The server creates a normal ERPNext Journal Entry and submits it through normal permissions.

Debit line:

- Account = Business Expense Expense Account
- Debit = Business Expense Amount
- Cost Centre = Business Expense Cost Centre when supplied
- Project = Business Expense Project when supplied

Credit line:

- Account = Business Expense Paid From Cash/Bank account
- Credit = Business Expense Amount

The Journal Entry uses:

- Company = Business Expense Company
- Posting Date = Business Expense Date
- a source-identifying user remark
- `retailedge_branch` when that field already exists on Journal Entry

The slice does not add a Journal Entry custom field merely for posting.

ERPNext validation and submission remain authoritative. RetailEdge does not create GL Entry directly and does not bypass accounting permissions.

## Source finalisation

Only after ERPNext confirms the Journal Entry is submitted does RetailEdge update the operational Business Expense with:

- Posting Reference Type = Journal Entry
- Posting Reference = submitted Journal Entry name
- Posting Ready = No
- Ledger Status = Posted
- Expense Status = Posted only when the RetailEdge fallback lifecycle owns that field

If Journal Entry insert or submit fails, the source is not marked Posted and no posting reference is finalised.

The Business Expense is operational metadata, not the accounting ledger. Updating these post-result fields does not mutate the submitted Journal Entry or its GL truth. When an active Frappe Workflow controls the document, RetailEdge never directly assigns that Workflow's state field during accounting finalisation.

Once a posting reference exists or Ledger Status is Posted, the Business Expense becomes terminal for workflow progression. The workflow bridge rejects further actions and workflow readiness suppresses transitions even when an active Frappe Workflow would otherwise advertise one. Corrections must use the approved accounting reversal process rather than reopening a posted operational record.

## EdgeSuite experience

The Business Expenses detail view now shows an Accounting Posting card for submitted records.

It displays:

- readiness;
- blocking reasons;
- permission availability;
- existing accounting reference after posting.

Eligible users receive a **Post to Accounts** button. The UI requires an explicit confirmation that a Journal Entry will be submitted and sends the current Business Expense `modified` value for stale protection.

The action stays inside EdgeSuite. It does not open the native Business Expense form.

## Expense Register

The consolidated Expense Register now includes `Business Expense` as a first-class source.

A posted Business Expense appears using its own operational context:

- original Expense Date;
- Branch;
- Expense Category;
- Amount;
- Description;
- Expense Account;
- Cost Centre;
- Paid From;
- Business Expense source reference.

Only submitted Business Expenses with Ledger Status = Posted whose linked Journal Entry still exists and is submitted are eligible for this posted-truth row. Expense Status is deliberately not used as a posting-truth predicate because an active Frappe Workflow may retain its configured submitted state after accounting finalisation.

The corresponding Journal Entry expense GL row is excluded through the posting-reference join. Generic Journal Entries not linked to a Business Expense continue to appear as Accounting Adjustment.

Business Expense source references route back to the EdgeSuite Business Expenses owner rather than the native DocType.

## Accounting safety

F3F31 does not:

- create GL Entry directly;
- use `ignore_permissions`;
- manually commit a transaction;
- mutate a submitted Journal Entry;
- alter or cancel a submitted accounting document;
- create a replacement for a broken/cancelled posting reference;
- post Supplier credit bills;
- post Expense Claims;
- change Cashier Expense posting behavior;
- introduce percentage allocation, tax, advance, accrual, or multi-currency semantics.

A correction to a posted Business Expense must use the approved accounting reversal/cancellation process in a later bounded slice. The source cannot be silently rewritten into different accounting truth.

## Migration and backward compatibility

F3F31 adds the **Workflow State Allowed for Accounting Posting** field to RetailEdge Settings. A normal site migration is required to install this additive setting.

The existing Business Expense DocType already contains:

- posting reference type;
- posting reference;
- posting readiness;
- posting block reason;
- expense and ledger states.

RetailEdge Settings already contains:

- Business Expense accounting-posting enablement;
- posting document type;
- Workflow State Allowed for Accounting Posting for active Frappe Workflow deployments.

Existing unposted Business Expenses are unchanged. Existing accounting vouchers remain unchanged. The Expense Register continues to use posted ERPNext accounting as financial truth.

## Tests required

Automated contract coverage verifies:

- row locking;
- stale protection;
- idempotent replay;
- normal Journal Entry insert/submit lifecycle;
- no permission bypass;
- no direct GL creation;
- balanced debit/credit mapping;
- company-currency fail-closed behavior;
- Business Expense first-class register rows;
- linked Journal Entry GL de-duplication;
- preservation of category/branch/account context;
- EdgeSuite Post to Accounts confirmation;
- EdgeSuite ownership of Business Expense register references;
- additive Workflow posting-state configuration and normal site migration.

The full governed exact-head gates remain:

1. RetailEdge Theme Compatibility
2. Linters
3. clean Frappe v16 standalone CI
4. EdgeSuite UI Candidate Compatibility

## Manual QA at consolidated RIR2E acceptance

Validate at least these personas and paths:

1. Accounts/manager user posts an approved Pending Ledger Business Expense and sees one submitted Journal Entry.
2. Double-click/retry does not create a second Journal Entry.
3. A stale Business Expense screen is blocked before new posting.
4. A user without Journal Entry submit permission does not see a usable post action and cannot call the API successfully.
5. Restricted Branch user cannot post an out-of-scope Business Expense.
6. Expense Account debit and Cash/Bank credit equal the Business Expense amount.
7. Cost Centre and Project flow to the debit line when present.
8. Posted Business Expense appears once in Expense Register.
9. The linked Journal Entry expense GL line does not appear as a second row.
10. Clicking the Business Expense source returns to Business Expenses in EdgeSuite.
11. A generic unlinked Journal Entry still appears as Accounting Adjustment.
12. Foreign-currency posting fails closed instead of assuming an exchange rate.
13. A broken, draft, or cancelled existing posting reference blocks automatic reposting.

## Risks and deferred work

- Accounting reversal/unposting of a posted Business Expense is deliberately not implemented here.
- Multi-currency direct Business Expense posting is deferred until explicit currency and exchange-rate semantics are designed.
- Tax-inclusive or tax-exclusive expense capture is not introduced.
- Supplier payable creation remains Purchase Invoice, not Business Expense.
- Cashier Expense ledger posting remains a separate contract.
- Browser/persona QA remains deferred to consolidated RIR2E acceptance.

## Next

After F3F31 passes all governed exact-head gates, continue with the next smallest F3 slice required by the RetailEdge MVP contract without widening accounting semantics or reopening frozen expense ownership decisions.
