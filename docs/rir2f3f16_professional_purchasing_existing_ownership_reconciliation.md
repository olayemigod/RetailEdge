# RIR2F3F16 — Professional Purchasing Existing-Ownership Reconciliation

## Goal

Reconcile the older `ProfessionalPurchasing.vue` action methods with the EdgeSuite-owned purchasing workflows that already exist on the reconciled branch, so normal purchasing behavior no longer depends on DOM capture handlers to prevent stale native ERPNext handoffs.

This slice does **not** invent new purchasing workflows. It makes the primary Vue component delegate directly to already-implemented EdgeSuite overlays and treats remaining native routes as explicit advanced fallbacks.

## Ownership Audit

| User action | Current primary ownership | Classification | F3F16 action |
| --- | --- | --- | --- |
| New Purchase Order | `ProfessionalPurchaseOrderOverlay` / guided dialog | `EDGESUITE_OWNED` | Route Vue action directly to existing overlay event |
| Start RFQ / standard RFQ submit | `ProfessionalRfqPreviewOverlay` + `professional_sourcing` standard submit | `EDGESUITE_OWNED` | Route Vue action directly to preview event; stop stale direct draft POST |
| RFQ History | `ProfessionalRfqHistoryOverlay` | `EDGESUITE_OWNED` | Route directly to history event |
| Supplier Quotation History | `ProfessionalSupplierQuotationHistoryOverlay` | `EDGESUITE_OWNED` | Route directly to history event |
| Supplier Quotation → PO draft | `ProfessionalSupplierQuotationPurchaseOrderOverlay` | `EDGESUITE_OWNED` | No change required |
| Purchase Order review/submit | `ProfessionalPurchaseOrderSubmitOverlay` | `EDGESUITE_OWNED` | No change required |
| Purchase Receipt preview/standard posting | `ProfessionalPurchaseReceiptPreviewOverlay` + standard ERPNext submit backend | `EDGESUITE_OWNED` | Route Vue Prepare Receipt directly to preview event; stop stale direct draft POST |
| Purchase Receipt History | `ProfessionalPurchaseReceiptHistoryOverlay` | `EDGESUITE_OWNED` | Route directly to history event |
| Material Request native detail/list | ERPNext native Desk | `ADVANCED_NATIVE_FALLBACK` | Guard directly with final Native Desk capability |
| Purchase Order native detail | ERPNext native Desk | `ADVANCED_NATIVE_FALLBACK` | Guard directly with final Native Desk capability |
| Supplier Quotation Comparison | ERPNext native report | `ADVANCED_NATIVE_FALLBACK` | Guard directly with final Native Desk capability |
| Purchase Order Analysis | ERPNext native report | `ADVANCED_NATIVE_FALLBACK` | Guard directly with final Native Desk capability |
| Procurement Tracker native report | ERPNext native report | `ADVANCED_NATIVE_FALLBACK` | Guard directly with final Native Desk capability |
| Landed Cost Voucher handoff | native unsaved voucher; panel hidden in EdgeSuite-only mode | `ADVANCED_NATIVE_FALLBACK` | Out of scope; preserve existing hidden/advanced policy |
| Purchase Return / Supplier Debit Note | native draft creation then native review | `OWNERSHIP_GAP` | Out of scope; do not remove only completion path |
| Incoming Quality Inspection | native draft creation then native review | `OWNERSHIP_GAP` | Out of scope; do not remove only completion path |

## Why This Slice Is Safe

The page controller and bundle already intercept ordinary user clicks for Purchase Order, RFQ, Supplier Quotation, Purchase Receipt, and related history/review flows. F3F16 moves that ownership contract into the Vue source itself so:

- the component remains correct if DOM interception order changes;
- programmatic calls do not accidentally invoke stale native draft creation;
- EdgeSuite ownership is explicit and testable at the primary component layer;
- existing controller interception can remain as compatibility/defence in depth.

## Scope

- `retailedge/public/js/professional_purchasing/ProfessionalPurchasing.vue`
- focused F3F16 contract tests
- reconcile the older `test_professional_purchasing_ui_contract.py` expectations that still require superseded direct native behavior
- this document

## Implementation Requirements

1. Add fail-closed `canUseNativeDesk: false` and populate it from final `navigation.access.can_use_native_desk`.
2. Define/reuse the existing EdgeSuite purchasing event names in the component.
3. `New Purchase Order` must dispatch the existing Professional Purchase Order overlay event instead of `frappe.new_doc("Purchase Order")`.
4. `Start RFQ` / legacy `prepareRfq()` must delegate to the existing RFQ preview overlay and must not POST `professional_purchasing.prepare_request_for_quotation_draft`.
5. RFQ list/history and Supplier Quotation list/history actions must dispatch their existing EdgeSuite history events.
6. `Prepare Receipt` must dispatch the existing Purchase Receipt preview event and must not POST `professional_purchasing.prepare_purchase_receipt_draft`.
7. Purchase Receipt list/history must dispatch the existing EdgeSuite receipt-history event.
8. Material Request native detail/list, Purchase Order native detail, native comparison/analysis/tracker reports, and DocType/Report menu routes must fail closed when Native Desk capability is unavailable.
9. Keep existing page-controller/bundle interception as defence in depth; do not remove it in this slice.
10. Preserve Purchase Return/Debit Note, Incoming Quality Inspection, and Landed Cost behavior for now. They are separately classified and must not be silently disabled.

## Out of Scope

- building the missing EdgeSuite Purchase Return/Debit Note completion flow;
- building the missing EdgeSuite Incoming Quality Inspection completion flow;
- redesigning Landed Cost Voucher;
- changing ERPNext purchase accounting, stock posting, valuation, GL, branch rules, native permissions, or document lifecycle;
- changing standard RFQ/PO/receipt submit backends already governed by RIR2F2;
- schema, migration, patch, or data changes.

## Safety Rules

- Existing standard EdgeSuite submit/post flows continue to invoke authoritative ERPNext document methods server-side.
- Advanced native fallbacks remain available only to users with final Native Desk capability.
- Do not replace an unresolved ownership gap with a hidden button if that removes the only viable business completion path.
- Do not weaken page-controller restricted-mode guards or backend permissions.

## Tests Required

Focused tests must verify:

- final Native Desk capability is fail closed and read from navigation context;
- all already-owned standard actions dispatch EdgeSuite events and no longer issue stale native draft POSTs/routes;
- advanced native methods and menu DocType/Report routes fail closed without Native Desk capability;
- stale legacy UI tests no longer require direct native `new_doc`/draft routes in the component;
- existing RIR2F2 ownership components/controllers remain present;
- no accounting/stock backend or migration file changes are required.

## Freeze Rule

Mark F3F16 `CODE-FROZEN / QA-PENDING` only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI, and governed EdgeSuite UI Candidate Compatibility pass on the exact implementation head. Browser/persona QA remains required for full freeze.
