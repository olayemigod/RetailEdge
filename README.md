# RetailEdge

RetailEdge is a retail operations app for Frappe / ERPNext v16 that is designed to work alongside POSNext. It provides a clean foundation for POS control, sales audit, payment verification, branch workflows, and future retail intelligence capabilities without modifying Frappe, ERPNext, or POSNext core files.

## Target Stack

- Frappe / ERPNext v16
- POSNext-compatible

## V0.1A Scope

V0.1A establishes the first installable application foundation for RetailEdge.

### Implemented in V0.1A

- RetailEdge app foundation
- RetailEdge Settings single DocType
- Cost price role restriction foundation
- Minimal RetailEdge workspace
- Backend utility and API foundation for cost visibility context

### Planned Next

- Hide Cost Price for Selected Roles
- Branch & Payment Defaults
- Sales Invoice Audit Intelligence
- Payment Verification Engine
- Daily Sales & Payment Audit
- Pending Verification Report
- Audit Variance Dashboard
- Cashier Expense Workflow
- Retail Intelligence and AI later

## Important Product Decision

Editable selling price is intentionally not implemented in RetailEdge. POSNext already supports editable selling price natively, so RetailEdge does not add settings, hooks, UI logic, or backend overrides for that behavior.

## Legacy Report Migrated

POS Closing Variance vs Expenses has been migrated from the old ProcessEdge POSNext Extension app into RetailEdge. In V0.1B it remains legacy-compatible so existing users can still recognize and use it without a redesign.

This report currently focuses on POS Closing Shift variance versus same-day expense GL Entries. It does not yet audit all Sales Invoices, and it is not yet the broader Daily Sales & Payment Audit system.

In later RetailEdge phases, this legacy report foundation will be upgraded into the wider Audit Variance Dashboard and Daily Sales & Payment Audit flow.

RetailEdge still does not implement editable selling price because POSNext already supports it natively.

## CoreEdge Readiness

RetailEdge can run in standalone mode or in an integrated mode with CoreEdge. When CoreEdge is installed and enabled, RetailEdge will be able to consume shared platform services without taking a hard install-time dependency on CoreEdge.

Planned CoreEdge services for RetailEdge include:

- app access and entitlements
- login and identity context
- app launcher integration
- branch context
- payment gateway and payment requests
- notifications and a future notification wallet

V0.1C only adds the adapter foundations for these integrations. Full payment gateway behavior, entitlements, and notification wallet features will be implemented in CoreEdge later and consumed by RetailEdge through these adapters.

Portal payment flows should call `retailedge.api.create_payment_request_for_sales_invoice` and must never expose gateway secrets directly to portal users.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Posting Date Control

RetailEdge can optionally restrict POS backdating through RetailEdge Settings. When posting date control is enabled, Administrator and System Manager can always override, and additional allowed roles can be configured in RetailEdge Settings.

V0.2 only adds safe backend validation and frontend context foundations for posting date control. In this phase, only backdated POS Sales Invoices are blocked for unauthorized users; normal non-POS Sales Invoices are not affected.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Hide Cost Price for Selected Roles - V0.3A Desk UI Protection

RetailEdge can hide cost and valuation related fields from selected roles in ERPNext Desk forms. The feature is controlled from RetailEdge Settings, and System Manager plus Administrator remain unrestricted.

V0.3A only adds Desk form UI protection. It is not the full security layer yet, and backend, API, and report protection will come in later V0.3 phases. POSNext-specific UI hiding will also come later.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense Structure Reset

RetailEdge Cashier Expense has been recreated as a clean structure-only DocType foundation. The earlier workflow-heavy implementation was removed so the app has a normal Frappe DocType that can save reliably, appear in list view, and support later phases without carrying broken behavior forward.

RetailEdge Expense Category exists so cashiers can work with friendly categories instead of choosing ERPNext expense accounts directly. In this reset phase, the data model is ready for later validation and autofill work, but the workflow, approval, posting, and role-specific behavior are intentionally deferred.

This phase does not add autofill logic, approval workflow, Journal Entry creation, Payment Entry creation, Daily Sales Audit integration, or advanced permission logic. Those capabilities will be layered onto this clean structure in later phases.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense V1.4B - Auto-fill + Shift Cash Control

RetailEdge Cashier Expense now expects an open POS Opening Shift by default before a cashier records an expense. When a shift is available, RetailEdge auto-fills the cashier, company, POS Profile, linked opening shift, cost center, and cash payment account where those values can be safely resolved from the current POS context.

Expense Date defaults to today, and date editability is controlled by RetailEdge Settings through `Allow Cashier Expense Date Editing`. RetailEdge also performs operational shift-cash control by comparing the current expense against the opening shift cash context and prior non-cancelled cashier expenses already linked to the same opening shift.

This V1.4B phase does not create Journal Entries or Payment Entries, does not update Account or GL balances, and does not mutate Sales Invoice, Payment Entry, or Daily Sales Audit records. Closing Shift linkage is filled later when the matching POS Closing Shift is created or submitted. Ledger posting behavior and variance report integration remain later phases.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense V1.4C - Submit, Review, and Pending Ledger

RetailEdge Cashier Expense now supports a lightweight submit and review lifecycle without introducing any accounting posting. Draft expenses can be submitted, reviewers can move Submitted expenses to Pending Ledger, reject them, or reopen Rejected and Pending Ledger expenses back to Submitted for another review pass.

Pending Ledger means the expense has been reviewed and approved operationally, but ledger posting is still deferred to a later phase. This phase does not create Journal Entries or Payment Entries, does not modify POS Opening Shift cash balances directly, and does not change Sales Invoice, Payment Entry, POS Closing Shift totals, or Daily Sales Audit records.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense V1.4D - Cash Sales Resolution for Shift Cash Control

RetailEdge now attempts to resolve cash sales from the active POS shift when calculating available shift cash for cashier expenses. The preferred source on supported schemas is submitted POS `Sales Invoice` payment rows, using only payment lines that match Cash mode or the resolved cash payment account.

Mixed payments are handled safely by summing only the cash portion of each invoice. Cancelled invoices and non-cash payment rows are excluded. If RetailEdge cannot safely resolve cash sales for the local POS schema, it keeps the warning and falls back to opening cash minus prior cashier expenses instead of guessing from invoice grand totals.

This phase only reads and calculates cash sales. It does not post ledger entries, and it does not modify invoices, payments, shifts, Daily Sales Audit, or GL balances.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense V1.4E - Variance Report Integration

RetailEdge Cashier Expenses are now available for variance reporting. The variance view reuses the V1.4D shift cash snapshot formula of `Opening Cash + Cash Sales - Cashier Expenses`, so non-cancelled cashier expenses can be seen operationally even before ledger posting exists.

Draft, Submitted, Pending Ledger, Rejected, and Posted expenses can all be included in reporting, while Cancelled expenses are excluded. This phase does not create Journal Entries or Payment Entries, does not modify account balances, and does not change POS Opening Shift or POS Closing Shift totals. Ledger posting remains a later phase.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense V1.4F - Ledger Posting Preparation

RetailEdge can now preview future ledger posting for cashier expenses without creating any accounting documents. The posting preview resolves the expected debit account, credit account, amount, posting date, and cost center, and stores posting readiness directly on the cashier expense for later posting phases.

This phase does not create Journal Entries or Payment Entries, and it does not modify GL balances, Sales Invoices, POS shifts, or Daily Sales Audit data. Actual accounting posting remains a later phase after readiness validation is complete.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense V1.4G - Hardening, Audit Trail, and UX Cleanup

RetailEdge Cashier Expense now keeps an action history so important transitions such as submit, approve, reject, reopen, cancel, and posting-readiness refresh are traceable on the expense itself. Reviewer role checks support both spaced and compact RetailEdge role names, and Desk buttons are restricted by both document status and user role.

Posting preview and posting readiness remain available, but actual ledger posting is still not implemented in this phase. No Journal Entry or Payment Entry is created, variance helpers remain read-only, cancelled expenses stay excluded from variance visibility, and rejected expenses remain visible for management review by default.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense V1.4H - Daily Audit Readiness and Controlled Inclusion Rules

RetailEdge Cashier Expense can now be classified for future Daily Audit review without mutating Daily Sales Audit itself. Managers and reviewers can mark a cashier expense as Included, Excluded, or Needs Clarification, and those actions are stored on the expense together with review metadata and action history.

Rejected expenses remain visible for Daily Audit readiness by default because they may still represent physical cash movement, while cancelled expenses are excluded by default. This phase does not mutate Daily Sales Audit, does not deduct expenses from audit totals, and does not create Journal Entries or Payment Entries.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense V1.4I - Manager Review Report

Managers and auditors now have a read-only `RetailEdge Cashier Expense Review` report that consolidates cashier expense status, posting readiness, Daily Audit readiness, branch/POS/cashier context, and exception visibility in one place. The report is intended as an operational review layer and does not perform approvals, posting, or audit mutation by itself.

This phase does not post accounting entries, does not modify Daily Sales Audit, and does not change POS shifts, Sales Invoices, or payment records. It only surfaces existing cashier expense review data in a safer manager-facing report.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Cashier Expense V1.4J - Workspace UX and Dashboard Cards

The RetailEdge workspace now surfaces cashier expense review tools more clearly, including direct access to cashier expenses, expense categories, the manager review report, the variance report, and RetailEdge Settings. Managers and auditors can also use a read-only dashboard summary helper to view cashier expense totals, review-state counts, posting readiness counts, Daily Audit readiness counts, top cashiers, top categories, and recent expenses.

This phase remains read-only. It does not create accounting entries, does not mutate Daily Sales Audit, and does not modify POS shifts, Sales Invoices, payment verification, or other ERPNext transaction records.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Daily Sales Audit V1.5A - Foundation

RetailEdge now includes a `RetailEdge Daily Sales Audit` control document as the foundation for later audit phases. The document captures a refreshable, read-only snapshot of shift context, sales and payment lines, cashier expense lines, expected cash, actual closing cash, and variance context for the selected company, branch, POS Profile, cashier, and shift combination.

This phase is limited to settings, DocTypes, draft audit creation, refreshable preview helpers, and a read-only register report. It does not verify invoices, does not verify payments, does not modify Sales Invoices, does not modify POS Opening or POS Closing Shift records, and does not create Journal Entries or Payment Entries. Actual audit approval, payment verification, and downstream posting remain later phases.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Daily Sales Audit V1.5A.1 - Context Autofill and Smart Filters

The Daily Sales Audit form now narrows POS Profile, cashier, opening shift, and closing shift choices based on the context the reviewer has already selected, such as company, branch, POS Profile, cashier, audit date, and shift links. Selecting a POS Opening Shift or POS Closing Shift can also autofill company, branch, POS Profile, cashier, and audit date where the local schema makes that context safely resolvable.

This behavior is schema-safe and read-only. RetailEdge inspects available fields before applying filters or defaults, skips missing schema pieces instead of failing, and does not modify any Sales Invoice, POS shift, Payment Entry, GL, or other source transaction document in this phase.

RetailEdge does not implement editable selling price because POSNext already supports it natively.

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench --site core.local install-app retailedge
bench --site core.local migrate
bench build --app retailedge
bench --site core.local clear-cache
bench restart
```

## License

MIT
