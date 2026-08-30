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

## C1 — Purchase Order operations + PO → draft Purchase Receipt

### Scope

- Add a standard EdgeSuite `professional-purchasing` page for internal Purchase/Accounts/System Manager users subject to native permissions.
- Show permission-aware Purchase Order operational context for the selected Company and optional Branch/Supplier.
- Surface PO status, transaction date, supplier, grand total, percent received and percent billed from ERPNext.
- Allow opening the native Purchase Order and Purchase Receipt records.
- Allow creation of a new native Purchase Order through the existing ERPNext form; do not build a second PO document editor in C1.
- For a submitted PO with remaining receivable quantity, provide an explicit `Prepare Purchase Receipt` action.
- The server must re-read and revalidate the Purchase Order, permissions, Company and Branch.
- Delegate mapping to ERPNext v16 `erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt`.
- Insert the resulting Purchase Receipt as **draft only** as the current user.
- Never submit the Purchase Receipt automatically.
- Never write Stock Ledger Entry, GL Entry, Purchase Order receipt percentages or Purchase Invoice directly.
- Keep ERPNext item links, remaining quantities, rates, taxes and source references authoritative.
- If the mapper produces no receivable items, fail closed and direct the user to the native PO/receipt workflow.
- Complex subcontracting or unsupported cases may fall back to the full native ERPNext workflow rather than adding custom accounting/stock logic.

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

### C1 tests required

- backend: submitted PO + create/read permissions delegates to native `make_purchase_receipt` and inserts draft only;
- backend: draft/cancelled PO rejected;
- backend: no remaining receivable items rejected;
- backend: Company/Branch mismatch or denied branch access rejected;
- backend: user without Purchase Receipt create permission rejected;
- contract: standard EdgeSuite page and bundle/component mount contract;
- contract: no `frappe.ui.Dialog`, direct GL/SLE write, submit or manual commit in the C1 workflow;
- navigation: page promoted only where the current user has appropriate buying access, without removing native Purchase Order / Purchase Receipt fallbacks;
- full RetailEdge regression suite and clean-install/migration/build validation.

## C2 — Material Request / RFQ / Supplier Quotation orchestration

Start only after C1 is fully green and checkpointed.

Potential scope is limited to native ERPNext mappings/searches and supplier-comparison UX. Exact ERPNext v16 mapper contracts must be inspected again immediately before implementation. Do not assume C2 is required merely because it is listed here; re-run the competitive-gap audit first.

## C3 — Purchase receipt / invoice readiness and exception visibility

Start only after C2 is either green or explicitly skipped as unnecessary.

Potential scope: actionable readiness/exception views over native PO → Receipt → Purchase Invoice state, without creating a duplicate three-way-match ledger. Re-audit before coding.

## Recovery checkpoint

Baseline before Professional Purchasing: `427bf451435de564654d87b1b917cbe9675cf2da`.

The next implementation checkpoint to create is **C1 only**. If work stops before C1 is green, resume from this document and the latest C1 commit; do not begin C2.