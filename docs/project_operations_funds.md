# RetailEdge Project Operations & Project Funds

## Stack dependency

This work remains intentionally stacked on PR #42 (`agent/advanced-payment-management`). ERPNext remains authoritative throughout.

## Business goal

Provide an EdgeSuite operational and financial-control layer for project-based businesses without creating parallel project, task, budget, purchasing, stock, cash or accounting ledgers.

## Sources of truth

- **ERPNext Project** — identity, company/customer, progress, sales value, billing, purchase cost, consumed-material cost, timesheet costing and gross margin.
- **ERPNext Task** — project tasks, hierarchy, progress and milestones.
- **ERPNext Budget** — Project-targeted budgets and native Stop/Warn/Ignore spend controls.
- **ERPNext Payment Entry** — submitted project-linked cash movements.
- **ERPNext Sales/Purchase/Stock documents** — operational transactions.
- **ERPNext GL / Payment Ledger / Stock Ledger** — final accounting, settlement and stock truth.

Submitted accounting documents are never mutated by RetailEdge.

## Project and Branch context

Project search is permission-aware and bounded. Branch is a smart EdgeSuite Link field filtered by the selected Project Company and RetailEdge branch-access rules. Changing Project clears stale Branch state. Project Receipt inherits the validated selected Branch as read-only context.

Branch scope applies only to branch-attributed Payment Entries and timeline documents. ERPNext Project totals, Task/Milestone records and Project Budgets remain whole-project values. Documents without usable Branch attribution are omitted from Branch-scoped timeline results rather than widening scope.

## Project cash semantics

`Project Cash In`, `Project Cash Out` and `Net Project-linked Cash` are derived from submitted Payment Entries carrying the Project dimension. They are cash movement measures, not revenue, expense, profit, bank balance or a RetailEdge wallet balance.

Legacy API aliases remain temporarily available for compatibility, but map to the same project-linked Payment Entry movements.

## Project cost semantics

`Tracked Cost` is the transparent sum of distinct ERPNext Project fields:

1. purchase cost;
2. consumed material cost;
3. timesheet costing.

Each component is exposed separately. RetailEdge does not post a separate expense or recalculate accounting truth.

## Tasks and milestones

Project Operations reads native ERPNext `Task` records filtered by Project, excludes templates, respects Task read permission and bounds results. Milestones use the native `is_milestone` flag. Users with Task create permission can open native Task creation with the Project prefilled.

## Project Budget governance

Project Operations reads ERPNext `Budget` records where `budget_against = Project`, scoped by Project and Company. It exposes draft/submitted amounts and configured controls for Material Request, Purchase Order, actual expenses and cumulative expense.

RetailEdge never duplicates or bypasses ERPNext Budget Stop/Warn/Ignore enforcement. New budgets open the native ERPNext Budget form.

## Project receipts

`Record Project Receipt` creates a **draft** standard ERPNext Receive Payment Entry. Server-side validation enforces Project Customer, Project Company, Project dimension, optional validated Branch, company-currency support, Mode of Payment/account resolution and normal Frappe permissions. RetailEdge never auto-submits the Payment Entry or writes GL directly.

## Spend, procurement and materials

The route provider exposes only installed native DocTypes the current user can create. Supported routes include, where installed and permitted:

1. Material Request — plan/request project materials;
2. Purchase Order — order project goods/services;
3. Purchase Receipt — receive project materials/goods;
4. Purchase Invoice — book supplier/service/project cost;
5. Stock Entry — consume/transfer project materials;
6. Expense Claim — employee reimbursement when HRMS is installed;
7. Journal Entry — accounting-adjustment fallback only.

Project/Company/Cost Center defaults are supplied only where the installed parent DocType supports those fields. The route provider never creates, inserts or submits transactions.

## Reports

### RetailEdge Project Portfolio

Whole-project management view of sales value, billing, project cash movements, native cost components, tracked cost, margin and progress. Cash labels deliberately avoid implying revenue/expense/bank-balance semantics.

### RetailEdge Project Financial Control

Whole-project control report combining:

- submitted Project Budget when readable;
- sales/order and billed values;
- submitted Sales Invoice receivable outstanding;
- submitted Purchase Invoice payable outstanding;
- Project Cash In/Out and net project-linked cash;
- purchase/material/timesheet costs and Tracked Cost;
- budget remaining against tracked cost;
- ERPNext Project gross margin.

Branch filtering is intentionally not offered because mixing branch-scoped cash with whole-project billing, AR/AP, costing and margin would be misleading.

## Safety rules

- No custom Project Funds balance DocType.
- No direct GL, Payment Ledger or Stock Ledger writes.
- No direct submitted-document mutation.
- No bypass of ERPNext Budget enforcement.
- No broad Branch widening when attribution is unavailable.
- No project-linked cash presented as revenue, expense, profit or bank balance.
- Permission-aware, bounded reads only.
- Optional HRMS/ERPNext routes are exposed only when installed and permitted.
