# RetailEdge Workspace Architecture

RetailEdge uses the standard Frappe Workspace and Workspace Sidebar JSON assets synced by `retailedge.workspace_sync.sync_retailedge_workspace_layout` during migrate. The live workspace should expose only existing, safe links. Planned tools are documented here instead of being added as broken shortcuts.

## Link Types

- ERPNext Link: native ERPNext/POSNext source documents or reports that RetailEdge links to without duplicating. Examples: Bank Transaction, Payment Entry, Sales Invoice, Stock Entry, Stock Reconciliation, Item, Warehouse, POS Opening Shift, POS Closing Shift, Stock Ledger, and Stock Balance.
- RetailEdge Native: RetailEdge-owned documents and reports such as Cashier Expense, Daily Sales Audit, Payment Statement Import, Branch Performance Summary, Bank Transaction Matching, Unmatched Bank Transactions, Unmatched Bank Payment Events, Invoice Payment Audit, and Cashier Expense Review.
- RetailEdge Overlay: RetailEdge control/review layers that sit above native ERPNext evidence, such as Bank Match Review, Reconciliation Readiness, and Reconciliation Handoff.

## Live Workspace Sections

1. Operations
2. Review & Approvals
3. Reports & Analytics
4. Accounting / Ledger Bridge
5. Setup / Configuration
6. Admin / Maintenance

## Planned Items Not Exposed Yet

The following targets should remain roadmap/documentation items until implemented as real DocTypes, reports, pages, or safe ERPNext links on the bench:

- Cashier Cash Control, Cashier Sales Board, Cash Declaration, Cash Remittance.
- General Expense, Expense Request, Department Expense, Expense Approval Queue, Expense Clarification Queue.
- Bank Reconciliation Tool link, Reconciliation Preflight page, Reconciliation Execution Log.
- Stock Overview Board, Item Availability Lookup, Stock Count Planning, Stock Transfer Request, Reorder Request.
- Stock Exception Center, Stock Count Review, Stock Variance Review, Stock Adjustment Approval Queue, Damaged Stock Review, Expired Stock Review, Negative Stock Exception Review.
- Branch Stock Health, Item Sales vs Stock Velocity, Reorder Recommendation Report, Fast / Slow / Dead Stock Report, Expiry / Near-Expiry Report, Stock Movement Timeline.
- Journal push queues, failed journal push repair, stock ledger bridge queues, and stock action logs.
- Branch Attribution Check, Bank Match Repair, Candidate Drift Repair, Queue Release Tool, and other admin repair tools unless/ until a safe implemented target exists.

## Guardrails

RetailEdge must not duplicate ERPNext source-of-truth modules. Bank Transaction, stock ledger documents, accounting entries, Sales Invoice, and Payment Entry remain ERPNext/POSNext sources. RetailEdge should expose intelligence, review queues, operational controls, and safety overlays only where implemented.
