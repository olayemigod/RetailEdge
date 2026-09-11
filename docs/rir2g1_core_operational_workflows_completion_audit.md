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

| Journey | Final classification | Current owner / authority | Closure evidence |
| --- | --- | --- | --- |
| Quote → Sales Order → Delivery → Sales Invoice | COMPLETE_STANDARD_MVP | Professional Selling + ERPNext | RIR2G1B–G1D now own standard completion, Workflow precedence and native ERPNext submit boundaries end-to-end |
| Customer receipt / advance / application | COMPLETE_STANDARD_MVP | Payment Management + Simple Payment + ERPNext Payment Entry/Reconciliation | Standard receipt review/submit/Workflow and advance application already hardened; complex reconciliation remains ERPNext authority |
| Purchase Order → Receipt → Purchase Invoice | COMPLETE_STANDARD_MVP | Professional Purchasing + ERPNext | Standard submit/Workflow precedence hardened through F3F36–F3F38 |
| Supplier payment | COMPLETE_STANDARD_MVP | Supplier Payables / Simple Payment + ERPNext Payment Entry | Pay Supplier reuses governed SimplePaymentDialog and standard supplier-payment completion owner |
| Purchase Return / Supplier Debit Note | COMPLETE_STANDARD_MVP | Professional Purchasing + ERPNext return documents | Standard return/debit-note Workflow precedence hardened through F3F39 |
| Stock Transfer | COMPLETE_WITH_ADVANCED_FALLBACK | Guided Stock Transfer + ERPNext Stock Entry | Standard guided creation is intentionally draft-only by frozen product baseline; final advanced/serial-batch stock handling remains ERPNext |
| Stock Count / Adjustment | COMPLETE_WITH_ADVANCED_FALLBACK | Guided Stock Adjustment + ERPNext Stock Reconciliation | RIR2G1A/A2 removed restricted-zero/Branch-scope defects; final Stock Reconciliation posting remains deliberate ERPNext advanced authority |
| POS shift close / cash verification | COMPLETE_WITH_ADVANCED_FALLBACK | POS Opening/Closing Shift + RetailEdge Cash Shift Verification | POS shift lifecycle remains POS/ERPNext-authoritative; RetailEdge owns branch-safe audit/verification and does not duplicate POS posting |
| Cash Deposit / Cash-Bank Transfer | COMPLETE_STANDARD_MVP | Business Hub + ERPNext Payment Entry | RIR2G1E closes standard Internal Transfer completion while preserving Cash Deposit before-submit custody enforcement |
| Cashier Expense | COMPLETE_STANDARD_MVP | Expense Register/Review + ERPNext-backed expense truth | Ownership and posted-truth hardening completed |
| Business Expense | COMPLETE_STANDARD_MVP | Business Expenses + ERPNext accounting posting | Posting, reversal, Workflow and consolidated register completed |
| Bank matching → reconciliation handoff | COMPLETE_WITH_ADVANCED_FALLBACK | Bank Matching + ERPNext reconciliation | Matching is EdgeSuite-owned; final advanced reconciliation remains deliberate native fallback |
| Customer receivables follow-up | COMPLETE_WITH_ADVANCED_FALLBACK | Customer Receivables + Simple Payment + ERPNext receivable truth | Direct receipt collection is EdgeSuite-owned; Payment Request/Dunning specialist review remains Native-Desk-capability-gated |
| Supplier payables follow-up | COMPLETE_STANDARD_MVP | Supplier Payables + Simple Payment + ERPNext payable truth | Pay Supplier row action prefills the governed EdgeSuite supplier-payment flow and completes through standard submit/Workflow ownership |

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

## Final RIR2G1 Reconciliation — Phase 2 Closure

RIR2G1 is now **CODE-COMPLETE / CONSOLIDATED QA-PENDING**.

The final audit found no remaining code-level ordinary-user blocker inside the approved MVP Core Operational Workflows contract.

### Runtime checkpoints completed inside RIR2G1

- **RIR2G1A / A2** — operational Branch cascade and restricted-zero hardening across guided stock adjustment, guided payments, cash transfer/custody, payment completion and mapped selling flows.
- **RIR2G1B** — standard Customer Quotation and Sales Order completion with Frappe Workflow precedence.
- **RIR2G1C** — standard Delivery Note completion with ERPNext stock/valuation authority preserved.
- **RIR2G1D** — standard Sales Invoice completion across Professional Selling and Business Hub with accounting-only versus update-stock safety.
- **RIR2G1E** — standard Cash Deposit and Cash/Bank Internal Transfer completion with existing cashier-custody before-submit enforcement preserved.

### Existing ownership reconciled rather than rebuilt

The audit also confirmed that these standard paths were already complete and did not require another implementation slice:

- customer receipt and customer advance Payment Entry review/submit/Workflow;
- supplier payment from Business Hub and Supplier Payables;
- customer advance application / mixed settlement;
- purchase submit, receipt, invoice, return and debit-note paths;
- Cashier Expense and Business Expense posting workflows;
- Bank Matching standard ownership;
- Customer Receivables and Supplier Payables actionable worklists.

### Deliberate Advanced ERPNext / subsystem boundaries

The following do **not** block Phase 2 because the frozen product contract deliberately retains their final specialist lifecycle outside ordinary EdgeSuite standard ownership:

- complex Stock Entry / serial-batch Stock Transfer completion;
- Stock Reconciliation final posting beyond the guided draft path;
- Payment Reconciliation and advanced treasury/allocation cases;
- multi-currency, deductions/write-offs and other advanced Payment Entry cases;
- Payment Request and Dunning specialist native review;
- POS Opening/Closing Shift lifecycle itself;
- advanced return, amendment, cancellation and exceptional accounting/stock cases already identified by individual contracts.

These boundaries remain permission- and Native-Desk-capability-controlled. They must not be silently converted into standard EdgeSuite operations without a new Product Owner contract.

### Phase 2 safety conclusion

Across the completed standard paths:

- ERPNext remains authoritative for GL, Payment Ledger, Stock Ledger, valuation, receivables, payables, outstanding balances, stock and submitted document lifecycle;
- active Frappe Workflow has precedence wherever a standard completion owner exists;
- restricted-zero Branch access fails closed;
- Company/Branch context is revalidated server-side;
- submitted accounting/stock documents are not mutated outside normal ERPNext lifecycle;
- no Phase-2 checkpoint introduced `ignore_permissions`, manual database commit or a parallel accounting/stock ledger.

### Governed closure evidence

The latest runtime checkpoint, RIR2G1E, is frozen at:

`04d50f3805d132fb8abaef0dfd1a35a2f33d04dd`

with all four exact-head gates passing:

- Theme Compatibility #746 — PASS;
- Linters / Semgrep / dependency audit #2587 — PASS;
- clean Frappe v16 CI #2605 — PASS;
- EdgeSuite UI Candidate Compatibility #843 — PASS.

Earlier RIR2G1A2, G1B, G1C and G1D exact-head freeze evidence remains recorded in the Godmode state ledger and PR #55 comments.

### Deferred acceptance

Phase 2 is not release-frozen. Browser/persona and cross-workflow acceptance remain part of consolidated RIR2E before final MVP freeze.

The next execution phase is **Phase 3 — EdgeSuite UI Completion**, beginning with an audit/reconciliation of remaining ordinary-user Native Desk dependencies and incomplete EdgeSuite operational surfaces. Do not rebuild surfaces already proven complete by F3 and G1 checkpoints.
