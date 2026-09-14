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

## QA status

RetailEdge 1.0.0 is **not yet released**.

Business Hub QA is still in progress. The automated browser runs recorded during PR #56 hardening are regression evidence only and must not be treated as completed Business Hub QA or full RetailEdge MVP RC3 acceptance.

Full MVP QA remains required after Business Hub acceptance, including selling, purchasing/Receive Stock, payments/cash/banking, expenses, stock operations, Action Centre, receivables/payables, reporting, role/persona access, Branch isolation, workflow behaviour, and ERPNext accounting/stock safety.

PR #56 was merged to `version-16` before QA completion. That merge represents code integration only; it does **not** represent product acceptance or permission to tag `v1.0.0`.

No release tag or GitHub Release should be created until the complete QA sequence is finished and frozen.
