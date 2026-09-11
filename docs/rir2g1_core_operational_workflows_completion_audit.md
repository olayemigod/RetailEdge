# RIR2G1 — Core Operational Workflows Completion Audit

## Goal

Prove that RetailEdge's MVP operational journeys can progress safely from initiation to a valid ERPNext-owned completion state, while preserving the approved EdgeSuite/Advanced ERPNext split.

RIR2G1 is an audit-led phase. It must not rebuild already-correct workflows merely to make every ERPNext surface look native to RetailEdge.

## Starting Point

Phase 1 Readiness Hardening is code-complete through RIR2F3F42. The authoritative branch is:

- `qa/retailedge-reconciled-20260902`
- Phase-1 frozen code head: `5a5c0b234993fde8c31baa8ce32a0191588edb48`

## Audit Classification

Each core journey is classified as one of:

- `COMPLETE_STANDARD_MVP`
- `COMPLETE_WITH_ADVANCED_FALLBACK`
- `WORKFLOW_GAP`
- `DEFERRED_NON_MVP`
- `AUDIT_IN_PROGRESS`

## Preliminary Journey Matrix

| Journey | Current classification | Current owner / authority | Audit note |
| --- | --- | --- | --- |
| Quote → Sales Order → Delivery → Sales Invoice | AUDIT_IN_PROGRESS | Professional Selling + ERPNext | EdgeSuite ownership exists; completion/workflow precedence still being traced end-to-end |
| Customer receipt / advance / application | COMPLETE_STANDARD_MVP | Payment Management + ERPNext Payment Entry/Reconciliation | Standard submit and application paths already hardened |
| Purchase Order → Receipt → Purchase Invoice | COMPLETE_STANDARD_MVP | Professional Purchasing + ERPNext | Standard submit/workflow precedence hardened through F3F36–F3F38 |
| Supplier payment | COMPLETE_STANDARD_MVP | Supplier Payables / Payment Management + ERPNext Payment Entry | Standard supplier-payment submit hardened |
| Purchase Return / Supplier Debit Note | COMPLETE_STANDARD_MVP | Professional Purchasing + ERPNext return documents | Standard return workflow precedence hardened through F3F39 |
| Stock Transfer | COMPLETE_WITH_ADVANCED_FALLBACK | Guided Stock Transfer + ERPNext Stock Entry | Standard guided path remains draft-only by frozen product baseline; serial/batch and final advanced stock handling remain native |
| Stock Count / Adjustment | WORKFLOW_GAP | Guided Stock Adjustment + ERPNext Stock Reconciliation | **Checkpoint A blocker:** still uses legacy Branch restriction semantics and can fail open for restricted-zero users |
| Cashier close / deposit / transfer | AUDIT_IN_PROGRESS | Cash Shift / Cash Movement + ERPNext | Existing EdgeSuite flows require end-to-end completion verification |
| Cashier Expense | COMPLETE_STANDARD_MVP | Expense Register/Review + ERPNext-backed expense truth | Ownership and posted-truth hardening completed |
| Business Expense | COMPLETE_STANDARD_MVP | Business Expenses + ERPNext accounting posting | Posting, reversal, workflow and consolidated register completed |
| Bank matching → reconciliation handoff | COMPLETE_WITH_ADVANCED_FALLBACK | Bank Matching + ERPNext reconciliation | Matching is EdgeSuite-owned; final advanced reconciliation remains deliberate native fallback |
| Customer receivables follow-up | COMPLETE_WITH_ADVANCED_FALLBACK | Customer Receivables + ERPNext receivable truth | Standard collection actions exist; specialist native review remains capability-gated |
| Supplier payables follow-up | AUDIT_IN_PROGRESS | Supplier Payables + ERPNext payable truth | Payment handoff exists; remaining follow-up completion still being traced |

## Checkpoint A — Guided Stock Adjustment Branch Scope

### Confirmed defect

`retailedge/guided_stock_adjustment.py` still uses the legacy Branch convention:

- `get_user_allowed_branches()`;
- `user_has_global_branch_access()`;
- `validate_user_branch_access()`.

That convention treats an empty allowed-Branch list ambiguously. In the current implementation:

1. restricted-zero Branch search can return only the Company filter, which exposes all Company Branches;
2. blank-Branch Warehouse search can return Company-wide Warehouses;
3. draft creation accepts blank Branch and only validates Warehouse Company/read permission;
4. therefore a restricted-zero or ambiguous restricted user can reach a Stock Reconciliation draft outside the authoritative operational Branch scope.

This conflicts with the already-frozen B3/RIR2F contracts where restricted-zero must never become unrestricted.

### Required correction

Migrate Guided Stock Adjustment only to the shared operational Branch-scope contract:

- `get_operational_branch_scope()`;
- `resolve_operational_branch()`.

Required behavior:

- unrestricted user + blank Branch retains Company-wide behavior;
- restricted user + exactly one permitted Branch may auto-resolve;
- restricted user + multiple permitted Branches must choose explicitly;
- restricted user + zero permitted Branches fails closed;
- Branch search exposes only allowed operational Branches;
- Warehouse search cannot broaden beyond the resolved/allowed Branch scope;
- draft creation re-resolves Branch server-side before Warehouse validation and insert;
- Warehouse must still be readable and belong to the selected Company;
- Branch/Warehouse relationship remains validated through existing Warehouse field / Branch Profile logic;
- Stock Reconciliation remains a normal ERPNext draft;
- no automatic submit, valuation rewrite, GL/SLE mutation, `ignore_permissions`, or manual commit.

## Out of Scope for Checkpoint A

- changing Stock Reconciliation submission ownership;
- adding valuation/cost fields to guided Stock Adjustment;
- serial/batch completion;
- changing Stock Transfer behavior;
- changing Branch architecture;
- reporting;
- Business Hub redesign;
- manual browser/persona QA.

## Tests Required for Checkpoint A

1. restricted-zero Branch search returns no permitted Branch;
2. restricted-zero Warehouse search cannot return Company-wide Warehouses;
3. restricted multi-Branch Warehouse search requires Branch selection;
4. restricted single-Branch blank input auto-resolves that Branch;
5. draft creation always passes through `resolve_operational_branch()`;
6. an explicit Branch outside allowed scope fails before Warehouse validation;
7. unrestricted blank Branch preserves Company-wide behavior;
8. legacy `get_user_allowed_branches`, `user_has_global_branch_access` and direct `validate_user_branch_access` are removed from Guided Stock Adjustment;
9. Stock Reconciliation remains draft-only and ERPNext-owned;
10. existing Company/Warehouse/read-permission, quantity, serial/batch and valuation-hiding contracts remain green.

## Checkpoint Freeze Rule

Checkpoint A may freeze only when the same four governed exact-head gates pass:

1. RetailEdge Theme Compatibility;
2. Linters / Semgrep / vulnerable dependency audit;
3. clean Frappe v16 CI;
4. governed EdgeSuite UI Candidate Compatibility.

RIR2G1 itself remains active after Checkpoint A until the remaining `AUDIT_IN_PROGRESS` journeys are classified and any genuine blockers are resolved.
