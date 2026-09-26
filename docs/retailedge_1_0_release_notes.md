# RetailEdge 1.0.0 — Release Notes

## Release purpose

RetailEdge 1.0.0 is the first governed MVP release for day-to-day retail operations on Frappe / ERPNext v16. It is designed for Nigerian and African SME retail operations while retaining ERPNext accounting, stock and document lifecycle authority.

## What is in 1.0

### Business Hub and control

- Business Hub command centre with eight actionable indices: Sales, Cash, Stock, Expenses, Receivables, Payables, Branch Performance and Banking, plus prioritised Attention signals
- permission-aware quick actions and searchable Create
- Action Centre for operational follow-up
- shared EdgeSuite navigation, appearance and keyboard ownership

### Selling and customer money

- Professional Selling
- customer receivables
- customer payments, advances and mixed settlement
- standard guided completion paths while ERPNext remains authoritative
- deliberate advanced-native boundaries for specialist accounting cases

### Purchasing and supplier money

- Professional Purchasing
- receiving and Purchase Invoice continuation
- supplier payables
- supplier payment handoff/completion
- supplier document review and controlled advanced fallback

### Expenses and cash control

- Cashier/POS Expense for shift-linked cashier spending
- Business Expenses for non-POS operating expenses
- Expense Register and review visibility
- cash movement, cash deposit and shift verification controls

### Stock

- Stock Position and Stock Movement History
- guided Stock Transfer and Stock Adjustment
- standard EdgeSuite completion continuity
- branch/warehouse-safe defaults and validation

### Banking

- Banking Setup & Readiness
- Bank Matching & Reconciliation
- statement/match review controls
- permission-safe empty states for personas without native bank transaction/account visibility

### Branch and access governance

- Company/Branch operating context
- Branch Assignment authority with one/multiple/zero-Branch behavior
- server-side revalidation of operational scope
- EdgeSuite-only everyday containment with explicit Native Desk capability for advanced users

### Reporting

MVP reporting includes operational and management visibility for sales, purchases, receivables, payables, stock, expenses, banking/cash, branch performance, salesperson performance and daily review.

## Accounting and stock safety

RetailEdge does not replace ERPNext ledgers.

- ERPNext remains authoritative for GL, Payment Ledger, Stock Ledger, valuation, outstanding balances and submitted document lifecycle.
- Submitted accounting/stock documents are not mutated by RetailEdge corrections.
- Frappe Workflow takes precedence where configured.
- Complex/exceptional cases remain in authorised ERPNext workflows rather than being reimplemented unsafely.

## Known advanced-native boundaries

These are intentional 1.0 boundaries, not release defects:

- complex serial/batch/valuation stock cases;
- specialist Payment Reconciliation and multi-currency accounting;
- exceptional drafts that fail the standard RetailEdge completion contract;
- System Manager-only Branch Assignment/setup governance;
- advanced ERPNext detail/form access for explicitly authorised Native Desk users.

## QA and promotion status

RetailEdge 1.0.0 is **not yet tagged or published**, but the governed MVP candidate has completed its audit and acceptance sequence.

Authoritative release-hardening evidence:

- PR #58 frozen head: `85c1834aedf5a934458a04a706cdc4d10ea0f02f`
- Business Hub → reporting audit: **FROZEN / COMPLETE**
- Theme Compatibility: **PASS**
- Linters / Semgrep / dependency audit: **PASS**
- clean Frappe v16 CI: **PASS**
- EdgeSuite UI Candidate Compatibility: **PASS**
- Upgrade Validation: **PASS**, including double migration and submitted accounting-truth verification
- formal Browser RC3: **31/31 PASS**

Blocker-only findings discovered during the audit/RC3 sequence were corrected and revalidated on the frozen head. Customer Receivables remains a controlled, Company/Branch-scoped RetailEdge view for permitted Sales roles without granting raw Sales Invoice Desk access, while Payment Management remains restricted to accounting-authorised roles because it performs native Payment Entry work.

The remaining step is final promotion approval. No `v1.0.0` tag or GitHub Release should be created until that decision is made. Any code change after the frozen head requires exact-head revalidation before promotion.
