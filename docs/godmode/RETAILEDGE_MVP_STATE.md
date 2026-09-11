# RetailEdge MVP Godmode Execution State

**Product:** RetailEdge  
**Owner:** ProcessEdge Solutions Limited  
**Governing contract:** RetailEdge MVP Godmode Contract — Draft V1.1  
**Repository:** `olayemigod/RetailEdge`  
**Active PR:** #55 — `QA reconciliation: clean E16 composition into consolidated RetailEdge candidate`  
**Branch:** `qa/retailedge-reconciled-20260902`  
**PR base:** `qa/retailedge-consolidated-20260829`  
**Latest code-frozen exact head:** `5ee298346a133ffeec202c343bc70aa2fd3869dd`

> This ledger records execution state only. It does not amend, rename, or silently promote the Product Owner's Draft V1.1 Godmode contract.

## Repository Authority

The current repository, governed tests, migrations, and this execution ledger are the engineering source of truth. Chat history and memory are supporting context only. If repository evidence conflicts with an older chat checkpoint, inspect and reconcile the repository before modifying RetailEdge.

## Current MVP Phase

**Phase 1 — Readiness Hardening**

Current focus is EdgeSuite-first operational ownership, Native Desk containment, permission-safe navigation, and preservation of reconciled branch/access contracts before reporting expansion proceeds.

Business Hub implementation already exists, but its existence does not bypass unfinished hardening, QA, security, or release gates.

## Current Code-Frozen Slice

### `RIR2F3F41` — Landed Cost Voucher EdgeSuite Ownership

**State:** `CODE-FROZEN / QA-PENDING`

Frozen exact head:

- `5ee298346a133ffeec202c343bc70aa2fd3869dd`

Primary contract/runtime files:

- `docs/rir2f3f41_landed_cost_voucher_edgesuite_ownership.md`
- `retailedge/landed_cost_allocation.py`
- `retailedge/public/js/professional_purchasing/ProfessionalPurchasing.vue`
- `retailedge/retailedge/page/professional_purchasing/professional_purchasing.js`
- focused F3F41 backend/UI/operational-guard contract tests

Contract now enforced:

- one permitted submitted Purchase Receipt or stock-updating Purchase Invoice is supported by the standard EdgeSuite flow;
- standard allocation supports Amount or Qty; manual distribution remains Advanced ERPNext;
- standard charge input is limited to Company-valid ERPNext-compatible expense account, description and positive amount;
- ERPNext native Landed Cost Voucher validation remains authoritative for currency, exchange rate, base amount, totals, proportional allocation, cost centres and mandatory dimensions;
- review is persistence-free;
- draft start is source-locked, stale-protected and duplicate-safe, reusing at most one standard-equivalent linked draft;
- native submit remains authoritative where no active Frappe Workflow exists; active Workflow delegates through F3F27 and Frappe `apply_workflow()`;
- submitted retry is idempotent on the exact named voucher;
- fixed assets, vendor-invoice claims, multi-source, manual allocation, custom dimension overrides, cancellation/amendment and unsupported source types fail closed to Advanced ERPNext;
- EdgeSuite-only users can complete the standard flow while native Landed Cost Voucher routes remain guarded;
- no schema migration, direct GL/SLE mutation, direct `update_landed_cost()`, `ignore_permissions` or manual commit was introduced.

## Governed Evidence at `5ee29834`

GitHub Actions associated with the exact F3F41 freeze head are green:

| Gate | Run | Result |
| --- | ---: | --- |
| EdgeSuite UI Candidate Compatibility | 34608209861 | PASS |
| CI — clean Frappe v16 standalone integration | 34608209941 | PASS |
| RetailEdge Theme Compatibility | 34608209835 | PASS |
| Linters / Semgrep / vulnerable dependency audit | 34608209866 | PASS |

The first two F3F41 validation attempts exposed only malformed/stale contract-test assertions. Those test-only defects were corrected without weakening runtime assertions. The final exact head above passed the complete governed suite.



## Prior Code-Frozen Slices

### `RIR2F3F40` — Incoming Quality Inspection EdgeSuite Ownership Hardening

**State:** `CODE-FROZEN / QA-PENDING`

- Frozen exact head: `82d621d2795db0052b1f7b7b482d7e625c69e70e`
- Exact-head gates: EdgeSuite `34588724646`, CI `34588724581`, Theme `34588724571`, Linters `34588724624` — all PASS.
- Active Quality Inspection Workflow owns approval progression; no-Workflow sites retain standard insert + submit.
- Draft start/reuse is exact-row idempotent and stale/source/template/readings protected.
- ERPNext remains authoritative for inspection status and source linkage.
- No schema migration.


### `RIR2F3F39` — Purchase Return / Supplier Debit Note Workflow Precedence

**State:** `CODE-FROZEN / QA-PENDING`

- Frozen exact head: `738800bc087124f598dcdd1f22b2d30b0b78561d`
- Exact-head gates: EdgeSuite `34579395120`, CI `34579395000`, Theme `34579395023`, Linters `34579395156` — all PASS.
- Active Purchase Receipt / Purchase Invoice Workflow owns the corresponding standard return/debit-note progression.
- Preview remains persistence-free; Workflow mode persists or idempotently reuses exactly one standard return draft.
- ERPNext remains authoritative for stock, valuation, tax, payable and accounting consequences.
- No schema migration.


### `RIR2F3F38` — Purchase Invoice Workflow Precedence

**State:** `CODE-FROZEN / QA-PENDING`

- Frozen exact head: `a1ebc536c99cd609e4179f49bf73f7eb88f98b94`
- Exact-head gates: EdgeSuite `34578567764`, CI `34578567779`, Theme `34578567789`, Linters `34578567830` — all PASS.
- Active Purchase Invoice Workflow owns F3F20 Supplier Document → Purchase Invoice progression; generic Guided Purchase Invoice remains draft-only.
- Direct F3F20 submit remains only for sites without an active Workflow; active Workflow exposes only Frappe-permitted actions on the exact immutable handed-off draft.
- ERPNext remains authoritative for Purchase Invoice accounting/payable effects.
- No schema migration.

### `RIR2F3F37` — Purchase Receipt Workflow Precedence

**State:** `CODE-FROZEN / QA-PENDING`

- Frozen exact head: `c68ca887c157f0743c939ba650b4c2b4132a1afb`
- Exact-head gates: EdgeSuite `34576828352`, CI `34576828410`, Theme `34576828386`, Linters `34576828356` — all PASS.
- Active Frappe Workflow owns standard Purchase Receipt progression; no-Workflow sites retain the existing ERPNext insert + submit path.
- Workflow mode persists or idempotently reuses exactly one standard Purchase Receipt draft; duplicate/non-standard/advanced stock cases fail closed.
- ERPNext remains authoritative for Purchase Receipt stock/accounting effects.
- No schema migration.

### `RIR2F3F16` — Professional Purchasing existing-ownership reconciliation

**State:** `CODE-FROZEN / QA-PENDING`

Primary commits:

- `b45c1339b16c7b0f127790ec9c2a264c0ceb3622` — F3F16 contract/documentation
- `2773d22b6b7d56e16b1f28beb85bb29e2e386000` — focused F3F16 contract tests
- `0dafe3b2a95e02de901fdb46f128f3a189ab2571` — initial stale Professional Purchasing UI test reconciliation
- `7a31415a42073e6a2cd0fcc650ce4e953fce92c3` — runtime implementation

Governed-suite recovery commits:

- `21bef4aa960c3ffee88bd87547e4c27126c84295` — reconcile Purchase Receipt parity test with EdgeSuite ownership
- `45f9f288a5c05f5e341e03bd08ac3a290a02f45c` — reconcile Procurement Tracker handoff test
- `d1b0ec9fbb1555b228ce771e305a25c0d6f3d039` — reconcile prereporting Procurement Tracker composition test
- `44451caa53fc64ce92bf739641bb0a472670d483` — scope Professional Purchasing standard-receipt assertions without removing Purchase Return completion
- `b9dbd8a6f273f60d0c3f7e5b4bb8166534d821d4` — explicitly preserve the then-unresolved Purchase Return ownership gap in the focused contract

Exact-head gates at `b9dbd8a6`: EdgeSuite `34448567476`, CI `34448567467`, Theme `34448567527`, Linters `34448567489` — all PASS.

F3F16 reconciled New Purchase Order, RFQ, Supplier Quotation, PO submit and Purchase Receipt workflows with already-existing EdgeSuite owners; advanced Material Request/PO detail/comparison/analysis/tracker handoffs remain Native Desk-capability-gated. It introduced no migration or accounting/stock lifecycle change.

### `RIR2F3F15` — Customer Receivables native-review containment

**State:** `CODE-FROZEN / QA-PENDING`

- Contract: `e5f628eb5dca150fe1a86d039d9eb5223115786b`
- Tests: `5642a05dcf7e4fdb9e41fffcb0b1cccc174fc4b2`
- Implementation: `6479ea7bec79957758b4b611754b01a120c23921`
- Exact-head gates: EdgeSuite `34442787460`, CI `34442787457`, Theme `34442787458`, Linters `34442787463` — all PASS.

### `RIR2F3F14` — Purchase Reporting native-detail containment

**State:** `CODE-FROZEN / QA-PENDING`

- Contract: `c072afa97e349504f55fc946d689987c0843518d`
- Tests: `a63a558bce82ff384c95460ad95800515ff1fd05`
- Implementation: `71624838c4320e1eda8e51630452ea988da4fa3b`
- Exact-head gates: EdgeSuite `34442297752`, CI `34442297749`, Theme `34442297743`, Linters `34442297744` — all PASS.

### `RIR2F3F13` — Stock Position native-handoff containment

**State:** `CODE-FROZEN / QA-PENDING`

- Contract: `5eb4d970c09f34779700a1ce46f64a7b690f6e57`
- Tests: `983d6bc66ea3904e23e53f87870e64a173b40dca`
- Implementation: `6412ce1f217ca5b37161c83de81460e2b6bfd2f8`
- Exact-head gates: EdgeSuite `34441475130`, CI `34441475141`, Theme `34441475139`, Linters `34441475131` — all PASS.

### `RIR2F3F12` — Cash Shift native-detail containment

**State:** `CODE-FROZEN / QA-PENDING`

- Contract: `a2a8becd90048007eb7572cb03b1a9bd0b5722b9`
- Tests: `ec34e0b601cc759f4edd6b22e84774381dab4a1c`
- Implementation: `8dde2a2efbfed10b3f2b7742ce4bfc8139ffbe6c`
- Exact-head gates: EdgeSuite `34440908251`, CI `34440908315`, Theme `34440908296`, Linters `34440908311` — all PASS.

### `RIR2F3F11` — Native visual workspace Desk handoff containment

**State:** `CODE-FROZEN / QA-PENDING`

- Contract: `be7dc70d`
- Tests: `95d744cc`
- Implementation: `0cf1418192f3d9a1f808fc606fb7f00e929c5033`
- Exact-head governed gates were green.

## Deferred QA

Browser/persona QA is not claimed as complete. Before F3F11–F3F17 may be represented as fully `FROZEN`, verify at minimum:

- authenticated Native Desk allowed and denied personas;
- ordinary EdgeSuite users cannot escape through guarded DocType/Report/create/record-row handoffs;
- Cash Shift native-detail columns do not open native forms for EdgeSuite-only users;
- Stock Position Item and Material Request actions remain non-operational for EdgeSuite-only users;
- Purchase Reporting native invoice/supplier detail links remain unavailable for EdgeSuite-only users while EdgeSuite supplier payment still works;
- Customer Receivables does not expose native detail/draft actions or issue collection POSTs for denied Native Desk users;
- Native-Desk-capable Customer Receivables users retain Payment Request/Dunning draft review flow;
- Professional Purchasing ordinary users enter the EdgeSuite PO, RFQ, Supplier Quotation and Purchase Receipt flows rather than stale native draft paths;
- Professional Purchasing advanced users retain intended Material Request, PO detail, comparison/analysis/tracker and other authorized native fallbacks;
- EdgeSuite-only Purchase Return persona can review and submit a permitted standard Purchase Receipt return without Native Desk;
- EdgeSuite-only Supplier Debit Note persona can review and submit a permitted standard Purchase Invoice return/debit note without Native Desk;
- F3F17 submitted source documents remain unchanged and created return documents have correct `is_return` / `return_against`, Company, Supplier, Branch and negative quantities;
- F3F17 stock/accounting effects are produced only by ERPNext submit;
- stale F3F17 preview is rejected after source change;
- Serial/Batch-controlled F3F17 return is blocked from standard completion without creating a draft;
- restricted branch and restricted-zero personas fail closed server-side;
- Native Desk-capable F3F17 persona sees and can use the explicit advanced fallback;
- Incoming Quality Inspection standard EdgeSuite review/workflow remains reachable for permitted personas;
- EdgeSuite Page destinations remain usable after containment.

## Frozen Product Baseline

Unless explicitly changed by the Product Owner:

- EdgeSuite UI is the normal RetailEdge operational experience.
- ERPNext remains the accounting, stock, selling, purchasing, and operational backbone where appropriate.
- Restricted branch users with one permitted branch may auto-resolve that branch.
- Restricted branch users with multiple permitted branches must choose an explicit branch.
- Restricted branch users with zero permitted branches fail closed; restricted-zero must never become unrestricted.
- Active Branch Assignments are authoritative where assignment history exists; legacy behavior is fallback only where assignment history does not exist.
- Security-sensitive branch and permission rules are enforced server-side; frontend filtering is not security.
- Stock Entry remains an ERPNext-native draft workflow unless explicitly changed.
- Reporting must consume reconciled and hardened operational contracts.
- Business Hub is mandatory before MVP release.

## Mandatory Stop Boundary

Escalate before materially changing MVP scope, major architecture, branch architecture, tenancy, accounting/GL semantics, stock ledger/valuation/posting semantics, authentication/security boundaries, destructive production data, irreversible migrations, or conflicting approved requirements.

Routine contract-preserving fixes, tests, documentation, regression correction, and security strengthening remain autonomously executable.

## Slice State Convention

- `ACTIVE` — implementation or investigation is in progress.
- `BLOCKED` — an external dependency or mandatory stop condition prevents progress.
- `CODE-FROZEN / QA-PENDING` — implementation and applicable automated gates are green, but required manual/browser/persona evidence remains outstanding.
- `FROZEN` — implementation, applicable automated gates, required QA evidence, documentation, and migration requirements are complete.

## Successor Ownership Gaps — Professional Purchasing

F3F16–F3F41 now cover the identified standard Professional Purchasing ownership gaps through purchase order, receipt, invoice handoff, returns/debit notes, payment/workflow parity, expenses, incoming quality inspection and standard landed cost, subject to deferred browser/persona QA.

No additional Professional Purchasing ownership gap is currently claimed from repository evidence. Advanced ERPNext remains deliberate for the bounded exceptional cases documented by each frozen slice.



## Unresolved / Not Yet Claimed

- F3F11–F3F17 browser/persona QA remain pending.
- Professional Purchasing automated ownership hardening is complete through F3F41; consolidated browser/persona acceptance remains pending.
- Overall Readiness Hardening is not complete.
- Business Hub is not release-complete merely because implementation exists.
- Reporting expansion remains downstream of unresolved foundational hardening.
- Fresh-install, upgrade, cross-workflow, release-hardening, rollback, and final MVP freeze gates remain later MVP requirements unless repository evidence explicitly freezes them.

## Prohibited Shortcuts

Do not obtain a green state by disabling meaningful tests, weakening valid assertions, suppressing real errors, converting restricted-zero into unrestricted access, relying on frontend-only security for protected business rules, mutating submitted accounting documents, duplicating ERPNext accounting/stock/planning truth, or bypassing execution order with non-blocking features.

## Exact Next Executable Step

Perform **RIR2F3F42 — Readiness Hardening Closure Audit** before starting reporting or treating Phase 1 as complete.

Required audit:

1. Reconcile every original Readiness Hardening blocker against the current authoritative branch, governed tests and EdgeSuite routing:
   - branch composition / authoritative reconciled line;
   - ordinary-role Desk access and EdgeSuite-only runtime;
   - guided Stock Transfer branch enforcement;
   - EdgeSuite operational page ownership;
   - Native Desk containment;
   - workflow precedence;
   - standard Professional Purchasing completion through F3F41.
2. Inventory all remaining native DocType/report/form handoffs reachable from ordinary EdgeSuite personas and classify each as:
   - `EDGESUITE_OWNED`;
   - `INTENTIONAL_ADVANCED_NATIVE`;
   - `READINESS_BLOCKER`;
   - `DEFERRED_NON_MVP`.
3. Inspect Business Hub only for readiness dependency/composition; do not expand Business Hub features in this audit.
4. Verify restricted-zero and Branch/Company fail-closed contracts remain server-side across the operational surfaces used by Phase 1.
5. Verify no submitted accounting/stock document is mutated by standard EdgeSuite preparation/review flows outside normal ERPNext lifecycle methods.
6. Identify stale tests/docs/guards that still describe superseded ownership and reconcile them only where repository evidence proves the new contract.
7. Produce a bounded F3F42 closure matrix and automated contract checks. Do not invent feature work merely to eliminate deliberate Advanced ERPNext fallbacks.
8. If any true P0/P1 Readiness blocker is found, fix the smallest blocker first and rerun the four governed exact-head gates.
9. If no automated blocker remains, mark Phase 1 **CODE-COMPLETE / CONSOLIDATED QA-PENDING**, preserve the deferred browser/persona checklist for RIR2E, and select the next MVP phase strictly from the Godmode execution order.
