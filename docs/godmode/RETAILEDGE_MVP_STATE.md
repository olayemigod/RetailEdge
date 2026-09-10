# RetailEdge MVP Godmode Execution State

**Product:** RetailEdge  
**Owner:** ProcessEdge Solutions Limited  
**Governing contract:** RetailEdge MVP Godmode Contract — Draft V1.1  
**Repository:** `olayemigod/RetailEdge`  
**Active PR:** #55 — `QA reconciliation: clean E16 composition into consolidated RetailEdge candidate`  
**Branch:** `qa/retailedge-reconciled-20260902`  
**PR base:** `qa/retailedge-consolidated-20260829`  
**Latest code-frozen implementation head:** `71624838c4320e1eda8e51630452ea988da4fa3b`

> This ledger records execution state only. It does not amend, rename, or silently promote the Product Owner's Draft V1.1 Godmode contract.

## Repository Authority

The current repository, governed tests, migrations, and this execution ledger are the engineering source of truth. Chat history and memory are supporting context only. If repository evidence conflicts with an older chat checkpoint, inspect and reconcile the repository before modifying RetailEdge.

## Current MVP Phase

**Phase 1 — Readiness Hardening**

Current focus is EdgeSuite-first operational ownership, Native Desk containment, permission-safe navigation, and preservation of reconciled branch/access contracts before reporting expansion proceeds.

Business Hub implementation already exists, but its existence does not bypass unfinished hardening, QA, security, or release gates.

## Current Code-Frozen Slice

### `RIR2F3F14` — Purchase Reporting native-detail containment

**State:** `CODE-FROZEN / QA-PENDING`

Commits:

- `c072afa97e349504f55fc946d689987c0843518d` — F3F14 contract/documentation
- `a63a558bce82ff384c95460ad95800515ff1fd05` — focused F3F14 contract tests
- `71624838c4320e1eda8e51630452ea988da4fa3b` — implementation

Material files:

- `docs/rir2f3f14_purchase_reporting_native_detail_containment.md`
- `retailedge/tests/test_rir2f3f14_purchase_reporting_native_detail_containment_contract.py`
- `retailedge/public/js/purchase_reporting/PurchaseReportingReport.vue`

Contract now enforced:

- Purchase Reporting continues to use the fail-closed `canUseNativeDesk` capability sourced from final EdgeSuite navigation access context.
- Purchase Invoice, return-against, and Supplier cells are only presented as native-detail clickable when Native Desk is available.
- DocType/Report menu handoffs fail closed without Native Desk capability.
- Programmatic report-cell events fail closed before native Purchase Invoice/Supplier routing.
- The EdgeSuite supplier-payment `payment_action` remains operational regardless of Native Desk capability.
- The explicit native Payment Entry fallback remains separately gated by Native Desk capability.
- No report calculation, outstanding balance, payment posting, branch scope, accounting, migration, or data semantics changed.

## Governed Evidence at `7162483`

GitHub Actions associated with the exact F3F14 implementation head are green:

| Gate | Run | Result |
| --- | ---: | --- |
| EdgeSuite UI Candidate Compatibility | 34442297752 | PASS |
| CI — clean Frappe v16 standalone integration | 34442297749 | PASS |
| RetailEdge Theme Compatibility | 34442297743 | PASS |
| Linters / Semgrep / vulnerable dependency audit | 34442297744 | PASS |

F3F14 introduced no migration or data patch.

## Prior Code-Frozen Slices

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

Browser/persona QA is not claimed as complete. Before F3F11–F3F14 may be represented as fully `FROZEN`, verify at minimum:

- authenticated Native Desk allowed and denied personas;
- ordinary EdgeSuite users cannot escape through guarded DocType/Report/create/record-row handoffs;
- Cash Shift native-detail columns do not open native forms for EdgeSuite-only users;
- Stock Position Item and Material Request actions remain non-operational for EdgeSuite-only users;
- Purchase Reporting native invoice/supplier detail links remain unavailable for EdgeSuite-only users while EdgeSuite supplier payment still works;
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

## Successor Audit Findings

1. **Customer Receivables:** invoice/customer/payment-request/dunning detail links and native-draft collection actions do not apply final Native Desk capability. The backend is already strong: submitted/outstanding invoice checks, company permission, branch revalidation, native create/read permission, duplicate prevention, and draft-only behavior are enforced. The identified gap is frontend exposure. EdgeSuite-only users must be stopped before the POST that creates a native draft they cannot review.
2. **Professional Purchasing and related overlays:** multiple draft-creation and review workflows deliberately terminate in native ERPNext forms/reports. This is a larger ownership boundary and must receive a dedicated audit rather than a blanket route-guard patch.

## Unresolved / Not Yet Claimed

- F3F11–F3F14 browser/persona QA remain pending.
- Overall Readiness Hardening is not complete.
- Business Hub is not release-complete merely because implementation exists.
- Reporting expansion remains downstream of unresolved foundational hardening.
- Fresh-install, upgrade, cross-workflow, release-hardening, rollback, and final MVP freeze gates remain later MVP requirements unless repository evidence explicitly freezes them.

## Prohibited Shortcuts

Do not obtain a green state by disabling meaningful tests, weakening valid assertions, suppressing real errors, converting restricted-zero into unrestricted access, relying on frontend-only security for protected business rules, mutating submitted accounting documents, duplicating ERPNext accounting/stock/planning truth, or bypassing execution order with non-blocking features.

## Exact Next Executable Step

Execute `RIR2F3F15 — Customer Receivables native-review containment`.

Required implementation contract:

1. Add a fail-closed `canUseNativeDesk` capability populated from final `navigation.access.can_use_native_desk`.
2. Native Sales Invoice, Customer, Payment Request, and Dunning detail columns must only be clickable when Native Desk is available.
3. Native-draft collection action columns (`Prepare Payment Request`, `Prepare Dunning`) must only be exposed when Native Desk is available because those actions require native review/submission.
4. `prepareCollectionAction()` must fail closed before the POST when Native Desk is unavailable; do not create an unreachable draft as a side effect.
5. `openReportCell()` and DocType/Report menu handoffs must independently fail closed before native routing.
6. Preserve all current backend accounting, duplicate-prevention, branch, permission, draft-only, and invoice-safety checks; no backend semantic rewrite is required.
7. Native-Desk-capable users retain the current draft preparation and ERPNext review flow.
8. Add focused negative-path tests and documentation, then run all exact-head governed gates before marking F3F15 `CODE-FROZEN / QA-PENDING`.

After F3F15, audit Professional Purchasing ownership as a separate bounded decision before any implementation there.
