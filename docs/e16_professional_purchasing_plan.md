# E16 Professional Purchasing — bounded implementation plan

This plan is the recovery-safe execution contract for incremental Professional Purchasing work on PR #53 / `agent/competitive-gap-nextgen-20260829`.

## Business and architecture boundary

RetailEdge improves procurement usability and operational control while ERPNext remains authoritative for Material Request, Request for Quotation, Supplier Quotation, Purchase Order, Purchase Receipt, Purchase Invoice, supplier rules, stock and accounting.

Do not rebuild native ERPNext documents, supplier bidding, buying reports, Projects, payables or ledgers. Existing Supplier Portal, Supplier Document Review, Purchase Register, Supplier Payables and Project Operations remain separate established capabilities.

## EdgeSuite UI policy — hard gate

All new operational frontend work must remain in the governed EdgeSuite UI experience:

- require `window.EdgeSuiteUI`;
- reuse the existing `professional-purchasing` Page and shared EdgeSuite shell/components;
- use EdgeSuite fields, buttons, loading/error/empty states and governed styling;
- no new `window.EdgeUI`, `frappe.ui.Dialog`, `frappe.prompt`, `frappe.msgprint`, `frappe.show_alert` or parallel operational frontend;
- native ERPNext forms and reports remain authoritative completion/fallback surfaces.

## Chunk discipline

For each chunk: audit first → write bounded contract → implement only that scope → focused tests → compare against previous green checkpoint → freeze exact head → require Theme, Linters, clean Frappe v16 CI/full tests and EdgeSuite candidate → record green SHA → only then continue.

## C1 — PO operations + PO → draft Purchase Receipt — GREEN

Final closeout: `67ecc8ae8b93d155b69c4b39ede1c7bc2c515b1c`.

- Theme #146: PASS
- Linters #1881 / #1882: PASS
- CI #1899 / #1900: PASS
- EdgeSuite Candidate #137 / #138: PASS

Delivered permission-aware PO operations in EdgeSuite and ERPNext-native PO → draft Purchase Receipt using `make_purchase_receipt`. No auto-submit, GL/SLE write, manual commit or shadow stock/accounting logic.

## C2A — Purchase Material Request → draft RFQ — GREEN

Validated checkpoint: `a920ce14b0e4687b256f080bf4e788d3f27efee1`.

- Theme #151: PASS
- Linters #1891 / #1892: PASS
- CI #1909: PASS
- EdgeSuite Candidate #148: PASS

Delivered inside the existing EdgeSuite Professional Purchasing page:

- permission/Company/Branch-aware submitted Purchase Material Request queue;
- native ERPNext `make_request_for_quotation` mapping;
- 1–20 unique permitted Suppliers selected through EdgeSuite Link fields;
- supplier rows appended with `send_email = 0`;
- draft RFQ insertion only;
- native ERPNext RFQ form retained for contacts, terms, communication and submission;
- direct native RFQ, Supplier Quotation and Supplier Quotation Comparison routes;
- no bid store, auto-email, auto-submit, automatic supplier selection or custom Supplier Quotation creation.

## C2B — RFQ / Supplier Quotation response workflow — SKIPPED AFTER AUDIT

Do not implement another response/bid workflow.

Audit confirmed:

- RetailEdge Supplier Portal already exposes ERPNext RFQ and Supplier Quotation transactions;
- ERPNext RFQ Supplier rows already maintain `quote_status` (`Pending` / `Received`), contact/email and email-sent state;
- submitted ERPNext RFQ already supports supplier email sending, native Supplier Quotation creation and RFQ-filtered Supplier Quotation Comparison;
- ERPNext Supplier Quotation remains authority for quotation → Purchase Order mapping.

A second RetailEdge RFQ-response store or quotation comparison engine would be divergent duplication.

## C3 audit result

Existing coverage is strong but split:

- RetailEdge Purchase Register / Supplier Payables cover submitted Purchase Invoice and payable reporting;
- ERPNext Purchase Order Analysis already owns item-level ordered, received, billed, pending quantities/amounts and Purchase Receipt linkage;
- Professional Purchasing already shows PO-level `% Received` and `% Billed` and can prepare draft receipts.

Therefore C3 must **not** build a three-way-match ledger or duplicate ERPNext Purchase Order Analysis.

The genuine operating gap is an action-oriented, permission-aware exception classification over authoritative PO header progress so buyers can quickly see which existing PO needs attention.

## C3A — Purchasing exceptions & readiness — SELECTED IMPLEMENTATION CHUNK

### Goal

Add a small read-only exception layer to the existing EdgeSuite Professional Purchasing workspace using current ERPNext Purchase Order fields only.

### Authoritative inputs

Use only permitted current Purchase Order rows already loaded by Professional Purchasing:

- `schedule_date` / required-by date;
- `status` / `docstatus`;
- `per_received`;
- `per_billed`;
- Company, Branch, Supplier and PO identity.

Do not create a new DocType, exception ledger or persisted matching state.

### Exception classifications

For submitted, open Purchase Orders only:

1. `Overdue Receipt` — required date is before today and `per_received < 100`.
2. `Received Not Fully Billed` — `per_received > per_billed` with a material difference greater than 0.01 percentage point.
3. `Billed Ahead of Receipt` — `per_billed > per_received` with a material difference greater than 0.01 percentage point. This is a **review state**, not an assertion of accounting error, because advance/vendor billing can be legitimate.
4. `Ready to Receive` — open PO with `per_received < 100` that is not overdue; this is readiness, not an exception.
5. `On Track / Complete` — no current exception/readiness classification requiring action.

A PO may carry more than one review flag where the native percentages justify it.

### Backend requirements

- Derive flags server-side from the same permission-aware PO dataset returned by `get_professional_purchasing_context`.
- Use server `nowdate()` / `getdate()` for overdue calculation; never browser clock as authority.
- Return per-row `attention_flags`, `attention_level` and summary counts.
- Do not query/write GL Entry, Stock Ledger Entry or create another receipt/invoice matching dataset.
- Do not mutate PO/Receipt/Invoice documents.
- Keep native Purchase Order Analysis available as the detailed quantity/amount report.

### EdgeSuite UI requirements

- Extend the existing `ProfessionalPurchasing.vue` only.
- Add summary cards/filters for overdue, received-not-billed and billed-ahead-of-receipt.
- Add an `Attention` column to the current sortable PO table using governed EdgeSuite-compatible badges/chips.
- Allow quick local filtering of the already server-scoped rows; filtering must not broaden the server dataset.
- Add an `Open PO Analysis` action to the native ERPNext `Purchase Order Analysis` report when permitted.
- No new page, modal, prompt, toast framework or parallel UI.

### Explicitly out of scope

- persisted three-way match records;
- tolerance/approval engine;
- automatic invoice blocking or approval;
- automatic supplier dispute workflow;
- valuation/accounting reconciliation;
- item-level replacement for ERPNext Purchase Order Analysis;
- Purchase Invoice creation or submission;
- Project funds changes.

### Tests required

- backend classification: overdue receipt;
- backend classification: received-not-fully-billed;
- backend classification: billed-ahead-of-receipt treated as review, not error mutation;
- backend: draft/cancelled/closed/completed rows do not produce active exception flags;
- backend: server date is used;
- UI contract: existing EdgeSuite page only, sortable Attention column and local filter;
- UI contract rejects `window.EdgeUI`, Frappe Dialog/Prompt/msgprint/show_alert;
- native Purchase Order Analysis route remains available;
- full regression and exact-head Theme/Linters/CI/EdgeSuite validation.

## Recovery checkpoints

- Pre-Professional Purchasing baseline: `427bf451435de564654d87b1b917cbe9675cf2da`
- C1 final green: `67ecc8ae8b93d155b69c4b39ede1c7bc2c515b1c`
- C2A final green: `a920ce14b0e4687b256f080bf4e788d3f27efee1`
- C2B: skipped after audit; no source SHA required.

Next implementation checkpoint is **C3A only**. If execution stops, resume from this contract and the latest C3A commit. Do not start another purchasing feature until C3A is exact-head green.
