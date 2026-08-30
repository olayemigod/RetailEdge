# E16 Professional Purchasing — bounded implementation plan

This plan is a recovery-safe execution contract for genuinely incremental E16 purchasing capabilities. It prevents a large procurement rewrite from becoming one stalled implementation thread.

## Business goal

Give internal purchasing users a professional RetailEdge operating surface comparable to Professional Selling while ERPNext remains the authority for Material Requests, Request for Quotation, Supplier Quotation, Purchase Orders, Purchase Receipts, Purchase Invoices, stock and accounting.

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
- ERPNext v16 already owns Supplier Quotation Comparison. RetailEdge must expose/orchestrate that report where useful rather than create a parallel bid-comparison engine.

## EdgeSuite UI policy — hard gate

All new RetailEdge operational frontend work must use the governed EdgeSuite UI runtime and composition model.

- require `window.EdgeSuiteUI`;
- mount with the shared EdgeSuite app/runtime contract;
- reuse the existing EdgeSuite `professional-purchasing` page rather than create a parallel procurement frontend;
- use shared EdgeSuite shells, page components, fields, buttons, loading/error/empty states and governed styling;
- do not introduce `window.EdgeUI`, `frappe.ui.Dialog`, `frappe.prompt` or a second operational UI framework for new C2 work;
- native ERPNext forms/reports remain permitted fallbacks and authoritative completion surfaces.

## Non-divergence rule

Continue only on PR #53 / `agent/competitive-gap-nextgen-20260829`.

Do not create another Professional Purchasing PR or branch while this E16 line is open. If a later chunk proves dependent on code not contained in the cumulative E16 line, stop that chunk and document the required reconciliation/stacking contract before coding.

## Chunk execution rule

Each implementation chunk must complete this cycle before the next chunk starts:

1. inspect exact live PR head and dependencies;
2. audit existing RetailEdge and ERPNext capability before selecting scope;
3. write the bounded implementation contract before code;
4. implement only the named chunk scope;
5. add focused backend/UI/safety tests;
6. compare against the previous green checkpoint and confirm no unrelated files were displaced;
7. require exact-head Theme, Linters, clean Frappe v16 CI/full tests and governed EdgeSuite UI candidate compatibility to pass;
8. record the green SHA and scope in the E16 audit/PR;
9. only then begin the next chunk.

A stalled thread must therefore leave a usable checkpoint and an explicit next chunk rather than an unbounded half-implementation.

## C1 — Purchase Order operations + PO → draft Purchase Receipt — IMPLEMENTED / GREEN

Validated implementation checkpoint: `7fc24e993f908cdc28b72dc841f2771a21b570d3`.

- RetailEdge Theme Compatibility #141: PASS
- Linters #1872, including pre-commit, Semgrep and vulnerable dependency audit: PASS
- CI #1890, including clean Frappe v16 site creation, exact app set, asset build, EdgeSuite asset contract and full RetailEdge tests: PASS
- EdgeSuite UI Candidate Compatibility #128, including clean build/migrate/shared runtime verification and full RetailEdge tests: PASS

Final C1 closeout checkpoint: `67ecc8ae8b93d155b69c4b39ede1c7bc2c515b1c`.

- RetailEdge Theme Compatibility #146: PASS
- Linters #1881 and #1882: PASS
- CI #1899 and #1900: PASS
- EdgeSuite UI Candidate Compatibility #137 and #138: PASS

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

## C2 audit result

The C2 audit confirmed that ERPNext v16 already supplies the authoritative procurement chain:

- submitted Purchase Material Request → Request for Quotation through `erpnext.stock.doctype.material_request.material_request.make_request_for_quotation`;
- RFQ supplier validation, including duplicate suppliers, disabled/frozen party validation and Supplier Scorecard RFQ warning/block rules;
- RFQ → Supplier Quotation through ERPNext's native mapper/portal flow;
- submitted Supplier Quotation → Purchase Order through ERPNext `make_purchase_order`;
- Supplier Quotation Comparison report with Company/date/RFQ/Supplier filters, validity, lead time, currencies and minimum-price highlighting.

Therefore RetailEdge must not build a second supplier-bid store, comparison engine or sourcing ledger.

## C2A — Purchase Material Request → draft RFQ — SELECTED IMPLEMENTATION CHUNK

### Goal

Extend the existing EdgeSuite Professional Purchasing workspace backwards from Purchase Order receiving into controlled sourcing preparation, while ERPNext remains the complete source of truth.

### Scope

- Extend the existing `professional-purchasing` EdgeSuite page; do not create another operational page.
- Show submitted ERPNext Material Requests where `material_request_type = Purchase` and there is still quantity available for procurement.
- Apply the same Company/Branch permission scope used by Professional Purchasing. Supplier filtering of the PO queue must not incorrectly hide Material Requests.
- Show Material Request identity, date/required date, status, Branch and percent ordered from ERPNext.
- Allow opening the native Material Request.
- Provide an explicit `Start RFQ` action only when the user can read the Material Request and create Request for Quotation.
- The buyer must select at least one Supplier before preparing the draft RFQ because ERPNext requires the RFQ Suppliers table.
- Allow a bounded supplier selection list, maximum 20 suppliers, with duplicate prevention.
- The browser supplies only Material Request identity and selected Supplier names. Company, Branch, items and quantities are derived from the authoritative Material Request/mapped document on the server.
- Re-read and revalidate the Material Request, Supplier permissions, Company, Branch, document state and procurement eligibility on the server.
- Delegate item mapping to ERPNext v16 `make_request_for_quotation`.
- Preserve ERPNext Material Request and Material Request Item references and remaining-quantity logic.
- Append the selected suppliers to the ERPNext RFQ draft with `send_email = 0`; C2A must never send email automatically.
- Let ERPNext RFQ validation enforce duplicate supplier, disabled/frozen Supplier and Supplier Scorecard warning/block rules.
- Insert only the **draft Request for Quotation** as the current user.
- Route the user to the native ERPNext RFQ form after draft preparation so supplier contacts, email settings, terms and final submission/sending remain standard ERPNext work.
- Keep direct links to native Request for Quotation and Supplier Quotation records.
- Expose the native `Supplier Quotation Comparison` report from Professional Purchasing when permitted; do not reproduce the report data model in RetailEdge.

### EdgeSuite UI requirements

- Keep `window.EdgeSuiteUI` as the only runtime.
- Reuse `EdgeAppShell`, `EdgePageLayout`, `EdgePageHeader`, `EdgeLinkField`, EdgeSuite loading/error/empty components and shared button/field styling already used by Professional Purchasing.
- Material Request sourcing must be a section of the existing EdgeSuite page.
- Supplier selection must use EdgeSuite Link-field search plus an inline selected-supplier list; do not use Frappe Dialog/Prompt.
- All new tables remain sortable using the shared RetailEdge table behaviour/contract.

### Explicitly out of scope for C2A

- automatic RFQ submission;
- automatic supplier email/portal invitation;
- Supplier Quotation creation by RetailEdge;
- Supplier Quotation comparison calculations or storage;
- automatic supplier selection;
- automatic Supplier Quotation → Purchase Order conversion;
- Material Request creation/reorder automation;
- approval-workflow replacement;
- procurement budgets beyond ERPNext's existing Material Request/Purchase controls;
- supplier portal changes;
- project-funds duplication.

### Tests required

- backend: submitted Purchase Material Request + permitted supplier(s) delegates to ERPNext `make_request_for_quotation`;
- backend: mapped RFQ retains Material Request references and is inserted as draft only;
- backend: selected suppliers are bounded, unique and appended with email sending disabled;
- backend: draft/cancelled/stopped/non-Purchase/fully ordered Material Request rejected;
- backend: missing suppliers rejected;
- backend: denied Material Request/RFQ permissions or Branch access rejected;
- backend: ERPNext Supplier validation remains active rather than being bypassed;
- frontend contract: new sourcing UI remains inside `ProfessionalPurchasing.vue` and uses only `window.EdgeSuiteUI`/shared components;
- frontend contract: no `frappe.ui.Dialog`, `frappe.prompt` or legacy `window.EdgeUI` introduced;
- navigation/fallback: native Material Request, RFQ, Supplier Quotation and Supplier Quotation Comparison routes remain available;
- full RetailEdge regression suite and clean install/migration/build/EdgeSuite candidate validation.

## C2B — RFQ / Supplier Quotation operational follow-through — AUDIT AFTER C2A GREEN

C2B is not approved yet. After C2A is green, re-audit whether the native RFQ lists, supplier portal and Supplier Quotation Comparison report already provide sufficient follow-through. If a real internal usability gap remains, define one bounded orchestration slice rather than implementing a second bid-comparison workflow.

## C3 — Purchase receipt / invoice readiness and exception visibility

Start only after C2A/C2B are green or explicitly skipped as unnecessary.

Potential scope: actionable readiness/exception views over native PO → Receipt → Purchase Invoice state, without creating a duplicate three-way-match ledger. Re-audit before coding.

## Recovery checkpoints

Baseline before Professional Purchasing: `427bf451435de564654d87b1b917cbe9675cf2da`.

C1 implementation checkpoint: `7fc24e993f908cdc28b72dc841f2771a21b570d3`.

C1 final fully green closeout checkpoint: `67ecc8ae8b93d155b69c4b39ede1c7bc2c515b1c`.

The next implementation checkpoint is **C2A only**. If work stops during C2A, resume from this contract and the latest C2A commit; do not rebuild C1 and do not begin C2B/C3 until C2A is exact-head green.
