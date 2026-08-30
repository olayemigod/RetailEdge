# E16 Professional Purchasing — bounded implementation plan

This plan is a recovery-safe execution contract for the next genuinely incremental E16 capability. It prevents a large procurement rewrite from becoming one stalled implementation thread.

## Business goal

Give internal purchasing users a professional RetailEdge operating surface comparable to Professional Selling while ERPNext remains the authority for Purchase Orders, Purchase Receipts, Request for Quotation, Supplier Quotation, Purchase Invoices, stock and accounting.

The gap is user experience and orchestration, not missing ERPNext buying documents.

## Existing capability boundaries

Do not rebuild or fork these existing programme capabilities:

- Transaction Workspace already exposes native Purchase Invoice, Purchase Order and Purchase Receipt creation routes.
- Guided Purchase Invoice already exists and remains the simple invoice-entry path.
- Supplier Collaboration already owns supplier-facing RFQ / Supplier Quotation / Purchase Order / Purchase Invoice portal experience.
- Supplier Document Review already owns accepted supplier-document → draft Purchase Invoice handoff.
- Purchase Register / Supplier Payables already own purchase/payables reporting surfaces.
- Project Operations already owns project-linked purchasing/funds workflows.
- ERPNext remains authoritative for buying validation, supplier scorecards, taxes, rates, stock receipt, billing state and document status.

## Non-divergence rule

Continue only on PR #53 / `agent/competitive-gap-nextgen-20260829`.

Do not create another Professional Purchasing PR or branch while this E16 line is open. If a later chunk proves dependent on code not contained in the cumulative E16 line, stop that chunk and document the required reconciliation/stacking contract before coding.

## Chunk execution rule

Each implementation chunk must complete this cycle before the next chunk starts:

1. inspect exact live PR head and dependencies;
2. implement only the named chunk scope;
3. add focused backend/UI/safety tests;
4. compare against the previous green checkpoint and confirm no unrelated files were displaced;
5. require exact-head Theme, Linters, clean Frappe v16 CI/full tests and governed EdgeSuite UI candidate compatibility to pass;
6. record the green SHA and scope in the E16 audit/PR;
7. only then begin the next chunk.

A stalled thread must therefore leave a usable checkpoint and an explicit next chunk rather than an unbounded half-implementation.

## C1 — Purchase Order operations + PO → draft Purchase Receipt — IMPLEMENTED / GREEN

Validated implementation checkpoint: `7fc24e993f908cdc28b72dc841f2771a21b570d3`.

- RetailEdge Theme Compatibility #141: PASS
- Linters #1872, including pre-commit, Semgrep and vulnerable dependency audit: PASS
- CI #1890, including clean Frappe v16 site creation, exact app set, asset build, EdgeSuite asset contract and full RetailEdge tests: PASS
- EdgeSuite UI Candidate Compatibility #128, including clean build/migrate/shared runtime verification and full RetailEdge tests: PASS

### Delivered scope

- Added a standard EdgeSuite `professional-purchasing` page for internal Purchase/Accounts/System Manager users subject to native permissions.
- Added permission-aware Purchase Order operational context for Company and optional Branch/Supplier scope.
- Surfaces PO status, transaction date, supplier, grand total, percent received and percent billed from ERPNext.
- Tables support local sorting without changing the authoritative server dataset.
- Native Purchase Order and Purchase Receipt records remain directly accessible.
- New Purchase Order creation continues through the native ERPNext form; C1 does not create a second PO document editor.
- Submitted Purchase Orders with remaining receivable quantity expose an explicit `Prepare Receipt` action.
- The server re-reads and revalidates Purchase Order state, Purchase Receipt create permission and RetailEdge Branch access.
- Mapping delegates to ERPNext v16 `erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt`.
- The mapped Purchase Receipt is inserted as **draft only** as the current user.
- Purchase Receipt Branch attribution is copied from the authoritative Purchase Order when the field is available; Branch-scoped actions fail closed if migration fields are unavailable.
- Draft/cancelled/non-open, fully received, subcontracted, no-remaining-item and denied-Branch cases fail closed or fall back to the native ERPNext workflow.
- Frappe v16 link-search result shape is preserved for EdgeSuite Link fields.
- Professional Purchasing is promoted into the shared Buy navigation before native Purchase Orders only when the Page is readable; native Purchase Order and Purchase Receipt navigation remains intact.
- Feature flag: `professional_purchasing = erpnext_native_po_receipt`.

### Accounting and stock safety

- No Purchase Receipt auto-submit.
- No direct Stock Ledger Entry or GL Entry write.
- No direct Purchase Order receipt-percentage mutation.
- No Purchase Invoice creation in this chunk.
- No manual database commit.
- ERPNext owns mapped item links, remaining quantities, rates, taxes, warehouses, stock validation and accounting consequences at standard document submission.

### Explicitly out of scope for C1

- Material Request workflow orchestration.
- Request for Quotation creation or supplier invitation.
- Supplier Quotation comparison / bid analysis.
- Supplier selection automation.
- Purchase Invoice creation except the already-existing supplier-document handoff / guided PI paths.
- Automatic receipt submission.
- Three-way matching automation.
- Reorder automation.
- Approval-workflow replacement.
- New supplier portal behaviour.

## C2 — Material Request / RFQ / Supplier Quotation orchestration — NEXT AUDIT CHUNK

C2 is **not automatically approved for implementation merely because C1 is green**.

Before coding C2:

1. inspect the exact current PR #53 head and confirm no branch movement;
2. re-audit existing Material Request, Request for Quotation, Supplier Quotation, Supplier Collaboration and Project Operations capabilities;
3. inspect the exact ERPNext v16 Material Request → RFQ / RFQ / Supplier Quotation mapper and permission contracts;
4. identify the smallest genuinely incremental internal purchasing UX gap;
5. write the C2 implementation contract into this document before code;
6. implement only that bounded C2 scope and repeat the full checkpoint cycle.

Potential scope remains limited to native ERPNext mappings/searches and supplier-comparison UX. Do not build a second procurement ledger, supplier bid store or approval workflow.

## C3 — Purchase receipt / invoice readiness and exception visibility

Start only after C2 is either green or explicitly skipped as unnecessary.

Potential scope: actionable readiness/exception views over native PO → Receipt → Purchase Invoice state, without creating a duplicate three-way-match ledger. Re-audit before coding.

## Recovery checkpoint

Baseline before Professional Purchasing: `427bf451435de564654d87b1b917cbe9675cf2da`.

C1 implementation checkpoint: `7fc24e993f908cdc28b72dc841f2771a21b570d3`.

C1 first fully validated documentation checkpoint: `d8d81994ab5152bf690eed75ae810bb3de294dc1`.

C1 audit synchronization checkpoint: `8764896cc524d07fb4d93d3566710e83724e0765`.

The current PR head after this file is the **final frozen C1 closeout head**. No further repository file writes are permitted until that exact head passes Theme, Linters, clean Frappe v16 CI/full tests and governed EdgeSuite UI Candidate Compatibility.

If work stops now, resume by validating the current frozen closeout head and then at **C2 audit**, not C1 implementation. Do not rebuild C1 and do not begin C3.