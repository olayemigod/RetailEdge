# RetailEdge Reconciliation Integrity Recovery

## Status

- **Authoritative line:** PR #55 / `qa/retailedge-reconciled-20260902`
- **Frozen hardening checkpoint audited:** `46af522fea7d7ad78d0b8fb66e392f50722a41f5` (B4B25)
- **Audit phase:** RIR1 — Reconciliation Integrity Audit
- **Implementation state:** documentation/audit only; no business behaviour changed in RIR1
- **Reporting:** remains blocked
- **B4B26:** deferred until reconciliation recovery is completed/frozen
- **Manual browser/persona QA:** remains deferred until the recovery slices below are complete

This document records the feature-level reconciliation state of RetailEdge before MVP completion. It exists because branch/PR state alone is not sufficient evidence that a capability is active in the current product experience. A feature may be in the current ancestry but disconnected, incorrectly routed, superseded, browser-broken, or intentionally held behind a parity gate.

## Non-negotiable safety baseline

All recovery work must preserve the B1–B4 hardening already completed on PR #55, including:

- ERPNext remains the source of truth for accounting, stock, selling, buying, payments and projects.
- Submitted accounting/stock documents must not be mutated to repair UI composition.
- Branch Assignment history remains authoritative when it exists.
- Restricted users with zero permitted branches remain fail-closed.
- Company, Branch, Warehouse and other operating-context rules remain server-authoritative.
- Frontend filtering is not a security boundary.
- Frappe/ERPNext permissions remain authoritative.
- EdgeSuite-only presentation controls must not weaken native permission checks.
- No historical branch is to be merged or cherry-picked wholesale merely because a feature appears missing.

## Classification vocabulary

| Classification | Meaning |
| --- | --- |
| `INCORPORATED_ACTIVE` | Capability exists in current source and is wired to the current product contract. Browser QA may still be required. |
| `INCORPORATED_BROKEN_RUNTIME` | Capability exists and is routed, but a confirmed runtime/asset compatibility defect prevents reliable use. |
| `INCORPORATED_DISCONNECTED` | Implementation exists but the normal product experience does not expose it. |
| `INCORPORATED_WRONG_ROUTE` | Implementation exists, but navigation still points to an older/native/legacy destination instead of the intended RetailEdge surface. |
| `MISSING_RECOVER` | Useful historical capability is not present in the frozen current head and should be recovered in a bounded modern implementation. |
| `MISSING_RECOVER_INTENT` | The old implementation should not be restored wholesale, but an important behavioural contract from it is absent and should be reintroduced safely. |
| `INTENTIONALLY_DEFERRED` | Implementation exists, but promotion was deliberately blocked pending parity/browser QA or another explicit gate. |
| `SUPERSEDED` | Historical implementation has been replaced by a newer current architecture and should not be restored. |
| `OBSOLETE_UNSAFE` | Historical implementation should not be recovered because it conflicts with current safety/product contracts. |

## Executive findings

1. The previously reported **Universal `+ Create` capability is not missing from the current source**. The current RetailEdge product menu includes a permission-aware `+ Create` action that can be invoked from the common product menu and routes to the guided Create experience. If it is not visible on `retail.local`, that is a browser/runtime/discoverability defect to QA, not evidence that the feature was omitted from reconciliation.
2. The **searchable/fuzzy Create picker is also present in the current source**. The Business Hub route bridge dynamically augments the Create list with fuzzy search, count, empty state and single-result Enter handling. It must be browser-tested after the current runtime blockers are corrected.
3. The guided everyday transaction programme is substantially preserved: Sales Invoice, customer receipt, supplier payment, cash deposit, cash/bank transfer, purchase, cashier expense, stock transfer and stock adjustment remain configured as guided quick actions. Customer, Supplier and Product quick entry is also present through the master-experience layer.
4. The dominant UX reconciliation problem is **route composition**. Many current RetailEdge EdgeSuite Pages exist, while base navigation still exposes native ERPNext DocTypes or legacy Query Reports. Each candidate must be promoted only where the RetailEdge surface has sufficient everyday-workflow parity.
5. **Bank Matching is a confirmed wrong-route case.** The full `bank-matching-reconciliation` EdgeSuite page exists on the frozen head, while the current Money navigation still points `Bank Matching` at `RetailEdge Bank Transaction Matching` Query Report.
6. The historical **EdgeSuite keyboard command** branch contains three useful commits not present in the frozen head. Its Ctrl/Cmd+S safe-save and Ctrl/Cmd+K command-palette intent should be recovered against the current EdgeSuite UI runtime rather than cherry-picked blindly.
7. The old EdgeUI navigation-quality/document-workspace stack is heavily superseded. Its older home/document-workspace implementation must not be merged wholesale. However, its target-based navigation-deduplication intent is still useful because current workspace/sidebar normalisation can distinguish duplicate aliases by label.
8. Manual QA on `retail.local` has already exposed a **real Frappe v16 runtime defect** in Transaction Workspace: `frappe.get_user().get_fullname()` is called even though the returned `UserPermissions` object has no `get_fullname()`. This must be repaired before the absence/presence of shared UX elements is judged from browser screenshots.
9. Professional Selling also reported an EdgeSuite-only operational-guard load failure in local QA, while the guard source and global installer are present in the current tree. Treat this as an asset/runtime verification blocker, not missing implementation.

## Feature-level reconciliation matrix

| Feature | Historical source / programme | Frozen HEAD state | Current route / exposure | Intended MVP-facing route / exposure | Guided flow | Native fallback | Classification | Recovery action | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Universal `+ Create` entry | R2 / R7 usability | Product-menu `guidedCreateSection()` and `requestGuidedCreate()` present | Product menu; request redirects to Business Hub Create | Common permission-aware RetailEdge Create entry from normal EdgeSuite product pages | Yes | Advanced/native where explicitly supported | `INCORPORATED_ACTIVE` | Do not rebuild. Browser-test visibility and invocation across product pages after runtime fixes. | Low if left on current shared action registry. |
| Searchable Create picker | R2 usability follow-up / route bridge | Fuzzy search, edit distance, subsequence scoring, count, empty state and Enter handling present | Injected by Business Hub route bridge when Create opens | Same current searchable Create picker | Yes | N/A | `INCORPORATED_ACTIVE` | Do not rebuild. Add browser regression coverage and ensure asset/controller boot is reliable. | Low. |
| Guided Sales Invoice | R2 guided Create | Present in `QUICK_ACTIONS` and Business Hub dialog set | Create picker | Create picker / relevant selling entry points | Yes | Full ERPNext draft form for authorised advanced use | `INCORPORATED_ACTIVE` | Preserve; browser-test smart filtering and draft creation. | Accounting safety if future changes bypass ERPNext draft rules. |
| Receive Customer Payment | R2 guided Create | Present | Create picker | Create picker / Payment Management where appropriate | Yes | Native Payment Entry for authorised advanced use | `INCORPORATED_ACTIVE` | Preserve; do not change allocation/accounting semantics. | High if payment allocation semantics are duplicated. |
| Pay Supplier | R2 guided Create | Present | Create picker | Create picker / payment workspace where appropriate | Yes | Native Payment Entry for authorised advanced use | `INCORPORATED_ACTIVE` | Preserve. | High if allocation semantics are duplicated. |
| Deposit Cash | R2 guided Create | Present and cashier-context gated | Create picker when cashier context permits | Create picker | Yes | Native Payment Entry for authorised advanced use | `INCORPORATED_ACTIVE` | Preserve current context checks. | High if custody controls are weakened. |
| Cash / Bank Transfer | R2 guided Create | Present; finance-role restricted | Create picker for permitted finance roles | Create picker | Yes | Native Payment Entry for authorised advanced use | `INCORPORATED_ACTIVE` | Preserve role and account controls. | High if internal-transfer accounting is reimplemented. |
| Record Purchase | R2 guided Create | Present | Create picker | Create picker / Professional Purchasing where appropriate | Yes | Native Purchase Invoice draft for authorised advanced use | `INCORPORATED_ACTIVE` | Preserve current server-authoritative pricing/default logic. | Medium/high. |
| Cashier Expense | R2 guided Create | Present | Create picker | Create picker / Expense operational surfaces | Yes | Native form only where advanced access is allowed | `INCORPORATED_ACTIVE` | Preserve shift/branch/account defaults. | Medium. |
| Stock Transfer | R2 + B3 hardening | Present; B3 branch-scope contract hardened | Create picker plus stock navigation | Guided Stock Transfer for everyday use | Yes | Native Stock Entry draft for authorised advanced use | `INCORPORATED_ACTIVE` | Preserve B3 exactly; browser-test single/multi/zero branch cases. | High if branch or warehouse validation is weakened. |
| Stock Adjustment | R2 guided Create | Present | Create picker | Create picker | Yes | Native Stock Reconciliation draft for authorised advanced use | `INCORPORATED_ACTIVE` | Preserve. | High if stock truth is reimplemented. |
| Customer Quick Entry | R2 master experience | Added by `master_experience.py`; route bridge supports Quick Entry | Create picker | Create picker | Quick Entry | Native Customer form | `INCORPORATED_ACTIVE` | Preserve permission-aware master creation. | Low/medium. |
| Supplier Quick Entry | R2 master experience | Present | Create picker | Create picker | Quick Entry | Native Supplier form | `INCORPORATED_ACTIVE` | Preserve. | Low/medium. |
| Product / Item Quick Entry | R2 master experience | Present | Create picker | Create picker | Quick Entry | Native Item form | `INCORPORATED_ACTIVE` | Preserve current restricted quick-entry contract; do not expose valuation/cost fields unnecessarily. | Medium. |
| Business Hub | EdgeSuite Business Hub / R2 | Present and bootstrapped globally | `retailedge-business-hub` | Same; MVP redesign will build on this surface later | Hosts Create | N/A | `INCORPORATED_ACTIVE` | Do not replace during reconciliation. Fix runtime dependencies first, then implement planned MVP Action Centre/dashboard enhancement later. | Medium if reconciliation is mixed with redesign. |
| Transaction Workspace | R2 transaction host | Source present; confirmed Frappe v16 user-name runtime defect | `transaction-workspace` | Same | Hosts transaction actions | Native advanced targets as authorised | `INCORPORATED_BROKEN_RUNTIME` | Replace invalid `frappe.get_user().get_fullname()` usage with Frappe-v16-safe current-user fullname resolution; add regression test. | Low if limited to display-name resolution. |
| Professional Selling | R2 selling workspace | Page/bundle and restricted operational guard present; local QA reported guard unavailable | `professional-selling` | Same | Guided selling workflow | Native selling forms only for authorised advanced users | `INCORPORATED_BROKEN_RUNTIME` | After Transaction Workspace fix, verify asset build/path and guard installation; do not weaken EdgeSuite-only restrictions. | Medium due access-mode presentation controls. |
| Professional Purchasing | R2 purchasing workspace | Present and promoted by master experience | `professional-purchasing` | Same for everyday purchasing where parity exists | Guided/native-draft orchestration | Native buying forms for advanced cases | `INCORPORATED_ACTIVE` | Browser/persona QA before final promotion decisions for every buying sub-operation. | Medium. |
| Payment Management | Payments programme | Present and promoted | `payment-management` | Same | Advanced payment orchestration | Native reconciliation remains ERPNext authority | `INCORPORATED_ACTIVE` | B4B26 read-scope hardening remains queued after RIR recovery. Do not change allocation/reconciliation writes during RIR. | High. |
| Expense Review | R4/R7 | Current master experience promotes browser-approved page | `expense-review` | Same | N/A | Native underlying documents as authorised | `INCORPORATED_ACTIVE` | Preserve. | Low. |
| Cash Shift Verification | R4/R7 | Current master experience promotes browser-approved page | `cash-shift-verification` | Same | N/A | Native underlying documents as authorised | `INCORPORATED_ACTIVE` | Preserve. | Low/medium. |
| Daily Sales Audit | R4/R7 | Current master experience promotes browser-approved page | `daily-sales-audit` | Same | N/A | Native source data remains authoritative | `INCORPORATED_ACTIVE` | Preserve. | Low/medium. |
| Bank Matching & Reconciliation | Banking / PR #24 | Full EdgeSuite page and workspace assets present | **Money navigation still points to `RetailEdge Bank Transaction Matching` Query Report** | `Page: bank-matching-reconciliation` for everyday RetailEdge banking | Banking workspace actions | Legacy report may remain advanced/comparison fallback if still useful | `INCORPORATED_WRONG_ROUTE` | Bounded route correction after RIR1, with access/permission tests and no banking engine rewrite. | Medium; route change can expose incomplete page if assets/browser parity are not checked. |
| Banking Readiness | Banking programme | Page present | Needs route-matrix review | Prefer RetailEdge page where current banking workflow requires it | N/A | Native Bank Account/statement setup where advanced | `INCORPORATED_ACTIVE` | Verify discoverability in RIR route matrix; do not assume all banking setup should be hidden. | Low/medium. |
| Branch Performance dashboard | R2 | EdgeSuite page present; historical R2 contract made it primary | EdgeSuite page exists | EdgeSuite page primary; Query Report detailed drill-down | N/A | Query Report detail | `INCORPORATED_ACTIVE` | Preserve existing page/report authority relationship. | Low. |
| Stock Movement History EdgeSuite page | R2 preview | Page present | Historical programme explicitly retained Query Report as normal route until parity QA | Promote only after local parity/export/mobile QA | N/A | Query Report remains fallback | `INTENTIONALLY_DEFERRED` | Do not force promotion during reconciliation. Run the deferred parity QA first. | Medium/high if promoted prematurely. |
| Stock Position / inventory operational pages | R8–R12 / inventory programme | Multiple current EdgeSuite pages present | Mixed Page + native DocType/report navigation | Promote only proven everyday surfaces; retain native advanced records where needed | Some guided flows | Yes | `INCORPORATED_ACTIVE` | Complete route matrix; no blanket native-page replacement. | Medium. |
| Customer Receivables | R8–R12 / customer programme | Page present and base navigation already points to Page | `customer-receivables` | Same | Collection actions may link to guided payment | Detailed AR report | `INCORPORATED_ACTIVE` | Preserve and test branch scope. | Medium. |
| Supplier Payables | R8–R12 / supplier programme | Page present and base navigation already points to Page | `supplier-payables` | Same | Payment action may link to guided supplier payment | Detailed AP report | `INCORPORATED_ACTIVE` | Preserve and test branch scope. | Medium. |
| Setup consolidation | R7 / later master experience | Current `retailedge-setup`, Branch Setup and Branch Assignments pages exist | Master experience consolidates selected RetailEdge setup DocTypes into setup Page | Same | Smart setup forms | Native advanced fallback as authorised | `SUPERSEDED` for old document-workspace implementation | Keep current setup architecture; audit old behaviour only for missing smart-form rules. | Medium. |
| Old `retailedge_home` / old document workspace | Historical EdgeUI navigation-quality stack | Not current product architecture | Historical routes | Business Hub / Transaction Workspace / RetailEdge Setup supersede them | N/A | N/A | `SUPERSEDED` | Do not restore/merge old stack wholesale. | High if old frontend architecture is reintroduced. |
| Target-based navigation deduplication | Historical navigation-quality Phase 7 | Old implementation absent; current workspace sync dedup identity includes label + target + link type | Current normalisation can retain aliases pointing to same target | One workflow-appropriate occurrence per target unless an intentional alias is documented | N/A | N/A | `MISSING_RECOVER_INTENT` | Reintroduce a bounded canonical-target dedupe contract after route matrix is frozen; hide technical child-table targets from normal navigation. | Medium if legitimate contextual aliases are removed blindly. |
| Shared keyboard commands | `agent/edgesuite-keyboard-commands` | Three branch commits are not in frozen head; asset absent | No current RetailEdge keyboard-command asset | Current EdgeSuite-compatible Ctrl/Cmd+K command access and safe Ctrl/Cmd+S where appropriate | N/A | Native Frappe save remains authority | `MISSING_RECOVER` | Reimplement/adapt against current EdgeSuite UI 1.1.0; preserve draft-only save safety and no permission bypass. | Medium due global keyboard interception. |

## Historical branch / PR disposition

### Fully incorporated or represented by later current work

- **R2 usability foundation / PR #23** — all branch commits are behind the current reconciled head. The current tree retains the Business Hub, guided Create programme, smart-link behaviour, Branch Performance Page and other R2 foundations. Do not merge PR #23 into PR #55.
- **Banking reconciliation direction / PR #24 lineage** — Banking implementation branches compared are behind the current reconciled head. The banking engine/Page is present; the defect is current route composition, not missing banking code.
- **R7 route consolidation / PR #26** — much of the behavioural intent is present through later current code: product-menu Create, new-tab native fallback, setup consolidation and selected page promotions. Treat PR #26 as historical design evidence, not a merge candidate.

### Genuinely missing bounded capability

- **`agent/edgesuite-keyboard-commands`** — three useful commits are not contained in the frozen head. Recover the command contract, not the old branch wholesale.

### Heavily superseded historical stack

- **`agent/retailedge-edgeui-navigation-quality-phase7` and related older document-workspace branches** — large divergent historical stack containing old home/document-workspace architecture. Do not merge. Recover only still-relevant behavioural contracts after comparing them with current pages. The strongest currently identified reusable contract is canonical target-based navigation deduplication.

## Current route-composition rule

The recovery must not convert every native ERPNext destination into an EdgeSuite page merely because a RetailEdge Page exists.

Use this rule for each operation:

1. If the RetailEdge Page is the tested everyday operational surface and has required workflow parity, make it the normal RetailEdge route.
2. If the RetailEdge Page is preview-only or explicitly held behind a parity gate, keep the existing native/report route until QA completes.
3. Keep native ERPNext forms/reports available to authorised advanced users where they provide legitimate advanced capability.
4. EdgeSuite-only users must not be forced into native Desk to complete ordinary supported work.
5. Route changes must never alter accounting, stock, allocation, reconciliation or submission semantics.

## Confirmed immediate recovery candidates

### RIR2A — Runtime blockers

Repair only confirmed browser-runtime defects first so subsequent UI QA is meaningful.

1. Transaction Workspace current-user fullname resolution must be Frappe-v16 compatible.
2. Add a regression test that executes/validates the context path without assuming `frappe.get_user()` exposes a User document API.
3. Verify Professional Selling loads `retailedge_edgesuite_only_operational_guard.bundle.js` and that `window.retailedgeInstallEdgesuiteOnlyOperationalGuard` is registered after asset load.
4. Treat local guard failure as asset/build/loader verification unless source evidence shows otherwise. Do not remove the guard to make the page load.

### RIR2B — Route/promotion matrix

Create one current navigation matrix before changing routes:

`Business operation | current target | available RetailEdge Page | parity/QA state | everyday target | advanced native fallback | access mode | MVP disposition`

First confirmed correction candidate:

- `Bank Matching`: `Report: RetailEdge Bank Transaction Matching` -> `Page: bank-matching-reconciliation` after focused browser/asset/access verification.

Do not promote Stock Movement History until its previously documented parity gate is completed.

### RIR2C — Keyboard command recovery

Recover against the current shared EdgeSuite runtime:

- Ctrl/Cmd+K -> current command palette/search contract where supported.
- Ctrl/Cmd+S -> current context-aware safe save.
- Submitted documents must not be mutated by the shortcut.
- Do not use `ignore_permissions`, direct DB writes or generic client-save bypasses.
- Avoid intercepting editable controls in ways that break normal browser/input behaviour.

### RIR2D — Navigation canonicalisation

After the route matrix is frozen:

- deduplicate by canonical target rather than display label where duplicates are accidental;
- retain an alias only when it represents a deliberate workflow distinction;
- keep technical child-table DocTypes out of normal navigation;
- add regression coverage so workspace sync cannot reintroduce duplicate/native routes that were deliberately promoted.

### RIR2E — Consolidated browser/persona QA

Run only after RIR2A–D are green.

Minimum personas/context cases:

- Owner / RetailEdge Manager
- Branch Manager
- Cashier
- Accounts User / Manager
- Stock / Store user
- Purchasing user
- Sales user
- restricted user with exactly one permitted Branch
- restricted user with multiple permitted Branches
- restricted user with zero permitted Branches
- unrestricted/advanced Native Desk user

Minimum browser checks:

- Business Hub and product menu load
- Universal `+ Create` visible only when permitted
- searchable Create works and filters only permitted actions
- each guided everyday form opens and creates only a draft/native-authoritative document
- Professional Selling / Purchasing / Payment Management / Banking load
- Bank Matching opens the intended RetailEdge banking surface
- no accidental native-Desk escape for EdgeSuite-only users
- advanced users retain intended native fallback
- company/branch context changes clear invalid dependent choices
- direct URL restrictions remain effective
- light/dark mode and mobile/tablet layouts

## B4B26 disposition

B4B26 — Payment Management customer-advance read-scope hardening — remains valid pending work. It is **deferred, not cancelled**.

Do not start B4B26 until:

1. RIR1 is frozen;
2. confirmed reconciliation/runtime defects are repaired in bounded recovery slices;
3. the route matrix is stable enough that B4B26 is hardening the surface that will actually ship.

## Tests required for recovery implementation

Every implementation slice after RIR1 must include the smallest focused regression suite plus the full PR #55 gates appropriate to the change:

- focused unit/contract tests;
- Frappe v16 test path for backend/runtime compatibility changes;
- navigation/access tests for route promotions;
- EdgeSuite UI candidate compatibility for product-menu/page changes;
- Theme Compatibility for visible UI changes;
- Linters / pre-commit / Semgrep / dependency audit;
- full RetailEdge suite before each frozen recovery checkpoint;
- local `retail.local` browser QA before final persona freeze.

No migration is expected for the currently identified RIR2A–D fixes unless the route audit uncovers a genuine schema/fixture requirement. Any migration introduced later must be idempotent.

## Things not to change during reconciliation recovery

- Do not merge PR #55 yet.
- Do not merge old branches wholesale.
- Do not start MVP reporting.
- Do not redesign the Business Hub during RIR; the planned smart role-aware MVP Business Hub enhancement follows the reconciliation baseline.
- Do not replace ERPNext ledgers, pricing engines, reconciliation, Payment Entry allocation, Stock Entry posting or native submission rules.
- Do not weaken B3/B4 Branch/Company scope to make UI tests pass.
- Do not expose CoreEdge/platform controls to ordinary RetailEdge users.

## Recommended bounded implementation order

1. **RIR2A1 — Transaction Workspace Frappe v16 runtime fix + regression test.**
2. **RIR2A2 — Professional Selling operational-guard asset/load verification and focused fix only if needed.**
3. **RIR2B1 — Freeze complete route/promotion matrix; no broad rewrites.**
4. **RIR2B2 — Correct confirmed Bank Matching route and add route/access regression coverage.**
5. **RIR2B3 — Apply only additional route promotions proven safe by the matrix; one bounded group at a time.**
6. **RIR2C — Recover current-compatible keyboard command contract.**
7. **RIR2D — Canonical navigation deduplication and anti-regression tests.**
8. **RIR2E — Local browser/persona QA and blocker-only fixes.**
9. Freeze the final reconciled hardening baseline.
10. Resume B4B26 only if still required against the final shipping Payment Management surface, then complete remaining hardening.
11. Continue MVP work: feature-disable/CoreEdge-ready registry -> planned Business Hub enhancement -> minimum MVP reports -> launch QA -> RC1.

## RIR1 conclusion

The reconciliation did not lose the majority of the RetailEdge usability programme. The current tree contains Universal Create, fuzzy searchable Create, guided transaction dialogs, numerous EdgeSuite operational Pages and the Banking workspace. The most important remaining problems are **runtime compatibility, route promotion/composition, one genuinely missing keyboard-command slice, and final browser/persona validation**.

Therefore the safe strategy is to repair and reconnect the current reconciled product rather than reconstruct it from old branches.
