# RetailEdge 1.0 — Second MVP Release Audit

## Authority

- Product: RetailEdge
- Release target: **1.0.0**
- Authoritative PR: #55
- Authoritative branch: `qa/retailedge-reconciled-20260902`
- Initial second-audit gap-closure head: `4ac9734f91fdd1c7a05e0539ce5a03ddd12873c8`
- Post-freeze implementation revalidation baseline: `ff5c260b19a5f66358fa3f95e94d6043edd17707`
- Audit date: 2026-09-12
- Revalidated: 2026-09-13
- Audit state: **FROZEN — IMPLEMENTATION GREEN / RC3 ACCEPTANCE READY**
- Purpose: perform and freeze the agreed second MVP re-audit **before** final browser/persona acceptance.

This audit supersedes the earlier assumption that RC3 could begin before a second full MVP re-audit. That re-audit is now complete, its P1 gaps are closed, and the governed implementation gates on the exact gap-closure head are green.

RC3 remains a separate acceptance phase. Automatically triggered browser smoke runs before or during the freeze do **not** count as RC3 acceptance.

## Governing conclusion

RetailEdge 1.0 is not missing a major MVP business workflow. Core sales, purchasing, payments, expenses, stock, banking, reporting and management services are present and retain ERPNext accounting/stock truth.

The second audit and exact-head reconciliation found four genuine P1 pre-test gaps. All four are now closed:

1. Business Hub expense ownership/routing;
2. approved Business Hub Home shortcuts;
3. RC3 acceptance-contract alignment for Stock Movement History and Frappe v16 Desk routing;
4. canonical RetailEdge Page-role access for the Business Hub / banking entry surfaces.

The second MVP audit is therefore frozen as **implementation-green / acceptance-ready**. The next governed phase is RC3 browser/persona acceptance.

## Twelve-area MVP review — frozen result

| # | Review area | Frozen status | Second-audit conclusion |
|---|---|---|---|
| 1 | Reconciled product baseline / branch composition | GREEN | PR #55 remains the authoritative consolidated candidate. No divergent product branch is required. |
| 2 | Role model / EdgeSuite access model | GREEN | Canonical compact RetailEdge roles remain authoritative. Frappe roles intentionally remain Desk-enabled System User roles; EdgeSuite UI access mode independently controls `edgesuite_only` vs Native Desk. Canonical Page-role gaps on Business Hub/Banking are corrected. The RC3-critical Page set was rechecked directly; Professional Purchasing intentionally remains limited to ERPNext Purchase/Accounts authority. |
| 3 | Sales / customer operational workflow | GREEN | Standard Quotation → Sales Order → Delivery → Sales Invoice, customer receipt/advance and standard Sales Invoice completion are code-complete with Frappe Workflow precedence and ERPNext lifecycle authority. |
| 4 | Purchasing / stock receiving / supplier workflow | GREEN | Professional Purchasing owns Purchase Order → Receipt → Purchase Invoice, returns/debit notes, supplier payment and standard completion. **Receive Stock** is now exposed from the approved Home shortcut contract while retaining Professional Purchasing as workflow owner. |
| 5 | Payments / cash / banking | GREEN | Payment Management, Cash Movement, internal transfer, banking readiness and Bank Matching are implemented; Banking pages use the shared RetailEdge shell. **Match Bank Transactions** is now exposed from the approved Home shortcut contract. |
| 6 | Expenses | GREEN | Cashier Expense and modern Business Expense workflows are both implemented. Owner/Manager/Accounts users with Business Expense create permission now receive **Record Expense** into the modern Business Expenses workflow; cashier-only contexts retain Cashier/POS Expense. |
| 7 | Stock operations | GREEN | Guided Stock Transfer and Stock Adjustment retain ERPNext draft truth; RC2 standard completion provides EdgeSuite completion for ordinary supported cases. Complex serial/batch/valuation cases remain deliberate advanced boundaries. |
| 8 | Business Hub / Home command centre | GREEN | Today KPIs, Stock/Banking/Branch/Cash Shift signals, Attention and permission-aware Create are implemented. The approved Home shortcut contract is reconciled: Make Sale, Receive Payment, Pay Supplier, Record Expense, Receive Stock, Transfer Stock, Record Purchase, and Match Bank Transactions. |
| 9 | Action Centre / review ownership | GREEN | Action Centre is EdgeSuite-owned, uses the shared shell, and banking exceptions route to canonical Bank Matching rather than native reports/DocTypes. Queue-specific deep-linking is convenience-only and does not block 1.0. |
| 10 | Reporting / management visibility | GREEN FOR MVP | Sales, purchase, receivables, payables, stock, expense, cash, branch, salesperson, daily audit and management signals are sufficient for MVP. Additional analytics remain post-1.0 unless a correctness defect is found. |
| 11 | Security / branch isolation / install / upgrade | GREEN AUTOMATED, RC3 PENDING | Branch Assignment authority, restricted-zero fail-closed, server-side Company/Branch checks, Native Desk containment, clean install and real upgrade validation are covered. Manual/browser persona isolation evidence remains an RC3 acceptance responsibility. |
| 12 | Acceptance contract / release hardening | GREEN FOR RC3 ENTRY | RC3 now matches the current Stock Movement History EdgeSuite ownership and Frappe v16 `/app/... → /desk/...` routing behavior. Version remains pre-release until RC3 passes. |

## P1 closure record

### P1-A — Business Hub expense intent — CLOSED

Implemented 1.0 behavior:

- Cashier/POS context keeps the governed Cashier Expense flow.
- Users who can open/create Business Expenses receive **Record Expense** into `business-expenses` new-entry mode.
- No duplicate ledger or accounting path was introduced.
- Permission-derived routing determines which expense experience is exposed.

### P1-B — Approved Home operational shortcuts — CLOSED

The approved Home contract now exposes compact permission-aware shortcuts for:

- Make Sale;
- Receive Payment;
- Pay Supplier;
- Record Expense;
- Receive Stock;
- Transfer Stock;
- Record Purchase;
- Match Bank Transactions.

These shortcuts route to existing governed workflow owners; they do not duplicate backend accounting or stock logic.

### P1-C — Acceptance contract reconciliation — CLOSED

The RC3 runbook now matches the exact candidate:

- Stock Movement History is part of the EdgeSuite-owned 1.0 composition when permission-available; the obsolete Query Report hold was removed.
- Frappe v16 Desk routing is handled correctly; `/app/...` may resolve to `/desk/...` and acceptance waits for the actual Desk/page mount.
- Automated browser smoke remains supplemental; full RC3 still requires the restricted one/multiple/zero Branch personas and consolidated cross-workflow checks.

### P1-D — Canonical Page-role access — CLOSED

Head reconciliation found that some high-value Page metadata still depended on compatibility role labels even though the canonical internal contract uses compact RetailEdge role IDs.

The 1.0 entry surfaces are now aligned so canonical RetailEdge personas can reach the permitted Page before the EdgeSuite runtime is evaluated:

- Business Hub includes canonical `RetailEdgeManager`, `RetailEdgeBranchManager` and `RetailEdgeCashier`;
- Banking Readiness and Bank Matching include canonical Manager / Branch Manager identities alongside finance/System Manager authority;
- the full RC3-critical Page set was rechecked for canonical role coverage;
- Professional Purchasing is deliberately **not** broadened to RetailEdge Manager roles because ERPNext Purchase/Accounts permissions remain the authority.

This is Page-entry compatibility only. It does not broaden DocType, accounting, stock, Company or Branch permissions.

### Shared-shell composition recheck — GREEN

The 1.0-critical operational surfaces were rechecked for common RetailEdge shell ownership. Business Hub, Action Centre, Banking Readiness, Bank Matching, Professional Selling/Purchasing, Payments, Cash Movement, Receivables, Payables, Stock Position/Movement, Expense Register/Business Expenses/Expense Review, Cash Shift Verification and Daily Sales Audit all resolve through the common RetailEdge navigation/shell contract or the shared reporting component that provides it.

EdgeSuite-only final navigation still removes native DocType/Report destinations, while authorised Native Desk users retain deliberate advanced fallbacks.

## Freeze evidence

The exact second-audit gap-closure head `4ac9734f91fdd1c7a05e0539ce5a03ddd12873c8` completed the normal governed implementation gates successfully:

- RetailEdge Theme Compatibility — run #896 — **PASS**
- Linters — run #2737 — **PASS**
- Clean Frappe v16 CI — run #2755 — **PASS**
- EdgeSuite UI Candidate Compatibility — run #993 — **PASS**
- RetailEdge Upgrade Validation — run #27 — **PASS**

A Browser Persona Smoke workflow was also automatically triggered. It is explicitly **not** counted as RC3 acceptance merely because it ran from GitHub triggers.

### Post-freeze implementation-head reconciliation

After the initial `4ac9734f...` audit freeze, the PR advanced through browser-harness work and a narrow Business Hub canonical Page-role correction. Before this audit record was realigned, implementation head `ff5c260b19a5f66358fa3f95e94d6043edd17707` passed the normal governed gates again:

- RetailEdge Theme Compatibility — run #908 — **PASS**
- Linters — run #2749 — **PASS**
- Clean Frappe v16 CI — run #2767 — **PASS**
- EdgeSuite UI Candidate Compatibility — run #1005 — **PASS**
- RetailEdge Upgrade Validation — run #39 — **PASS**

The Browser Persona Smoke run on that head is **not** used to declare the second audit green; RC3 is a separate acceptance phase. The latest exact-head revalidation after audit-document alignment is recorded in the authoritative PR #55 freeze comment.

## Explicitly not reopened by this audit

Do not restart or expand these unless a P0/P1 defect is found:

- core sales/purchase/payment/stock workflow rewrites;
- selector-by-selector G2G expansion;
- conversion of every specialist ERPNext screen into EdgeSuite;
- advanced analytics/forecasting polish;
- complex serial/batch/valuation workflows;
- specialist Payment Reconciliation / multi-currency accounting;
- cosmetic-only report enhancements.

## Governed release order from this freeze

1. **Second full MVP re-audit — COMPLETE**
2. **Close second-audit P1 gaps — COMPLETE**
3. **Freeze second audit as implementation-green / acceptance-ready — COMPLETE**
4. Execute RC3 browser/persona acceptance on the authoritative PR #55 line.
5. Fix **only** P0/P1 defects discovered by RC3.
6. Set RetailEdge version to `1.0.0`, update README/release/upgrade notes, and rerun final release gates.
7. Tag `v1.0.0` only after all required release gates are green.

## Release rule

RetailEdge 1.0 must not be tagged while any RC3 stop-the-line defect remains open.

The second MVP audit is frozen. New feature work or non-blocking polish must not be inserted between this freeze and RC3 acceptance.
