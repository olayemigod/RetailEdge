# RetailEdge MVP Godmode Execution State

**Product:** RetailEdge  
**Owner:** ProcessEdge Solutions Limited  
**Governing contract:** RetailEdge MVP Godmode Contract — Draft V1.1  
**Repository:** `olayemigod/RetailEdge`  
**Active PR:** #55 — `QA reconciliation: clean E16 composition into consolidated RetailEdge candidate`  
**Branch:** `qa/retailedge-reconciled-20260902`  
**PR base:** `qa/retailedge-consolidated-20260829`  
**Latest code-frozen exact head:** `82d621d2795db0052b1f7b7b482d7e625c69e70e`

> This ledger records execution state only. It does not amend, rename, or silently promote the Product Owner's Draft V1.1 Godmode contract.

## Repository Authority

The current repository, governed tests, migrations, and this execution ledger are the engineering source of truth. Chat history and memory are supporting context only. If repository evidence conflicts with an older chat checkpoint, inspect and reconcile the repository before modifying RetailEdge.

## Current MVP Phase

**Phase 1 — Readiness Hardening**

Current focus is EdgeSuite-first operational ownership, Native Desk containment, permission-safe navigation, and preservation of reconciled branch/access contracts before reporting expansion proceeds.

Business Hub implementation already exists, but its existence does not bypass unfinished hardening, QA, security, or release gates.

## Current Code-Frozen Slice

### `RIR2F3F40` — Incoming Quality Inspection EdgeSuite Ownership Hardening

**State:** `CODE-FROZEN / QA-PENDING`

Frozen exact head:

- `82d621d2795db0052b1f7b7b482d7e625c69e70e`

Primary contract/runtime files:

- `docs/rir2f3f40_incoming_quality_inspection_workflow_ownership.md`
- `retailedge/incoming_quality_inspection.py`
- `retailedge/public/js/professional_purchasing/IncomingQualityInspection.vue`
- `retailedge/tests/test_rir2f3f40_incoming_quality_inspection_workflow_ownership_contract.py`

Contract now enforced:

- the F3F18 persistence-free review and ERPNext template/readings authority remain intact;
- no-Workflow sites retain the existing standard Quality Inspection insert + submit path;
- active Frappe Workflow blocks direct submission and exposes Start Inspection Approval;
- workflow start row-locks/revalidates the Purchase Receipt, Branch/Company scope, current ERPNext inspection requirement, stale source snapshot, template/specifications and submitted readings;
- exactly one matching readable draft per Purchase Receipt child row may be reused idempotently; multiple, unreadable, foreign or non-standard drafts fail closed;
- ERPNext's native Quality Inspection source-link update is accounted for in lost-response retry handling without allowing unrelated stale source edits;
- saved-draft workflow actions row-lock/revalidate both source and inspection, exact linkage, standard inspection equivalence, stale source/target snapshots and expected workflow state;
- all transitions delegate through the shared F3F27 bridge to Frappe `apply_workflow()`;
- ERPNext remains authoritative for final Accepted/Rejected status and Purchase Receipt Quality Inspection linkage;
- EdgeSuite does not assign workflow state, inspection status or docstatus directly;
- Advanced: Prepare in ERPNext remains capability-gated to Native-Desk-capable users;
- no schema migration is required.

## Governed Evidence at `82d621d2`

GitHub Actions associated with the exact F3F40 freeze head are green:

| Gate | Run | Result |
| --- | ---: | --- |
| EdgeSuite UI Candidate Compatibility | 34588724646 | PASS |
| CI — clean Frappe v16 standalone integration | 34588724581 | PASS |
| RetailEdge Theme Compatibility | 34588724571 | PASS |
| Linters / Semgrep / vulnerable dependency audit | 34588724624 | PASS |

F3F40 is a bounded descendant of the F3F39 code-freeze. The intervening pre-F3F40 repository-state commit touched only this ledger; F3F40 itself adds the contract/test plus the existing Incoming Quality Inspection backend and EdgeSuite component changes.



## Prior Code-Frozen Slices

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
- Incoming Quality Inspection remains recognized as the next ownership gap rather than accidentally becoming unreachable;
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

F3F16–F3F40 now provide EdgeSuite ownership for the standard Professional Purchasing path through purchase order, receipt, invoice handoff, return/debit note, payment workflow parity, expense operations and incoming quality inspection, subject to deferred browser/persona QA.

Current unresolved classification:

1. **Landed Cost Voucher — `ADVANCED_NATIVE_FALLBACK / MVP OWNERSHIP REVIEW REQUIRED`**
   - the current handoff prepares an unsaved native Landed Cost Voucher and the panel is hidden in EdgeSuite-only mode;
   - no submitted accounting or stock document is mutated merely by opening the current handoff, so risk is lower than the former Quality Inspection draft-first gap;
   - however RetailEdge MVP intends EdgeSuite to be the normal operational experience, so a bounded ownership audit is required to decide whether standard Landed Cost allocation needs an EdgeSuite review/create path and what cases must remain Advanced ERPNext;
   - ERPNext valuation/reposting/accounting truth must remain authoritative.


## Unresolved / Not Yet Claimed

- F3F11–F3F17 browser/persona QA remain pending.
- Landed Cost remains advanced/native fallback pending the next bounded MVP ownership review.
- Overall Readiness Hardening is not complete.
- Business Hub is not release-complete merely because implementation exists.
- Reporting expansion remains downstream of unresolved foundational hardening.
- Fresh-install, upgrade, cross-workflow, release-hardening, rollback, and final MVP freeze gates remain later MVP requirements unless repository evidence explicitly freezes them.

## Prohibited Shortcuts

Do not obtain a green state by disabling meaningful tests, weakening valid assertions, suppressing real errors, converting restricted-zero into unrestricted access, relying on frontend-only security for protected business rules, mutating submitted accounting documents, duplicating ERPNext accounting/stock/planning truth, or bypassing execution order with non-blocking features.

## Exact Next Executable Step

Perform a bounded repository audit for **RIR2F3F41 — Landed Cost Voucher EdgeSuite Ownership Review**.

Required next audit:

1. Trace the complete current Landed Cost flow in Professional Purchasing, including source Purchase Receipts/Purchase Invoices, charge capture, allocation, any native mapper/handoff and persistence side effects.
2. Confirm whether the current handoff is truly unsaved/persistence-free and whether any source document is modified before native submission.
3. Identify the smallest standard EdgeSuite-owned flow that can safely review and create/submit a Landed Cost Voucher if MVP ownership is warranted.
4. Preserve ERPNext Landed Cost Voucher allocation, valuation reposting, stock ledger and accounting truth; never duplicate those calculations in RetailEdge.
5. Apply Company/Branch/source-document filtering and backend validation so users can select only permitted compatible receipts/invoices.
6. Reuse F3F27 workflow precedence if Landed Cost Voucher has an active Frappe Workflow; do not invent a RetailEdge workflow.
7. Fail closed to Advanced ERPNext for unsupported multi-company, incompatible source, complex tax/accounting override, cancellation/amendment or other advanced cases.
8. Keep reporting expansion, unrelated purchasing redesign and manual browser/persona QA outside this slice.
9. Define the smallest F3F41 contract from repository evidence, add focused tests, implement only the approved standard path, then run the same four governed exact-head gates before freeze.
