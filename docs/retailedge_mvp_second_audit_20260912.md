# RetailEdge 1.0 — Second MVP Release Audit

## Authority

- Product: RetailEdge
- Release target: **1.0.0**
- Authoritative PR: #55
- Authoritative branch: `qa/retailedge-reconciled-20260902`
- Audit head: `7e5d1c8b79e5bb1edea783114d86a9825623fe16`
- Date: 2026-09-12
- Purpose: perform the agreed second MVP re-audit **before** final browser/persona acceptance.

This audit supersedes the assumption that RC3 is the immediate next step. RC3 must not be treated as release acceptance until all P0/P1 findings below are reconciled.

## Governing conclusion

RetailEdge 1.0 is no longer missing a major business workflow. Core sales, purchasing, payments, expenses, stock, banking, reporting and management services are present and retain ERPNext accounting/stock truth.

The remaining pre-test work is **composition and contract reconciliation**, not another broad feature phase.

## Twelve-area MVP review

| # | Review area | Status | Second-audit conclusion |
|---|---|---|---|
| 1 | Reconciled product baseline / branch composition | GREEN | PR #55 remains the authoritative consolidated candidate. No divergent product branch is required. |
| 2 | Role model / EdgeSuite access model | GREEN | Canonical compact RetailEdge roles remain authoritative. Frappe roles intentionally remain Desk-enabled System User roles; EdgeSuite UI access mode independently controls `edgesuite_only` vs Native Desk. Canonical Page-role gaps on Business Hub/Banking were corrected before this audit. |
| 3 | Sales / customer operational workflow | GREEN | Standard Quotation → Sales Order → Delivery → Sales Invoice, customer receipt/advance and standard Sales Invoice completion are code-complete with Frappe Workflow precedence and ERPNext lifecycle authority. |
| 4 | Purchasing / stock receiving / supplier workflow | GREEN WITH HOME-SHORTCUT GAP | Professional Purchasing owns Purchase Order → Receipt → Purchase Invoice, returns/debit notes, supplier payment and standard completion. “Receive Stock” exists operationally through Ready-to-Receive Purchase Orders, but is not yet surfaced as the approved Business Hub shortcut. |
| 5 | Payments / cash / banking | GREEN WITH HOME-SHORTCUT GAP | Payment Management, Cash Movement, internal transfer, banking readiness and Bank Matching are implemented; Banking pages now use the shared RetailEdge shell. “Match Bank Transactions” is not yet surfaced as the approved Business Hub shortcut. |
| 6 | Expenses | AMBER — P1 COMPOSITION GAP | Cashier Expense and modern Business Expense workflows are both implemented. Business Expenses are enabled by default and accounting posting is enabled by default. However Business Hub `record-expense` still opens only the Cashier/POS Expense dialog for every eligible user, rather than routing owner/manager/accounts users to the approved non-POS Business Expenses flow. |
| 7 | Stock operations | GREEN | Guided Stock Transfer and Stock Adjustment retain ERPNext draft truth; RC2 standard completion provides EdgeSuite completion for ordinary supported cases. Complex serial/batch/valuation cases remain deliberate advanced boundaries. |
| 8 | Business Hub / Home command centre | AMBER — P1 COMPOSITION GAP | Today KPIs, Stock/Banking/Branch/Cash Shift signals, Attention and permission-aware Create are implemented. Before 1.0 acceptance, Home must reconcile its approved quick-action contract: non-POS Record Expense for eligible users, Receive Stock, and Match Bank Transactions. |
| 9 | Action Centre / review ownership | GREEN | Action Centre is EdgeSuite-owned, uses the shared shell, and banking exceptions now route to canonical Bank Matching rather than native reports/DocTypes. Queue-specific deep-linking is convenience-only and does not block 1.0. |
| 10 | Reporting / management visibility | GREEN FOR MVP | Sales, purchase, receivables, payables, stock, expense, cash, branch, salesperson, daily audit and management signals are sufficient for MVP. Additional analytics remain post-1.0 unless a correctness defect is found. |
| 11 | Security / branch isolation / install / upgrade | GREEN AUTOMATED, MANUAL ACCEPTANCE PENDING | Branch Assignment authority, restricted-zero fail-closed, server-side Company/Branch checks, Native Desk containment, clean install and real upgrade validation are covered. Manual persona/browser isolation evidence remains RC3. |
| 12 | Acceptance contract / release hardening | AMBER — PRE-TEST RECONCILIATION REQUIRED | The RC3 runbook still contains stale Stock Movement History “Query Report hold” wording even though current master composition promotes the hardened EdgeSuite Page. Browser smoke also must account for Frappe v16 `/app/... → /desk/...` runtime routing. Version remains pre-release until RC3 passes. |

## P1 findings that must close before RC3

### P1-A — Business Hub expense intent

Current state:

- base quick action key `record-expense` is labelled **Record Cashier Expense**;
- Business Hub maps that key directly to `SimpleCashierExpenseDialog`;
- therefore manager/accounts users are not guided to the modern Business Expenses owner from the main Home create/action surface.

Required 1.0 behavior:

- Cashier/POS context keeps the governed Cashier Expense flow;
- users who can open/create Business Expenses should receive **Record Expense** into `business-expenses` new-entry mode;
- no duplicate ledger or accounting path is introduced.

### P1-B — Approved Home operational shortcuts

The approved Home contract included actionable shortcuts for:

- Make Sale;
- Receive Payment;
- Pay Supplier;
- Record Expense;
- Receive Stock;
- Transfer Stock;
- Create/Record Purchase;
- Match Bank Transactions.

Current Business Hub has permission-aware `+ Create`, but:

- Receive Stock is only discoverable inside Professional Purchasing;
- Match Bank Transactions is only discoverable through Banking/menu/signal cards;
- Record Expense resolves to Cashier Expense rather than Business Expense for eligible non-cashier roles.

Before RC3, Home should expose these as compact permission-aware shortcuts without duplicating backend workflows.

### P1-C — Acceptance contract reconciliation

The RC3 runbook must match the current exact candidate:

- Stock Movement History is now an EdgeSuite Page in final master composition when permission-available; remove the obsolete “must remain Query Report” acceptance hold.
- Browser automation must follow Frappe v16 Desk routing (`/app/... ` may resolve to `/desk/...`) and wait for actual Desk/page mount before asserting.
- Automated browser smoke remains supplemental; full RC3 still requires the restricted one/multiple/zero Branch personas and cross-workflow checks in the consolidated runbook.

## Explicitly not reopened by this audit

Do not restart or expand these unless a P0/P1 defect is found:

- core sales/purchase/payment/stock workflow rewrites;
- selector-by-selector G2G expansion;
- conversion of every specialist ERPNext screen into EdgeSuite;
- advanced analytics/forecasting polish;
- complex serial/batch/valuation workflows;
- specialist Payment Reconciliation / multi-currency accounting;
- cosmetic-only report enhancements.

## Pre-test execution order

1. Close P1-A Business Hub expense ownership.
2. Close P1-B Business Hub approved shortcuts.
3. Close P1-C RC3 runbook / Frappe v16 route contract.
4. Rerun exact-head governed gates.
5. Freeze this second MVP audit as **implementation-green / acceptance-ready**.
6. Only then execute RC3 browser/persona acceptance.
7. Fix only P0/P1 defects discovered by RC3.
8. Set RetailEdge version to `1.0.0`, update README/release/upgrade notes, rerun release gates, and tag `v1.0.0`.

## Release rule

RetailEdge 1.0 must not be tagged while any second-audit P1 finding or RC3 stop-the-line defect remains open.
