# E16 C18 — Guided Landed Cost Allocation

## Goal

Make freight, clearing, customs duty, insurance and other acquisition costs discoverable from RetailEdge purchasing operations while ERPNext v16 Landed Cost Voucher remains the sole authority for inventory valuation and accounting effects.

C18 is a draft-first handoff. RetailEdge must not calculate or post inventory revaluation itself.

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

### Draft preparation

Provide one backend action such as `prepare_landed_cost_voucher_draft` accepting:

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
7. create a new native `Landed Cost Voucher` draft using `frappe.new_doc("Landed Cost Voucher")`;
8. derive Company from the source;
9. append exactly the selected source into the native `purchase_receipts` child table using ERPNext's `receipt_document_type` / `receipt_document` contract;
10. use the native `get_receipt_document_details` method to populate Supplier, posting date and grand total rather than trusting browser values;
11. call native `get_items_from_purchase_receipts()` to populate authoritative receipt items;
12. reject a draft with no mapped items;
13. set only the selected native distribution method; default `Amount`;
14. insert the Landed Cost Voucher as the current user, draft only;
15. return `/app/landed-cost-voucher/<name>` for the user to enter/review landed charges, vendor invoices, expense accounts and allocation before standard ERPNext submission.

### Important boundary: do not collect landed charges in the guided action

C18 should prepare the native draft and route to ERPNext. The RetailEdge handoff must not accept freight/duty/clearing amounts or expense accounts in its POST payload in this slice.

Reason: those values affect valuation and accounting and ERPNext already has the authoritative Landed Cost Voucher validation/distribution UI. Keeping charge entry native materially reduces accounting risk.

## EdgeSuite UX

Add **Allocate Landed Cost** to Professional Purchasing.

The user should:

1. choose `Purchase Receipt` or `Stock-updating Purchase Invoice`;
2. choose an eligible source from a filtered EdgeLinkField;
3. optionally choose distribution basis: `Amount` (default), `Qty`, or `Distribute Manually`;
4. click `Prepare Landed Cost Draft`;
5. land on the standard ERPNext Landed Cost Voucher draft to add/review freight, clearing, duty, insurance or other charges and submit through normal ERPNext permissions.

Plain-language guidance must explain that Landed Cost affects true inventory value/gross margin and that nothing is posted until the native voucher is reviewed and submitted.

Changing Company, Branch, Supplier or source type must clear any incompatible selected source.

## Permission and Operating Context rules

1. Source read permission is mandatory.
2. Landed Cost Voucher create permission is mandatory.
3. Source Company must match active Operating Company where one is active.
4. Source Branch, when attributed, must be permitted and match active Operating Branch where one is active.
5. Source Supplier is server-derived.
6. No `ignore_permissions=True`.
7. The native LCV draft is inserted as the current user.

## Accounting and stock safety

- Draft only.
- Never submit the LCV automatically.
- Never mutate the submitted Purchase Receipt/Purchase Invoice.
- Never directly change valuation rate, landed-cost amount, Stock Ledger Entry or GL Entry.
- Never call ERPNext `update_landed_cost()` directly from RetailEdge.
- Never create/repost SLE/GLE directly.
- Never bypass expense-account, cost-centre, serial/batch, stock-closing or posting-period validation.
- Preserve Purchase Invoice `update_stock` exactly as stored on the source.
- Do not accept browser-provided Company/Supplier/Branch/receipt totals as truth.

## Files to inspect / expected bounded implementation

Primary:

- `retailedge/professional_purchasing.py`
- `retailedge/public/js/professional_purchasing/ProfessionalPurchasing.vue`
- focused C18 backend tests
- focused C18 EdgeSuite/source safety contract tests

No new DocType, patch, schema or standalone page is expected.

## Tests required

### Source discovery

1. Purchase Receipt source search requires read permission and LCV create permission.
2. Purchase Invoice source search requires read permission and LCV create permission.
3. Results are bounded and permission-aware.
4. Only submitted, non-return sources are returned.
5. Purchase Invoice search includes `update_stock = 1`.
6. Company/Branch/Supplier filters are applied server-side.

### Draft preparation

1. Missing/unsupported source type is rejected.
2. Source read and LCV create permissions are required.
3. Draft/cancelled/return source is rejected.
4. Purchase Invoice without `update_stock` is rejected.
5. Operating Company or Branch mismatch is rejected before draft insertion.
6. Company/Supplier/Branch come from server-side source context.
7. Exactly one source child row is added.
8. `get_receipt_document_details` is used for native source details.
9. `get_items_from_purchase_receipts()` is called exactly once.
10. No-item result is rejected.
11. Distribution method is restricted to `Amount`, `Qty`, `Distribute Manually` and defaults to `Amount`.
12. Valid LCV is inserted exactly once and remains `docstatus = 0`.
13. Submitted source remains unchanged.

### UI / contract

1. Professional Purchasing exposes `Allocate Landed Cost` / `Prepare Landed Cost Draft`.
2. Uses EdgeLinkField/backend filtered source discovery.
3. Purchase Receipt and stock-updating Purchase Invoice are visibly distinct source choices.
4. Company/Branch/Supplier/source-type changes clear invalid source selection.
5. Success routes to native `Landed Cost Voucher` form.
6. UI does not collect or post landed charge/accounting rows itself.
7. Existing RFQ/PO/Receipt/Returns & Supplier Credits flows remain present.
8. EdgeSuite remains the guided frontend runtime.

### Source safety contract

Assert no C18 introduction of:

- `.submit()`;
- `frappe.db.commit()`;
- `ignore_permissions=True`;
- direct GL/SLE creation or update;
- direct `update_landed_cost()` invocation;
- direct valuation-rate mutation;
- source-document save/mutation;
- automatic Purchase Invoice/Payment Entry/Journal Entry creation.

## Migration and backward compatibility

No migration or new schema is expected. Existing ERPNext Landed Cost Vouchers remain authoritative and can continue to be created directly.

C18 adds only a guided draft-preparation entry point inside existing Professional Purchasing.

## Out of Scope

- submitting/cancelling Landed Cost Voucher from RetailEdge;
- custom landed-cost accounting engine;
- browser-side valuation calculations;
- direct freight/duty/clearing amount entry in the guided handoff;
- vendor-invoice creation/payment;
- Purchase Invoice creation;
- Stock Entry / Subcontracting Receipt guided sources in this first slice;
- landed-cost forecasting;
- customs/import documentation workflow;
- automatic expense-account selection;
- manual QA before cumulative reconciliation.

## Acceptance and execution gate

1. Commit this C18 audit/contract on the existing PR #53 branch only.
2. Freeze the exact contract head.
3. Require that exact head to pass Theme, Linters, clean Frappe v16 CI and governed EdgeSuite compatibility.
4. Only then implement C18 on the same branch.
5. Freeze the implementation head and repeat the exact validation gate before any C19 audit.
6. Manual/browser QA remains deferred to the cumulative consolidated QA branch.
