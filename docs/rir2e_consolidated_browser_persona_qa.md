# RetailEdge RIR2E — Consolidated browser/persona QA

## Authority and status

- **Authoritative PR:** #55
- **Authoritative branch:** `qa/retailedge-reconciled-20260902`
- **Preflight source baseline:** `aa5d37a53b7a6b79eed1637769e3b85617e0fa29`
- **Stage:** RIR2E — consolidated local browser/persona QA
- **Execution status:** **NOT RUN**
- **Target QA site:** `retail.local`
- **Reporting:** remains blocked
- **B4B26:** remains paused until this browser/persona gate is completed and the reconciled baseline is frozen

This is the single execution record for the final reconciliation browser/persona gate. It consolidates the current PR #55 contracts and reuses useful detail from earlier module-specific browser QA documents without inheriting their obsolete PR #23 branch assumptions or superseded promotion decisions.

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
- Stock Movement History remains on its existing Query Report as the normal route until its explicit Page parity gate is separately completed.
- The current Business Hub remains product Home for this reconciliation stage. A later MVP Business Hub/Home enhancement is outside this QA gate.

## Exact-head preflight

Before testing:

1. Record the exact deployed RetailEdge SHA below. It must be the current PR #55 head being accepted.
2. Confirm the working tree is clean after pull/build/migrate.
3. Build RetailEdge and governed EdgeSuite UI assets.
4. Run `bench --site retail.local migrate` and clear browser/server cache as required.
5. Confirm the operational-guard bundle is served successfully and the Professional Selling/Purchasing pages load without the previous Frappe-v16 fullname/runtime error.
6. Confirm Theme Compatibility, Linters, full Frappe/RetailEdge CI and EdgeSuite UI Candidate Compatibility are green on the same exact head.
7. Keep browser console and network panels available during QA. Missing assets, uncaught exceptions and 403/permission failures must be captured with the persona and route.

Execution record:

- Tested SHA: **NOT RUN**
- RetailEdge version/branch: `qa/retailedge-reconciled-20260902`
- Frappe version: **record at execution**
- ERPNext version: **record at execution**
- EdgeSuite UI version/candidate: **record at execution**
- Browser(s): **record at execution**
- Tester/date: **record at execution**

## Required personas and scope fixtures

Use separate users/fixtures where practical; do not simulate denial only by hiding menu items.

| Persona/context | Required scope characteristic | Status |
| --- | --- | --- |
| Owner / RetailEdge Manager | broad permitted company context | NOT RUN |
| Branch Manager | management role with restricted branch context | NOT RUN |
| Cashier | ordinary operational/cashier context | NOT RUN |
| Accounts User / Manager | payments/banking/accounting operational context | NOT RUN |
| Stock / Store user | stock operational context | NOT RUN |
| Purchasing user | buying operational context | NOT RUN |
| Sales user | selling operational context | NOT RUN |
| Restricted — one Branch | exactly one permitted Branch in selected Company | NOT RUN |
| Restricted — multiple Branches | more than one permitted Branch | NOT RUN |
| Restricted — zero Branches | Branch Assignment history exists but no active permitted Branch | NOT RUN |
| Advanced Native Desk user | explicitly allowed native/advanced fallback | NOT RUN |

The branch fixtures must exercise the current authority rule: once Branch Assignment history exists it is authoritative; restricted-zero must fail closed.

## Gate A — shell, Home and navigation composition

For each applicable persona:

- Business Hub loads as the normal RetailEdge Home with one EdgeSuite shell and no competing native sidebar.
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
- Record Cashier Expense
- Transfer Stock
- Stock Adjustment
- Customer Quick Entry
- Supplier Quick Entry
- Product / Item Quick Entry

For every creation flow:

- Company/Branch/dependent Link fields cascade to permitted values only.
- Server validation rejects manipulated or stale dependent values.
- The result is an ERPNext/RetailEdge **draft** or normal Quick Entry record according to the existing workflow contract.
- No guided UI silently submits, posts, reconciles, mutates GL/SLE, bypasses permissions or changes submitted documents.
- Advanced completion opens native ERPNext only where the current access-mode contract explicitly permits it.

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

## Explicit parity hold

Do **not** use RIR2E to promote `/app/stock-movement-history`. The current Query Report remains the normal route until its dedicated Page-vs-Report parity/export/mobile/browser gate passes. If that separate parity QA is run during the same local session, record it independently and do not change navigation without a bounded reviewed slice.

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
10. required asset 404, uncaught runtime exception or shell failure preventing a core persona workflow.

Blocker-only fixes found during this stage must remain narrowly scoped, preserve the reconciled branch composition, receive regression coverage where practical, and rerun the exact-head automated gates before browser retest.

## Result matrix

Record PASS / FAIL / BLOCKED / NOT APPLICABLE. Initial state is intentionally NOT RUN.

| Gate | Owner/Manager | Branch Manager | Cashier | Accounts | Stock | Purchasing | Sales | 1 Branch | Multi Branch | Zero Branch | Native Advanced |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A Shell/navigation | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| B Create/search | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| C Guided operations | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| D Operational Pages | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| E Banking/setup | NOT RUN | NOT RUN | N/A | NOT RUN | N/A | N/A | N/A | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| F Read scope | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| G Keyboard/save | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| H Appearance/interaction | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

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

## RIR2E closure gate

RIR2E may be frozen only when:

- all required exact-head automated gates are green;
- all required personas/context fixtures have been executed against the exact deployed head;
- every stop-the-line check passes;
- any blocker-only correction has been retested on the corrected exact head;
- no unresolved permission, branch-scope, runtime/asset, route-composition or submitted-document safety defect remains;
- the final PASS record identifies the exact tested SHA.

Until then PR #55 remains draft/open/unmerged, reporting stays blocked and B4B26 remains paused.
