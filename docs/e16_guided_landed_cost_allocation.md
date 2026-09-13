# E16 C18 — Guided Landed Cost Allocation

## Goal

Make freight, clearing, customs duty, insurance and other acquisition costs discoverable from RetailEdge purchasing operations while ERPNext v16 Landed Cost Voucher remains the sole authority for inventory valuation and accounting effects.

C18 is a native-form handoff. RetailEdge must not calculate or post inventory revaluation itself.

## Why this gap matters

Purchase price alone is often not the true cost of stock. For Nigerian and African retailers importing goods or moving stock through freight/clearing channels, unallocated landed costs can materially overstate gross margin and understate inventory valuation.

RetailEdge currently exposes procurement, receipts, purchasing analysis and supplier corrections but has no guided landed-cost workflow. ERPNext already provides the correct accounting/stock mechanism through `Landed Cost Voucher`; RetailEdge should make that mechanism easier to start without duplicating it.

## ERPNext v16 source of truth

Use native `Landed Cost Voucher` only.

ERPNext remains authoritative for:

- eligible receipt document types;
- submitted-source validation;
- Company consistency;
- Purchase Invoice `update_stock` eligibility;
- receipt items and cost centres;
- landed-cost tax/charge rows and expense-account validation;
- distribution by `Qty`, `Amount`, or `Distribute Manually`;
- applicable charges per item;
- vendor invoice linkage where used;
- stock valuation, Stock Ledger and General Ledger effects on submission;
- future SLE/GLE reposting;
- cancellation and amendment behavior.

C18 must not copy ERPNext's `update_landed_cost`, stock-ledger, GL, distribution or reposting logic.

### Native unsaved handoff behavior

ERPNext v16 already exposes `erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_lcv(doctype, docname)` from both Purchase Receipt and stock-updating Purchase Invoice forms.

That native function:

1. creates a new in-memory `Landed Cost Voucher` with `frappe.new_doc`;
2. derives Company, Supplier and base total from the selected source;
3. appends the selected source into `purchase_receipts`;
4. calls native `get_items_from_purchase_receipts()`; and
5. returns `landed_cost_voucher.as_dict()` **without inserting or saving it**.

The client then uses `frappe.model.sync(...)` and routes to the standard Landed Cost Voucher form. This unsaved handoff is important because the native `taxes` / landed-cost charges table is mandatory before the first save. RetailEdge must preserve this behavior rather than bypass mandatory validation or create an incomplete saved draft.

## Scope

### Existing product surface

Extend the existing EdgeSuite `Professional Purchasing` workspace. Do not create a parallel accounting page or custom landed-cost DocType.

Add a compact **Landed Cost Allocation** action area near post-receipt purchasing operations.

### Guided source types

For the first C18 slice, support only the most common purchase-side sources:

1. submitted **Purchase Receipt**; and
2. submitted **Purchase Invoice** where `update_stock = 1`.

Do not expose Stock Entry or Subcontracting Receipt in the guided RetailEdge flow yet. They remain available in the native ERPNext Landed Cost Voucher form.

### Source discovery

Source selectors must be backend-filtered and permission-aware.

Purchase Receipt candidates:

- `docstatus = 1`;
- not a return;
- active Operating Company;
- permitted/active Branch where Branch attribution exists;
- optional Supplier scope;
- bounded results.

Purchase Invoice candidates:

- `docstatus = 1`;
- not a return;
- `update_stock = 1`;
- active Operating Company;
- permitted/active Branch where Branch attribution exists;
- optional Supplier scope;
- bounded results.

The browser must never be authoritative for source Company, Supplier, Branch, posting date or stock behavior.

### Native handoff preparation

Provide one backend action such as `prepare_landed_cost_voucher_handoff` accepting:

- source type (`Purchase Receipt` or `Purchase Invoice`);
- source name;
- optional distribution method limited to ERPNext's native values: `Qty`, `Amount`, `Distribute Manually`.

The action must:

1. require source read permission;
2. require `Landed Cost Voucher` create permission;
3. re-read the source server-side;
4. require submitted, non-return source;
5. require matching active Operating Company and permitted Branch;
6. for Purchase Invoice, require `update_stock = 1`;
7. call ERPNext v16 native `purchase_receipt.make_lcv(source.doctype, source.name)` rather than reconstructing the mapper;
8. verify the returned document is an unsaved/draft `Landed Cost Voucher` for the source Company;
9. verify exactly one `purchase_receipts` row references the selected source;
10. verify mapped receipt items exist and remain linked to the selected source;
11. set only the selected native distribution method on the unsaved returned document; default `Amount`;
12. return the native unsaved document payload for client-side `frappe.model.sync(...)` and routing to the standard Landed Cost Voucher form;
13. never call `insert()`, `save()` or `submit()` in the RetailEdge handoff.

### Important boundary: do not collect landed charges in the guided action

C18 must not accept freight/duty/clearing amounts or expense accounts in its POST payload.

Reason: those values affect valuation and accounting and ERPNext already has the authoritative Landed Cost Voucher validation/distribution UI. The native form requires those mandatory charge rows before first save, so the safe handoff is an unsaved ERPNext document rather than an incomplete persisted record.

## EdgeSuite UX

Add **Allocate Landed Cost** to Professional Purchasing.

The user should:

1. choose `Purchase Receipt` or `Stock-updating Purchase Invoice`;
2. choose an eligible source from a filtered EdgeLinkField;
3. optionally choose distribution basis: `Amount` (default), `Qty`, or `Distribute Manually`;
4. click `Prepare Landed Cost`;
5. RetailEdge calls the guarded native handoff, syncs the returned unsaved LCV into Frappe's client model, and opens the standard ERPNext Landed Cost Voucher form;
6. the user enters/reviews freight, clearing, duty, insurance or other charges, expense accounts and allocation, then saves/submits through normal ERPNext permissions.

Plain-language guidance must explain that Landed Cost affects true inventory value/gross margin and that nothing is saved or posted by the RetailEdge handoff itself.

Changing Company, Branch, Supplier or source type must clear any incompatible selected source.

## Permission and Operating Context rules

1. Source read permission is mandatory.
2. Landed Cost Voucher create permission is mandatory.
3. Source Company must match active Operating Company where one is active.
4. Source Branch, when attributed, must be permitted and match active Operating Branch where one is active.
5. Source Supplier is server-derived.
6. No `ignore_permissions=True`.
7. The returned LCV remains unsaved until the user completes native mandatory fields and saves it through ERPNext.

## Accounting and stock safety

- Unsaved native handoff only.
- Never insert/save/submit the LCV automatically.
- Never bypass mandatory validation to persist an incomplete LCV.
- Never mutate the submitted Purchase Receipt/Purchase Invoice.
- Never directly change valuation rate, landed-cost amount, Stock Ledger Entry or GL Entry.
- Never call ERPNext `update_landed_cost()` directly from RetailEdge.
- Never create/repost SLE/GLE directly.
- Never bypass expense-account, cost-centre, serial/batch, stock-closing or posting-period validation.
- Preserve Purchase Invoice `update_stock` exactly as stored on the source.
- Do not accept browser-provided Company/Supplier/Branch/receipt totals as truth.

## Files to inspect / expected bounded implementation

Primary:

- `retailedge/professional_purchasing.py` or a tightly scoped Professional Purchasing extension module;
- `retailedge/public/js/professional_purchasing/ProfessionalPurchasing.vue`;
- focused C18 backend tests;
- focused C18 EdgeSuite/source safety contract tests.

No new DocType, patch, schema or standalone page is expected.

## Tests required

### Source discovery

1. Purchase Receipt source search requires read permission and LCV create permission.
2. Purchase Invoice source search requires read permission and LCV create permission.
3. Results are bounded and permission-aware.
4. Only submitted, non-return sources are returned.
5. Purchase Invoice search includes `update_stock = 1`.
6. Company/Branch/Supplier filters are applied server-side.

### Native handoff preparation

1. Missing/unsupported source type is rejected.
2. Source read and LCV create permissions are required.
3. Draft/cancelled/return source is rejected.
4. Purchase Invoice without `update_stock` is rejected.
5. Operating Company or Branch mismatch is rejected before native handoff.
6. Company/Supplier/Branch come from server-side source context.
7. ERPNext native `make_lcv` is called exactly once with the validated source doctype/name.
8. Returned doctype must be `Landed Cost Voucher` and `docstatus` must remain `0`.
9. Exactly one source child row must reference the selected source.
10. Mapped items must exist and remain tied to the selected source.
11. Distribution method is restricted to `Amount`, `Qty`, `Distribute Manually` and defaults to `Amount`.
12. No `insert()`, `save()` or `submit()` occurs in the RetailEdge handoff.
13. Submitted source remains unchanged.

### UI / contract

1. Professional Purchasing exposes `Allocate Landed Cost` / `Prepare Landed Cost`.
2. Uses EdgeLinkField/backend filtered source discovery.
3. Purchase Receipt and stock-updating Purchase Invoice are visibly distinct source choices.
4. Company/Branch/Supplier/source-type changes clear invalid source selection.
5. Success uses `frappe.model.sync(...)` and routes to the native `Landed Cost Voucher` form.
6. UI does not collect or post landed charge/accounting rows itself.
7. Existing RFQ/PO/Receipt/Returns & Supplier Credits flows remain present.
8. EdgeSuite remains the guided frontend runtime.

### Source safety contract

Assert no C18 introduction of:

- `.submit()`;
- `.insert()` or `.save()` in the landed-cost handoff;
- `frappe.db.commit()`;
- `ignore_permissions=True`;
- direct GL/SLE creation or update;
- direct `update_landed_cost()` invocation;
- direct valuation-rate mutation;
- source-document save/mutation;
- automatic Purchase Invoice/Payment Entry/Journal Entry creation;
- `ignore_mandatory=True` or equivalent mandatory-field bypass.

## Migration and backward compatibility

No migration or new schema is expected. Existing ERPNext Landed Cost Vouchers remain authoritative and can continue to be created directly.

C18 adds only a guarded entry point into ERPNext's existing unsaved Landed Cost Voucher handoff inside Professional Purchasing.

## Out of Scope

- inserting/saving/submitting/cancelling Landed Cost Voucher from RetailEdge;
- custom landed-cost accounting engine;
- browser-side valuation calculations;
- direct freight/duty/clearing amount entry in the guided handoff;
- vendor-invoice creation/payment;
- Purchase Invoice creation;
- Stock Entry / Subcontracting Receipt guided sources in this first slice;
- landed-cost forecasting;
- customs/import documentation workflow;
- automatic expense-account selection;
- mandatory-field bypass;
- manual QA before cumulative reconciliation.

## Acceptance and execution gate

1. Keep C18 on the existing PR #53 branch only.
2. Freeze this corrected contract head because native ERPNext inspection changed the persistence assumption.
3. Require the corrected exact head to pass Theme, Linters, clean Frappe v16 CI and governed EdgeSuite compatibility.
4. Only then implement C18 on the same branch.
5. Freeze the implementation head and repeat the exact validation gate before any C19 audit.
6. Manual/browser QA remains deferred to the cumulative consolidated QA branch.
