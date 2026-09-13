# RetailEdge MVP RC3 — Consolidated exact-head browser/persona QA

## Authority and status

- **Authoritative PR:** #55
- **Authoritative branch:** `qa/retailedge-reconciled-20260902`
- **MVP candidate:** current PR #55 exact head deployed to `retail.local`
- **Stage:** RC3 — consolidated local browser/persona acceptance
- **Execution status:** **PASS — RC3 FROZEN**
- **Target QA site:** `retail.local`
- **Release status:** **RC3 CLOSED** — proceed to blocker-only RetailEdge 1.0.0 release hardening

This is the single execution record for the final reconciliation browser/persona gate. It must be executed only after the second MVP audit in `docs/retailedge_mvp_second_audit_20260912.md` is implementation-green. It consolidates the current PR #55 contracts and reuses useful detail from earlier module-specific browser QA documents without inheriting their obsolete PR #23 branch assumptions or superseded promotion decisions.

Actual QA results must be recorded against the exact commit deployed to `retail.local`. Automated green checks do not substitute for this browser gate.

## Source contracts reused by this runbook

The detailed checks in the following documents remain useful where they agree with the current PR #55 route/promotion contract:

- `docs/retailedge_reconciliation_integrity_recovery.md`
- `docs/retailedge_route_promotion_matrix.md`
- `docs/action_center_browser_qa.md`
- `docs/r4_browser_parity_qa.md`
- `docs/retailedge_owner_dashboard_browser_qa.md`
- `docs/prereporting_access_hardening.md`
- `docs/prereporting_edgesuite_only_operational_guard.md`
- `docs/prereporting_edgesuite_operational_surfaces.md`
- `docs/rir2b3_banking_readiness_discoverability.md`
- `docs/rir2c1_keyboard_command_ownership.md`
- `docs/rir2d1_searchable_create_picker.md`

When an older browser document conflicts with the current route matrix or later RIR decision, the later PR #55 contract wins. In particular:

- Bank Matching everyday navigation must open Page `bank-matching-reconciliation`, not the legacy `RetailEdge Bank Transaction Matching` Query Report.
- Banking Readiness is permission-aware in the Business Hub Money group and appears before Bank Matching.
- `branch-assignments` remains System Manager-only through consolidated RetailEdge Setup; it must not appear as a general operator route.
- Daily Sales Audit, Expense Review and Cash Shift Verification are current Business Hub Pages with native/report fallback retained where defined by the route matrix.
- Stock Movement History now uses the hardened EdgeSuite Page `stock-movement-history` in final master composition when Page permission is available; native Item/Voucher drill-through remains capability-gated.
- The current Business Hub MVP Home is in scope. QA must verify the Today command centre, permitted KPI cards, Stock/Banking/Branch/Cash Shift sections, Attention items, quick actions, and graceful degradation for personas without management-dashboard permissions.

## Exact-head preflight

Before testing:

1. Record the exact deployed RetailEdge SHA below. It must be the current PR #55 head being accepted.
2. Confirm the working tree is clean after pull/build/migrate.
3. Build RetailEdge and governed EdgeSuite UI assets.
4. Run `bench --site retail.local migrate` and clear browser/server cache as required.
5. Confirm the operational-guard bundle is served successfully and the Professional Selling/Purchasing pages load without the previous Frappe-v16 fullname/runtime error.
6. Confirm Frappe v16 Desk routing is handled correctly: an `/app/<page>` request may resolve to `/desk/<page>`; acceptance waits for the Desk shell and target RetailEdge Page mount rather than assuming the visible URL remains under `/app`.
7. Confirm Theme Compatibility, Linters, full Frappe/RetailEdge CI and EdgeSuite UI Candidate Compatibility are green on the same exact head.
8. Keep browser console and network panels available during QA. Missing assets, uncaught exceptions and 403/permission failures must be captured with the persona and route.

Execution record:

- Tested SHA: **`202741c34abd76d53521e3d60f0a69d1557a9a87`**
- RetailEdge version/branch: `qa/retailedge-reconciled-20260902` — MVP 1.0 candidate
- Frappe version: `version-16` workflow candidate
- ERPNext version: `version-16` workflow candidate
- EdgeSuite UI version/candidate: governed `agent/reporting-standard-v1` candidate used by RC3 workflow
- Browser(s): Playwright Chromium on Ubuntu 24.04
- Tester/date: exact-head GitHub Actions persona run + retained-evidence review, 2026-09-13
- Browser workflow run: **34768383675**
- Browser result: **21 / 21 PASS**
- Retained evidence artifact: **retailedge-browser-persona-evidence**, artifact **10320623855** (screenshots, traces and video retained on success)
- Companion exact-head gates: Theme Compatibility, Linters, Frappe v16 CI, EdgeSuite UI Candidate Compatibility and Upgrade Validation — **PASS**

## Required personas and scope fixtures

Use separate users/fixtures where practical; do not simulate denial only by hiding menu items.

| Persona/context | Required scope characteristic | Status |
| --- | --- | --- |
| Owner / RetailEdge Manager | broad permitted company context | PASS |
| Branch Manager | management role with restricted branch context | PASS |
| Cashier | ordinary operational/cashier context | PASS |
| Accounts User / Manager | payments/banking/accounting operational context | PASS |
| Stock / Store user | stock operational context | PASS |
| Purchasing user | buying operational context | PASS |
| Sales user | selling operational context | PASS |
| Restricted — one Branch | exactly one permitted Branch in selected Company | PASS |
| Restricted — multiple Branches | more than one permitted Branch | PASS |
| Restricted — zero Branches | Branch Assignment history exists but no active permitted Branch | PASS |
| Advanced Native Desk user | explicitly allowed native/advanced fallback | PASS |

The branch fixtures must exercise the current authority rule: once Branch Assignment history exists it is authoritative; restricted-zero must fail closed.

## Gate A — shell, Home and navigation composition

For each applicable persona:

- Business Hub loads as the normal RetailEdge Home with one EdgeSuite shell and no competing native sidebar.
- Business Hub Today cards and Stock/Banking/Branch/Cash Shift/Attention signals load within the selected Company/Branch scope; unavailable management sections degrade independently without disabling permitted operational actions.
- Product menu and sidebar expose only routes permitted for that user.
- Direct URL access does not bypass Frappe Page/DocType/report permissions or EdgeSuite-only restrictions.
- Everyday EdgeSuite-only users are not forced into Native Desk for flows already declared supported in RetailEdge.
- Advanced Native Desk user retains authorised native fallback without changing accounting or stock authority.
- No accidental duplicate route remains where a canonical current Page has deliberately replaced an everyday legacy target.
- Technical child-table/setup records are not exposed as ordinary navigation.

Stop the run on any cross-company/branch data leak, permission bypass or unexpected Native Desk escape.

## Gate B — Universal Create and searchable Create

For every persona that should receive Create:

- Universal `+ Create` is visible from the common RetailEdge product experience only when permitted.
- Opening Create shows only server-permitted actions.
- The Create popup contains its current search field, focuses correctly, filters rendered permitted actions, updates the result count, shows a no-match state, and lets Escape clear an active query before closing the modal.
- Search never reveals the label/count/existence of an action withheld by permission/context.
- Ctrl/Cmd+K opens the shared EdgeSuite Product Menu and allows reaching `+ Create` without a duplicate RetailEdge global keyboard listener.

Create/search absence on the deployed exact head is a reconciliation blocker, not permission to rebuild an older branch wholesale.

## Gate C — guided everyday operations

Exercise every action available to the tested persona, including as applicable:

- New Sales Invoice
- Receive Customer Payment
- Pay Supplier
- Deposit Cash
- Cash / Bank Transfer
- Record Purchase
- Record Expense:
  - permitted Owner/Manager/Accounts contexts must enter the modern **Business Expenses** flow;
  - cashier-only contexts must retain the governed **Cashier/POS Expense** flow;
- Transfer Stock
- Stock Adjustment
- Customer Quick Entry
- Supplier Quick Entry
- Product / Item Quick Entry

For every creation flow:

- Company/Branch/dependent Link fields cascade to permitted values only.
- Server validation rejects manipulated or stale dependent values.
- Guided entry first creates an ERPNext/RetailEdge **draft** or normal Quick Entry record according to the existing workflow contract.
- Where RetailEdge owns a standard completion surface, the saved draft must continue into EdgeSuite review rather than stranding an EdgeSuite-only user.
- Sales Invoice, Purchase Invoice, internal Cash/Bank Transfer, Stock Transfer, and Stock Adjustment completion must show server-authoritative blockers/readiness before any transition.
- Active Frappe Workflow must take precedence; only server-returned workflow actions may be applied.
- Direct standard completion may submit only through the normal ERPNext document `submit()` path with normal submit permission and stale-version protection.
- Serial/Batch-managed, amended, specialist valuation, or otherwise advanced stock cases must remain explicit Advanced ERPNext boundaries.
- No guided or completion UI may directly mutate GL/SLE, valuation truth, docstatus/workflow state, bypass permissions, or change submitted documents.
- Advanced ERPNext fallback appears only where the current Native Desk capability contract explicitly permits it.

### Stock Transfer branch cases

- One permitted Branch + blank Branch: resolves automatically where the B3 contract allows.
- Multiple permitted Branches + blank Branch: requires explicit Branch.
- Zero permitted Branches: fails closed.
- Source and target Warehouses are revalidated server-side against Company and permitted Branch.

## Gate D — core operational Pages

For personas with access, open and interact with the current authoritative Pages and confirm filters, empty/loading/error states, permissions, drill-through and no shell collision:

- `transaction-workspace`
- `professional-selling`
- `professional-purchasing`
- `payment-management`
- `cash-movement`
- `customer-receivables`
- `supplier-payables`
- `stock-position`
- `action-center` where role-gated
- `expense-review` where permitted
- `cash-shift-verification` where permitted
- `daily-sales-audit` where permitted

Where a Page is a read/control surface, compare representative values/rows with its existing authoritative source report/service rather than accepting visual rendering alone.

## Gate E — Banking and controlled setup discoverability

For permitted Accounts/Manager personas:

- Banking Readiness appears in Business Hub Money only when Page permission allows it.
- Banking Readiness appears immediately before Bank Matching.
- Banking Readiness Company/Branch data remains permission-scoped and cannot be widened by request manipulation.
- **Bank Matching opens Page `bank-matching-reconciliation`.** The legacy Query Report must not be the everyday Bank Matching target.
- Bank Matching loads the current RetailEdge banking workspace and does not regress to legacy/native matching merely because the fallback report still exists.
- Existing matching/review/reconciliation authority remains unchanged; loading the page does not mutate or reconcile records.
- `branch-assignments` is absent from ordinary operator navigation and is reachable only through the current System Manager-only RetailEdge Setup path.

## Gate F — read-scope and branch isolation

Across Selling, Purchasing, Payments, Stock, Expenses, Receivables, Payables, Banking and management/control Pages:

- selected Company cannot reveal another Company outside permission;
- selected Branch cannot reveal another Branch outside operational scope;
- restricted-zero users receive no company-wide fallback;
- direct API/URL manipulation does not widen returned rows, summaries, counts, choices or exports;
- missing/ambiguous branch attribution follows each already-frozen B4 scope contract rather than being guessed client-side;
- valuation/cost information remains hidden from cost-restricted users wherever that capability is already enforced.

Any wrong-company/wrong-branch row, count, summary or selectable warehouse/account is a stop-the-line defect.

## Gate G — keyboard/save safety

- Ctrl/Cmd+K behaves through the shared EdgeSuite command owner and does not fire duplicate menus/listeners.
- Ctrl/Cmd+S saves a normal active draft form through standard Frappe save semantics.
- Ctrl/Cmd+S refuses submitted documents.
- EdgeSuite contexts use only the shared registered/event save contract.
- No keyboard path uses permission bypass, direct database mutation or docstatus manipulation.

## Gate H — appearance and interaction quality

Run representative core surfaces in Light and Dark modes and at desktop plus narrow/mobile width:

- text, headings, tables, status pills, forms and dialogs remain readable;
- modal/dialog layering is correct;
- no critical horizontal clipping or unusable action controls;
- loading, empty, denied and backend-error states are understandable;
- Create search and product-menu search remain keyboard usable;
- no uncaught browser exception or missing required asset remains unresolved.

## Current Stock Movement History acceptance

Stock Movement History is now part of the EdgeSuite-owned 1.0 composition when the current user can open the `stock-movement-history` Page.

RIR2E must verify:

- the Page loads under the shared RetailEdge shell;
- Company/Branch/Warehouse scope matches the hardened Stock Ledger read contract;
- restricted-zero remains fail-closed;
- Item/Voucher identity remains visible for EdgeSuite-only users without exposing native Form links;
- authorised Native Desk users retain capability-gated Item/Voucher drill-through;
- page/export values reconcile with the underlying authoritative Stock Ledger dataset.

Do not demote the Page back to the Query Report during RC3 unless the second MVP audit identifies a correctness blocker.

The older Owner Dashboard browser checklist may be used for preview validation, but Owner Dashboard navigation promotion/redesign is not part of this reconciliation gate.

## Stop-the-line defects

RIR2E cannot pass with any unresolved defect in these classes:

1. cross-company or cross-Branch data exposure;
2. restricted-zero user receiving unrestricted/company-wide data or workflow access;
3. EdgeSuite-only user escaping to unauthorised Native Desk completion;
4. submitted accounting/stock/payment document mutation from a RetailEdge guided or keyboard path;
5. Bank Matching everyday route opening the legacy report instead of `bank-matching-reconciliation`;
6. Banking Readiness or Branch Assignments exposed outside their current permission/discoverability contracts;
7. Universal `+ Create` or its searchable Create picker missing/broken for a persona that should have it;
8. guided action exposing an action/Company/Branch/Warehouse/account the server does not permit;
9. Professional Selling/Purchasing operational guard missing at runtime;
10. required asset 404, uncaught runtime exception or shell failure preventing a core persona workflow;
11. Business Hub management cards, attention counts, or drill-through reveal another Company/Branch or break the ordinary user's permitted quick actions;
12. a standard guided Stock Transfer/Stock Adjustment leaves an EdgeSuite-only user with no completion path, or its completion bypasses Frappe Workflow / ERPNext stock authority.

Blocker-only fixes found during this stage must remain narrowly scoped, preserve the reconciled branch composition, receive regression coverage where practical, and rerun the exact-head automated gates before browser retest.

## Result matrix

Record PASS / FAIL / BLOCKED / NOT APPLICABLE. Initial state is intentionally NOT RUN.

| Gate | Owner/Manager | Branch Manager | Cashier | Accounts | Stock | Purchasing | Sales | 1 Branch | Multi Branch | Zero Branch | Native Advanced |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A Shell/navigation | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | N/A | N/A | PASS |
| B Create/search | PASS | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| C Guided operations | PASS* | PASS* | PASS* | PASS* | PASS* | PASS* | PASS* | PASS | PASS | PASS | PASS* |
| D Operational Pages | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | N/A | N/A | PASS |
| E Banking/setup | N/A | PASS | PASS (denied as designed) | PASS | N/A | N/A | N/A | N/A | N/A | N/A | PASS |
| F Read scope | PASS* | PASS* | PASS* | PASS* | PASS* | PASS* | PASS* | PASS | PASS | PASS | PASS* |
| G Keyboard/save | PASS* | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | PASS* |
| H Appearance/interaction | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | N/A | N/A | PASS |

### Acceptance evidence note

- `PASS` means the exact-head browser/persona suite directly exercised the surface/context and the retained successful artifact was reviewed.
- `PASS*` combines exact-head browser/persona execution with the corresponding exact-head backend/permission/accounting contract tests in the full Frappe v16 CI suite. RC3 deliberately did not create or submit arbitrary accounting documents merely to prove Frappe-native authority that is already regression-locked.
- The Branch Assignment fixtures exercised one-Branch auto-resolution, multi-Branch explicit-choice behavior and restricted-zero fail-closed behavior.
- Preserved successful-run evidence was reviewed for Business Hub/Create, Stock Position, Banking, Payment Management, Supplier Payables, RetailEdge Setup, Action Centre, permission-denial behavior and narrow/mobile rendering.
- No unresolved cross-company/Branch exposure, unauthorised Native Desk escape, required-asset/runtime failure or submitted-document mutation blocker remained on the accepted SHA.

## Defect record

For every failure capture:

| Field | Value |
| --- | --- |
| Exact SHA | |
| Persona/user type | |
| Company/Branch fixture | |
| Route/action | |
| Expected | |
| Actual | |
| Severity | P0 / P1 / P2 / P3 |
| Console/network evidence | |
| Screenshot/video reference | |
| Reproducible | Yes / No |
| Fix commit | |
| Retest result | |

### Closed RC3 blocker summary

| Blocker | Resolution | Final retest |
| --- | --- | --- |
| Incomplete Frappe/ERPNext Desk asset graph in browser CI | Browser workflow now builds the full Desk asset graph before Playwright | PASS |
| Business Hub permission/modal leakage and restricted operational master access | Capability probes made quiet; Branch Assignment retained as operational authority; restricted Home remains fail-closed | PASS |
| Sales/Purchase shell access and Page navigation fallback defects | Canonical persona Page access and EdgeSuite navigation fallback corrected without widening business-data authority | PASS |
| Searchable Create hidden items remained visually rendered | Hidden Create actions now remain actually hidden while preserving server-derived permissions | PASS |
| Restricted persona Stock/Banking data-path gaps | Branch warehouse fixture/data paths and safe-empty banking behavior hardened | PASS |
| RC3 harness initially filtered out consolidated acceptance spec | Playwright discovery corrected; final run executed **21 tests** | **21/21 PASS** |

## RIR2E closure gate

RIR2E may be frozen only when:

- all required exact-head automated gates are green;
- all required personas/context fixtures have been executed against the exact deployed head;
- every stop-the-line check passes;
- any blocker-only correction has been retested on the corrected exact head;
- no unresolved permission, branch-scope, runtime/asset, route-composition or submitted-document safety defect remains;
- the final PASS record identifies the exact tested SHA.

RC3 closure decision: **PASS / FROZEN** on implementation SHA `202741c34abd76d53521e3d60f0a69d1557a9a87`.

PR #55 remains the authoritative release candidate line. After this documentation-only freeze record, all six governed gates must remain green on the resulting exact head. Once that is confirmed, the next allowed stage is RetailEdge **1.0.0 release hardening**; no new feature scope is permitted.
