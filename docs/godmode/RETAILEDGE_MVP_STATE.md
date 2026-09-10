# RetailEdge MVP Godmode Execution State

**Product:** RetailEdge  
**Owner:** ProcessEdge Solutions Limited  
**Governing contract:** RetailEdge MVP Godmode Contract — Draft V1.1  
**Repository:** `olayemigod/RetailEdge`  
**Active PR:** #55 — `QA reconciliation: clean E16 composition into consolidated RetailEdge candidate`  
**Branch:** `qa/retailedge-reconciled-20260902`  
**PR base:** `qa/retailedge-consolidated-20260829`  
**Latest code-frozen implementation head:** `6479ea7bec79957758b4b611754b01a120c23921`

> This ledger records execution state only. It does not amend, rename, or silently promote the Product Owner's Draft V1.1 Godmode contract.

## Repository Authority

The current repository, governed tests, migrations, and this execution ledger are the engineering source of truth. Chat history and memory are supporting context only. If repository evidence conflicts with an older chat checkpoint, inspect and reconcile the repository before modifying RetailEdge.

## Current MVP Phase

**Phase 1 — Readiness Hardening**

Current focus is EdgeSuite-first operational ownership, Native Desk containment, permission-safe navigation, and preservation of reconciled branch/access contracts before reporting expansion proceeds.

Business Hub implementation already exists, but its existence does not bypass unfinished hardening, QA, security, or release gates.

## Current Code-Frozen Slice

### `RIR2F3F15` — Customer Receivables native-review containment

**State:** `CODE-FROZEN / QA-PENDING`

Commits:

- `e5f628eb5dca150fe1a86d039d9eb5223115786b` — F3F15 contract/documentation
- `5642a05dcf7e4fdb9e41fffcb0b1cccc174fc4b2` — focused F3F15 contract tests
- `6479ea7bec79957758b4b611754b01a120c23921` — implementation

Material files:

- `docs/rir2f3f15_customer_receivables_native_review_containment.md`
- `retailedge/tests/test_rir2f3f15_customer_receivables_native_review_containment_contract.py`
- `retailedge/public/js/customer_receivables/CustomerReceivablesReport.vue`

Contract now enforced:

- Customer Receivables reads final `navigation.access.can_use_native_desk` into a fail-closed client capability.
- Sales Invoice, Customer, Payment Request, and Dunning detail cells are only presented as clickable when Native Desk is available.
- Payment Request and Dunning draft-preparation actions are only exposed when Native Desk is available because their lifecycle requires native ERPNext review/submission.
- `prepareCollectionAction()` fails before the POST when Native Desk is unavailable, preventing unreachable native drafts from being created for EdgeSuite-only users.
- DocType/Report menu routes and programmatic report-cell native routes fail closed without Native Desk capability.
- Native-Desk-capable users retain the existing native draft preparation/review flow.
- Backend accounting safety, branch validation, permission checks, duplicate prevention, submitted/outstanding invoice checks, and draft-only behavior remain unchanged.
- No accounting, GL, Sales Invoice mutation, migration, patch, or data semantics changed.

## Governed Evidence at `6479ea7`

GitHub Actions associated with the exact F3F15 implementation head are green:

| Gate | Run | Result |
| --- | ---: | --- |
| EdgeSuite UI Candidate Compatibility | 34442787460 | PASS |
| CI — clean Frappe v16 standalone integration | 34442787457 | PASS |
| RetailEdge Theme Compatibility | 34442787458 | PASS |
| Linters / Semgrep / vulnerable dependency audit | 34442787463 | PASS |

F3F15 introduced no migration or data patch.

## Prior Code-Frozen Slices

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

Browser/persona QA is not claimed as complete. Before F3F11–F3F15 may be represented as fully `FROZEN`, verify at minimum:

- authenticated Native Desk allowed and denied personas;
- ordinary EdgeSuite users cannot escape through guarded DocType/Report/create/record-row handoffs;
- Cash Shift native-detail columns do not open native forms for EdgeSuite-only users;
- Stock Position Item and Material Request actions remain non-operational for EdgeSuite-only users;
- Purchase Reporting native invoice/supplier detail links remain unavailable for EdgeSuite-only users while EdgeSuite supplier payment still works;
- Customer Receivables does not expose native detail/draft actions or issue collection POSTs for denied Native Desk users;
- Native-Desk-capable Customer Receivables users retain Payment Request/Dunning draft review flow;
- permitted advanced/native-Desk users retain intended ERPNext lifecycle handoffs;
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

## Successor Audit Finding — Professional Purchasing

Professional Purchasing is not equivalent to the simple native-detail leaks already contained in F3F11–F3F15. The main page includes multiple end-to-end operational flows that deliberately prepare ERPNext drafts and then rely on native forms/reports for completion or review, including RFQ, Purchase Receipt, purchase returns, supplier debit notes, Landed Cost Voucher, Purchase Order, Material Request, Supplier Quotation, Purchase Order Analysis, Procurement Tracker, and Purchase Receipt navigation.

The repository also contains newer Professional Purchasing overlays/components from the earlier RIR2F2 sequence. The next task must determine which native handoffs are already superseded by EdgeSuite-owned overlays, which are intentional advanced fallbacks, and which represent unfinished EdgeSuite operational ownership. Do not blanket-disable them before this reconciliation because that could remove core purchasing capability from ordinary users.

## Unresolved / Not Yet Claimed

- F3F11–F3F15 browser/persona QA remain pending.
- Overall Readiness Hardening is not complete.
- Business Hub is not release-complete merely because implementation exists.
- Reporting expansion remains downstream of unresolved foundational hardening.
- Fresh-install, upgrade, cross-workflow, release-hardening, rollback, and final MVP freeze gates remain later MVP requirements unless repository evidence explicitly freezes them.

## Prohibited Shortcuts

Do not obtain a green state by disabling meaningful tests, weakening valid assertions, suppressing real errors, converting restricted-zero into unrestricted access, relying on frontend-only security for protected business rules, mutating submitted accounting documents, duplicating ERPNext accounting/stock/planning truth, or bypassing execution order with non-blocking features.

## Exact Next Executable Step

Perform a dedicated **Professional Purchasing ownership reconciliation audit** before defining another implementation slice.

Required audit:

1. Map each user-facing purchasing action in `ProfessionalPurchasing.vue` to its backend API, native ERPNext destination, and any existing EdgeSuite overlay/component.
2. Inspect the RIR2F2 purchase-invoice, purchase-receipt, RFQ, supplier-quotation, and purchase-order ownership components/tests/docs already present on the branch.
3. Classify each action as:
   - `EDGESUITE_OWNED` — ordinary-user workflow is already complete in EdgeSuite;
   - `ADVANCED_NATIVE_FALLBACK` — native ERPNext is intentionally retained only for authorized advanced users;
   - `OWNERSHIP_GAP` — ordinary-user workflow still depends on native Desk and requires EdgeSuite completion before containment;
   - `READ_ONLY_NATIVE_DETAIL` — native detail/navigation only and safe to contain separately.
4. Do not remove a native handoff that is currently the only viable completion path for an ordinary-user purchasing workflow.
5. If repository evidence identifies a bounded ownership gap with an existing EdgeSuite replacement, define the smallest next F3 slice and implement it with focused tests.
6. If a workflow requires material product/architecture change rather than reconciliation, record the gap and escalate under the mandatory stop boundary rather than silently redesigning purchasing.
