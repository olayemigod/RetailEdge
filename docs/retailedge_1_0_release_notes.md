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

## Acceptance evidence

PR #56 formal RC3 was accepted on exact post-audit-freeze SHA `099e4a30b2c8a25c2ca0858caa6bcbfe99a8b98c`. Browser Persona workflow run #234 completed **24/24 PASS** and retained evidence artifact `10357567550`. On the same exact head, Theme Compatibility #1121, Linters #2962, clean Frappe v16 CI #2983, EdgeSuite UI Candidate Compatibility #1218, and Upgrade Validation #128 were all green.

The second MVP audit is frozen at commit `1bd01c39d7a574df85773aae86fec7a144a98698`, backed by validated implementation head `aea2cf4980cfd2dc2b61133ee567f166392a7285`.

The final `v1.0.0` tag must point to the merged/promoted `version-16` release commit after the release-hardening head passes the complete final gate set.
