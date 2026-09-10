# RetailEdge MVP Godmode Execution State

**Product:** RetailEdge  
**Owner:** ProcessEdge Solutions Limited  
**Governing contract:** RetailEdge MVP Godmode Contract — Draft V1.1  
**Activation instruction:** Product Owner instruction in ChatGPT on 2026-09-10 to continue implementation from GitHub  
**Repository:** `olayemigod/RetailEdge`  
**Active PR:** #55 — `QA reconciliation: clean E16 composition into consolidated RetailEdge candidate`  
**Branch:** `qa/retailedge-reconciled-20260902`  
**PR base:** `qa/retailedge-consolidated-20260829`  
**Latest code-frozen implementation head:** `8dde2a2efbfed10b3f2b7742ce4bfc8139ffbe6c`

> This ledger records execution state only. It does not amend, rename, or silently promote the Product Owner's Draft V1.1 Godmode contract.

## Repository Authority

The current repository, governed tests, migrations, and this execution ledger are the engineering source of truth. Chat history and memory are supporting context only.

If repository evidence conflicts with an older chat checkpoint, PR narrative, or superseded document, inspect and reconcile the current repository before modifying RetailEdge. Do not resurrect superseded work from chat history.

## Current MVP Phase

**Phase 1 — Readiness Hardening**

Current hardening focus is EdgeSuite-first operational ownership, native Desk containment, permission-safe navigation, and preservation of the reconciled branch/access contracts before reporting work is allowed to proceed.

Business Hub code is already present on the reconciled branch, but its existence does not bypass unfinished readiness-hardening, QA, security, or release gates.

## Current Bounded Slice

### `RIR2F3F12` — Cash Shift native-detail containment

**State:** `CODE-FROZEN / QA-PENDING`

Commits:

- `a2a8becd90048007eb7572cb03b1a9bd0b5722b9` — F3F12 contract/documentation
- `ec34e0b601cc759f4edd6b22e84774381dab4a1c` — focused F3F12 contract tests
- `8dde2a2efbfed10b3f2b7742ce4bfc8139ffbe6c` — implementation

Material files:

- `docs/rir2f3f12_cash_shift_native_detail_containment.md`
- `retailedge/tests/test_rir2f3f12_cash_shift_native_detail_containment_contract.py`
- `retailedge/public/js/cash_shift_verification/CashShiftVerificationReport.vue`

Contract now enforced:

- Cash Shift Verification fails closed on Native Desk capability before navigation context resolves.
- Native-detail columns are not presented as clickable for EdgeSuite-only users.
- Direct row handoffs to Daily Sales Audit, User, POS Profile, POS Opening Shift, and POS Closing Shift are blocked when Native Desk is unavailable.
- DocType/Report menu handoffs are defensively blocked client-side in addition to server-side navigation filtering.
- Native-Desk-capable users retain the existing handoffs subject to normal Frappe/ERPNext permissions.
- No accounting, POS posting, branch-scope, document lifecycle, migration, or data semantics changed.

## Governed Evidence at `8dde2a2`

GitHub Actions associated with the exact F3F12 implementation head are green:

| Gate | Run | Result |
| --- | ---: | --- |
| EdgeSuite UI Candidate Compatibility | 34440908251 | PASS |
| CI — clean Frappe v16 standalone integration | 34440908315 | PASS |
| RetailEdge Theme Compatibility | 34440908296 | PASS |
| Linters / Semgrep / vulnerable dependency audit | 34440908311 | PASS |

F3F12 introduced no migration or data patch.

## Prior Code-Frozen Slice

### `RIR2F3F11` — Native visual workspace Desk handoff containment

**State:** `CODE-FROZEN / QA-PENDING`

Primary implementation commit:

- `0cf1418192f3d9a1f808fc606fb7f00e929c5033` — `fix: contain native visual workspace Desk handoffs`

Supporting contract/test commits:

- `be7dc70d` — F3F11 contract/documentation
- `95d744cc` — F3F11 contract tests

Exact-head governed evidence was green:

| Gate | Run | Result |
| --- | ---: | --- |
| EdgeSuite UI Candidate Compatibility | 34388948501 | PASS |
| CI | 34388948484 | PASS |
| RetailEdge Theme Compatibility | 34388948475 | PASS |
| Linters | 34388948549 | PASS |

## Deferred QA

Browser/persona QA is not claimed as complete.

Before F3F11/F3F12 may be represented as fully `FROZEN`, verify at minimum:

- authenticated Native Desk allowed and denied personas;
- ordinary EdgeSuite users cannot escape through guarded DocType/Report/create/record-row handoffs;
- Cash Shift native-detail columns do not open native forms for EdgeSuite-only users;
- permitted advanced/native-Desk users retain intended ERPNext lifecycle handoffs;
- EdgeSuite Page destinations remain usable after containment.

## Frozen Product Baseline

Unless explicitly changed by the Product Owner:

- EdgeSuite UI is the normal RetailEdge operational experience.
- ERPNext remains the accounting, stock, selling, purchasing, and operational backbone where appropriate.
- Restricted branch users with one permitted branch may auto-resolve that branch.
- Restricted branch users with multiple permitted branches must choose an explicit branch.
- Restricted branch users with zero permitted branches fail closed; restricted-zero must never become unrestricted.
- Active Branch Assignments are authoritative where assignment history exists; legacy behaviour is fallback only where assignment history does not exist.
- Security-sensitive branch and permission rules are enforced server-side; frontend filtering is not security.
- Stock Entry remains an ERPNext-native draft workflow unless the Product Owner explicitly changes that contract.
- Reporting must consume reconciled and hardened operational contracts.
- Business Hub is mandatory before MVP release.

## Mandatory Stop Boundary

Escalate before materially changing:

- MVP/product scope;
- major architecture;
- branch architecture;
- tenancy model;
- accounting or GL semantics;
- stock ledger, valuation, or posting semantics;
- authentication or security boundaries;
- destructive production data;
- irreversible migrations;
- two approved requirements that conflict.

Routine contract-preserving fixes, tests, documentation, regression correction, and security strengthening remain autonomously executable.

## Slice State Convention

- `ACTIVE` — implementation or investigation is in progress.
- `BLOCKED` — an external dependency or mandatory stop condition prevents progress.
- `CODE-FROZEN / QA-PENDING` — implementation and applicable automated gates are green, but required manual/browser/persona evidence remains outstanding.
- `FROZEN` — implementation, applicable automated gates, required QA evidence, documentation, and migration requirements are complete.

A later regression that violates a frozen or code-frozen contract reopens the affected contract and takes priority according to the Godmode priority rule.

## Successor Audit Findings

The repository-wide native-handoff audit has identified additional bounded gaps. They must be handled independently rather than bundled into a broad rewrite.

1. **Stock Position:** Item detail and reorder-due actions can still open native `Item` and unsaved `Material Request` forms without checking final EdgeSuite Native Desk capability. The backend already revalidates report scope, branch/warehouse scope, Material Request create permission, item validity, and reorder rules; the identified gap is interface exposure.
2. **Purchase Reporting:** final Native Desk capability is loaded, but invoice/supplier/return report-cell native handoffs are not consistently gated.
3. **Customer Receivables:** invoice/customer/payment-request/dunning detail links and draft collection handoffs can route directly to native forms without applying final Native Desk capability. This is more nuanced because collection actions prepare native drafts for review and must be handled without weakening accounting/document safeguards.
4. **Professional Purchasing and related purchasing overlays:** multiple native lifecycle handoffs exist. Some are intentionally governed advanced fallbacks, while others require a dedicated audit before any change. Do not treat this as one blanket frontend replacement.

## Previously Completed Hardening Context

The reconciled branch contains the preceding F3 payment/banking/navigation containment sequence through F3F12. Repository history remains authoritative for exact implementation details.

Notable areas include:

- guided customer/supplier payment ownership and fallback containment;
- permission-aware payment history and EdgeSuite revisit surface;
- EdgeSuite payments navigation ownership;
- Payment Reconciliation native fallback gating;
- Payment Order native fallback gating;
- Bank Transaction native fallback gating;
- recurring billing native route containment;
- native visual workspace Desk handoff containment;
- Cash Shift native-detail containment.

## Unresolved / Not Yet Claimed

- F3F11 and F3F12 browser/persona QA remain pending.
- Overall Readiness Hardening is not complete.
- Business Hub is not release-complete merely because implementation exists.
- Reporting remains downstream of unresolved foundational hardening.
- Fresh-install, upgrade, cross-workflow, release-hardening, rollback, and final MVP freeze gates remain later MVP requirements unless repository evidence explicitly freezes them.

## Prohibited Shortcuts

Do not obtain a green state by:

- disabling meaningful tests;
- weakening valid assertions to fit broken behaviour;
- suppressing real errors;
- converting restricted-zero branch scope into unrestricted access;
- relying on frontend-only security for protected business rules;
- mutating submitted accounting documents to simplify a workflow;
- introducing duplicate accounting, stock, or planning truth where ERPNext remains authoritative;
- bypassing the execution order with attractive non-blocking features.

## Exact Next Executable Step

Execute `RIR2F3F13 — Stock Position native-handoff containment` as the next bounded readiness-hardening slice.

Primary objective:

- preserve Stock Position read/report/reorder truth while preventing EdgeSuite-only users from escaping into native `Item` or unsaved `Material Request` forms.

Required implementation contract:

1. Read final `navigation.access.can_use_native_desk` into a fail-closed client capability.
2. Keep Stock Position data, stock status, reorder signals, branch/warehouse scope, and exports available according to their existing permissions.
3. Present `Item` detail and native Material Request replenishment actions as clickable only when Native Desk capability is true.
4. Independently guard native Item, Material Request, DocType, and Report handoffs even if a click/navigation event is triggered programmatically.
5. Preserve the existing server-side Material Request handoff revalidation and create-permission checks; do not move security to the frontend.
6. Do not change ERPNext stock, valuation, Stock Ledger, accounting, reorder calculations, Material Request semantics, or branch architecture.
7. Add a focused negative-path contract test and documentation.
8. Run the exact-head governed gates before marking the slice `CODE-FROZEN / QA-PENDING`.

After F3F13, continue the repository audit in risk order rather than automatically advancing to reporting.
