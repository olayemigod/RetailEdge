# R7 Route Consolidation

## Goal

Make the RetailEdge interface the normal operating surface while preserving ERPNext as the accounting, stock, and document system of record.

## Navigation policy

- Guided Entry is the preferred path for supported high-frequency transactions.
- A permission-aware **Guided + Create** entry is available from the shared RetailEdge product menu on every page where the RetailEdge menu is mounted.
- Guided + Create routes to the Business Hub and opens the existing permission-filtered Create picker.
- Retained native DocType and Query Report destinations are advanced/fallback surfaces and open in a new browser tab so the active RetailEdge workspace remains intact.
- RetailEdge pages continue to navigate in the current tab.
- Native documents, reports, permissions, controllers, workflow rules, accounting, and stock truth are not duplicated or bypassed.
- The old Frappe RetailEdge Workspace is treated as a legacy launcher, not the primary operating navigation surface. Do not add new primary workflows there while Business Hub/product-menu consolidation is active.

## Naming policy

- Do not expose the internal UI framework name in RetailEdge page titles, menu labels, report names, dashboard names, buttons, descriptions, or user messages.
- Use business-facing RetailEdge terminology directly, such as **Daily Sales Audit**, **Expense Review**, and **Cash Shift Verification**.
- Internal package, module, import, API, and framework identifiers remain unchanged where technically required.

## Migration classification

### Promote to RetailEdge pages

- **Cashier Expense Review** -> **Expense Review** (`expense-review`).
- **Cash Shift Verification** -> **Cash Shift Verification** (`cash-shift-verification`).
- **RetailEdge Daily Sales Audit** -> **Daily Sales Audit** (`daily-sales-audit`).
- **Daily Sales Audit Register** is no longer a separate navigation destination because the Daily Sales Audit page reuses its report provider.

### Retain as advanced native reports

These have no dedicated RetailEdge page replacement in the current branch and therefore remain available as advanced reports in a new tab:

- **Invoice Payment Audit**.
- **POS Closing Variance vs Expenses**.
- ERPNext detailed accounting reports including General Ledger, Trial Balance, Profit and Loss, Balance Sheet, Cash Flow, Accounts Receivable, Accounts Payable, Stock Ledger, Stock Balance, Projected Stock, and Stock Ageing.

### Defer pending existing work

- **Stock Movement History**: keep the legacy Query Report as primary until its existing parity QA gate is accepted.
- **Bank Matching**, **Unmatched Bank Transactions**, **Unmatched Bank Payments**, **Reconciliation Readiness**, and **Reconciliation Handoff**: do not retire here; ownership belongs to R6 / PR #24 until that banking work is reconciled with the current RetailEdge foundation.

### Retain native documents as advanced records

ERPNext and RetailEdge DocTypes that remain necessary for full/advanced operations are not cloned as replacement pages merely for visual consistency. Their normal RetailEdge operating path should be Guided Entry where supported; direct native access remains an advanced fallback and opens in a new tab.

This includes full ERPNext documents such as Sales Invoice, Sales Order, Delivery Note, Purchase Invoice, Purchase Order, Purchase Receipt, Stock Entry, Stock Reconciliation, Material Request, Payment Entry, Bank Transaction, Customer, Supplier, Item, Warehouse, Bank Account, and Mode of Payment.

### RetailEdge Setup

R7 now provides a dedicated **RetailEdge Setup** page at `retailedge-setup`. It is the primary RetailEdge setup destination for these existing configuration DocTypes:

- **RetailEdge Settings**.
- **RetailEdge Branch Profile**.
- **RetailEdge Expense Category**.
- **RetailEdge Statement Mapping Template**.

The Setup page does not create replacement configuration models. The existing DocTypes and their controllers remain the source of truth. The page provides managed business-facing editing for normal configuration, including Branch Profile operational users and non-banking RetailEdge Settings role tables. Company-dependent fields use contextual filtering and server-side validation. Native forms remain available through **Open Full Form** as advanced fallbacks and open in a new tab.

R6 bank matching/reconciliation settings and reconciliation execution roles are deliberately not managed by this R7 page. Platform integration controls also remain advanced configuration.

### Legacy Frappe Workspace

The committed `RetailEdge` Frappe Workspace still contains direct DocType and Query Report links. It is retained for backward compatibility while the Business Hub/product menu becomes authoritative. R7 must not patch Frappe routing globally or install brittle DOM click interception merely to change workspace behavior. Instead:

- new primary navigation changes belong in the Business Hub/product menu;
- direct native destinations reached through RetailEdge's authoritative navigation use the new-tab fallback policy;
- the legacy workspace should not receive new operational shortcuts;
- once PR #23 stabilizes, workspace fixture cleanup can be done in one deliberate sync-safe pass so migration does not restore obsolete primary routes.

## Audit hardening

The post-implementation R7 audit hardened the setup layer so that:

- Branch Profile company-dependent Branch, POS Profile, Warehouse, Cost Centre, and Account defaults are validated server-side rather than relying only on frontend filters;
- setup counts are permission-filtered;
- Branch Profile detail reads enforce document-level read permission;
- Branch Profile detail responses match the UI contract and preserve existing record state;
- setup list rows expose write capability so the UI can avoid presenting write actions to read-only users;
- no `ignore_permissions` bypass is used.

## Migration constraints

- Do not retire Stock Movement History's legacy Query Report until its existing parity QA gate is accepted.
- Do not retire or rewrite the banking/reconciliation surfaces owned by the active R6 branch/PR until that work is reconciled into the current RetailEdge foundation.
- Route retirement must happen only where a tested RetailEdge replacement is authoritative.
- Workspace/sidebar generators and committed fixtures must be updated together when a primary route changes so migrate/sync cannot restore an obsolete route.
- Do not add global Desk route monkey-patches or generic click interception to enforce RetailEdge-specific navigation behavior.

## Current slice

1. PR #23 owns global permission-aware **+ Create** access and new-tab handling for native DocType/Query Report destinations.
2. R7 promotes verified operational replacements and removes the duplicate Daily Sales Audit Register destination.
3. R7 provides the primary RetailEdge Setup page over existing RetailEdge configuration DocTypes.
4. R7 preserves Stock Movement and R6 banking boundaries instead of creating competing routes.
5. User-visible failure messages use RetailEdge/business terminology rather than the internal framework name.
6. Regression coverage locks route promotion, setup permissions and source-of-truth rules, new-tab inheritance, global Guided Create inheritance, naming, and no-business-write contracts.
