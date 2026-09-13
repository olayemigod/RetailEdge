# E16 C19 — Guided Incoming Quality Inspection

## Goal

Add an EdgeSuite-guided incoming quality-control step to Professional Purchasing without creating a RetailEdge inspection engine or bypassing ERPNext stock controls.

The first C19 slice lets a permitted user select an existing persisted **draft Purchase Receipt**, see only receipt rows that ERPNext considers eligible for incoming Quality Inspection, provide the sample size for selected rows, and create the corresponding **draft ERPNext Quality Inspection** documents through ERPNext's native quality-inspection service.

ERPNext remains authoritative for:

- whether an item requires incoming inspection;
- Quality Inspection templates, parameters, readings and acceptance logic;
- draft/submitted Quality Inspection status;
- the link from Quality Inspection back to the Purchase Receipt item row;
- Purchase Receipt submission gates for missing, unsubmitted or rejected inspections;
- Stock Settings that control inspection enforcement.

## Why C19

The competitive-gap audit after C18 found no RetailEdge Quality Inspection or Supplier Scorecard surface.

Quality Inspection is the stronger immediate gap because it sits directly inside receiving correctness and stock acceptance. ERPNext v16 already exposes Quality Inspection from Purchase Receipt/Purchase Invoice/other stock transactions and already owns the relevant validation rules.

Supplier Scorecard is a broader configurable supplier-evaluation subsystem with criteria, variables, standings and periods. It remains a later, separate competitive-gap candidate and must not be mixed into this C19 receiving-control slice.

## Native ERPNext authority verified

ERPNext v16 `erpnext.TransactionController.setup_quality_inspection()`:

- supports Purchase Receipt and other stock-bearing transaction types;
- exposes Quality Inspection creation only for an existing document;
- permits the action while the source is draft, or after submission only when ERPNext explicitly exposes the post-submission allowance;
- requires Quality Inspection create permission;
- treats Purchase Receipt as an `Incoming` inspection context.

ERPNext v16 `erpnext.controllers.stock_controller.check_item_quality_inspection(...)`:

- determines which source rows require Quality Inspection from ERPNext Item/Stock Settings rules;
- does not require RetailEdge to reproduce the item-inspection-required logic.

ERPNext v16 `erpnext.controllers.stock_controller.make_quality_inspections(...)`:

- creates standard `Quality Inspection` documents;
- sets Company, inspection type, inspected by, reference type/name, item, description, sample size, serial/batch context and child-row reference;
- saves the Quality Inspections as drafts;
- returns the created Quality Inspection names;
- does not submit the Quality Inspections.

ERPNext StockController validation remains the submission authority for missing, unsubmitted or rejected Quality Inspections.

## First guided scope

### Included source

Only persisted **draft Purchase Receipts**:

- `doctype = Purchase Receipt`
- `docstatus = 0`
- `is_return = 0`
- document already has a real ERPNext name; unsaved browser-local Purchase Receipts are not eligible
- Company/Branch/Supplier must match the authorised Professional Purchasing operating scope

C19 deliberately does **not** guide creation against submitted Purchase Receipts. ERPNext can support Quality Inspection after submission under Stock Settings, but ProcessEdge's first slice avoids adding a guided path that mutates reference metadata on a submitted stock/accounting document.

Users who intentionally use ERPNext's native post-submission Quality Inspection capability can continue using the native ERPNext form.

### Eligible receipt rows

RetailEdge must re-read the selected Purchase Receipt server-side and derive all candidate rows from the authoritative document.

Rows must be excluded when:

- they do not belong to the selected Purchase Receipt;
- they already have a `quality_inspection` link;
- their accepted quantity is not positive;
- ERPNext's native `check_item_quality_inspection(...)` does not classify them as requiring/eligible for Quality Inspection.

The browser must never be allowed to supply authoritative Item, quantity, Company, Supplier, Branch, serial number, batch number or child-row identity independently of the selected Purchase Receipt.

### Sample size

EdgeSuite may collect a sample size for each selected eligible receipt row because ERPNext's native Quality Inspection creation UI requires it.

Rules:

- sample size must be positive;
- sample size must not exceed the authoritative accepted quantity on the Purchase Receipt row;
- ERPNext's native service remains the final validation authority;
- default may be the Purchase Receipt row's `sample_quantity` when valid;
- changing sample size does not alter Purchase Receipt quantity.

## Proposed backend contract

Use a dedicated C19 module such as:

`retailedge/incoming_quality_inspection.py`

### Capability

`get_incoming_quality_capability()`

Return permission-aware capability only. At minimum:

- can read Purchase Receipt;
- can create Quality Inspection;
- whether guided incoming inspection is available.

No hidden bypass if permissions are missing.

### Source search

`search_incoming_quality_receipts(txt="", company=None, branch=None, supplier=None)`

Requirements:

- permission-aware;
- bounded by existing `MAX_LINK_RESULTS` or an equally explicit bound;
- `docstatus = 0`;
- `is_return = 0`;
- Company/Branch/Supplier filters;
- Operating Context and branch-access enforcement;
- only persisted draft Purchase Receipts.

### Receipt inspection context

`get_incoming_quality_receipt_context(purchase_receipt)`

Requirements:

1. assert Purchase Receipt read permission and Quality Inspection create permission;
2. re-read the Purchase Receipt server-side;
3. require `docstatus = 0` and `is_return = 0`;
4. validate Company/Branch against authorised Operating Context;
5. construct candidate item dictionaries from the authoritative Purchase Receipt rows;
6. exclude rows that already have a Quality Inspection;
7. call ERPNext native `check_item_quality_inspection(...)` rather than reproducing Item/Stock Settings inspection rules;
8. return only eligible rows with business-safe fields needed by EdgeSuite, such as child row name, item code/name, accepted quantity, UOM, warehouse, batch/serial summary and suggested sample size.

The response is guidance/read-model data only.

### Create draft inspections

`create_incoming_quality_inspections(purchase_receipt, selections)`

`selections` may contain only:

- authoritative Purchase Receipt child-row name;
- requested sample size.

Backend requirements:

1. re-read and revalidate the Purchase Receipt inside the POST request;
2. reject a source that is no longer draft, is now a return, or is outside authorised Company/Branch scope;
3. require Quality Inspection create permission;
4. de-duplicate selected child-row names and apply an explicit reasonable row-count bound;
5. re-derive Item, quantity, description, serial/batch and child-row identity from the Purchase Receipt;
6. reject rows already linked to a Quality Inspection;
7. rerun ERPNext native eligibility checking immediately before creation;
8. validate sample size against the authoritative row quantity;
9. call ERPNext native `make_quality_inspections(...)` with:
   - authoritative Company;
   - `doctype = Purchase Receipt`;
   - authoritative Purchase Receipt name;
   - server-reconstructed selected row payloads;
   - `inspection_type = Incoming`;
10. return the created draft Quality Inspection names and native routes;
11. never submit a Quality Inspection or Purchase Receipt.

The Frappe request remains the transaction boundary. Do not add manual `frappe.db.commit()`.

## EdgeSuite UI contract

Extend the existing `ProfessionalPurchasing.vue`; do not add a classic custom Frappe page/dialog.

Suggested section title:

**Incoming Quality Inspection**

Suggested business wording:

- explain that inspection is performed before receipt submission;
- make clear that ERPNext inspection templates/readings remain authoritative;
- show only relevant persisted draft Purchase Receipts;
- after receipt selection, show only eligible rows;
- allow row selection and sample-size entry;
- create draft Quality Inspections only;
- show created inspection links and allow opening the native ERPNext Quality Inspection form for readings/review/submission;
- provide a native Purchase Receipt link so the user can return to the receipt after inspection.

No `frappe.ui.Dialog`, `frappe.prompt`, `frappe.msgprint`, or separate classic RetailEdge inspection surface.

## Accounting and stock safety

C19 must not:

- submit or cancel Purchase Receipts;
- submit Quality Inspections;
- alter received quantity, valuation rate, warehouse, taxes or accounting fields;
- write GL Entry or Stock Ledger Entry;
- create a RetailEdge quality-status ledger;
- duplicate ERPNext Quality Inspection readings/templates/acceptance formulas;
- use `ignore_permissions`;
- call manual database commit;
- create Quality Inspections against submitted Purchase Receipts in the first guided slice;
- allow browser-provided Company/Branch/Supplier/Item/quantity/serial/batch values to become authoritative.

Draft Quality Inspection creation through ERPNext's own `make_quality_inspections(...)` is intentionally allowed because it is the standard ERPNext non-accounting quality-control document creation path.

## Multi-app and backward compatibility

- no ERPNext core modification;
- no monkey patch;
- no new mandatory dependency beyond ERPNext already required by RetailEdge;
- no hard CoreEdge dependency;
- no new RetailEdge DocType required for first C19 slice;
- no schema patch required unless implementation evidence later proves one necessary;
- existing Professional Purchasing, Purchase Return/Debit Note and Landed Cost flows must remain unchanged;
- native ERPNext Quality Inspection remains fully usable outside RetailEdge.

## Tests required before production implementation

### Backend contract tests

Cover at minimum:

- capability permission combinations;
- source search filters `docstatus = 0`, `is_return = 0`, Company/Branch/Supplier and bound;
- submitted Purchase Receipt rejected;
- return Purchase Receipt rejected;
- source outside authorised branch rejected;
- source read and Quality Inspection create permissions required;
- already-inspected child row excluded/rejected;
- native eligibility helper is used;
- browser cannot substitute Item/quantity/serial/batch/company values;
- duplicate child-row selections rejected or safely de-duplicated;
- zero/negative sample size rejected;
- sample size greater than authoritative quantity rejected;
- native `make_quality_inspections(...)` called with server-reconstructed rows and `Incoming` inspection type;
- created documents remain drafts;
- no Quality Inspection or Purchase Receipt submission path.

### UI/static contract tests

Cover at minimum:

- Incoming Quality Inspection section exists inside EdgeSuite Professional Purchasing;
- backend-filtered Purchase Receipt source search is used;
- Company/Branch/Supplier changes clear the selected quality source/context without breaking C17/C18 resets;
- eligible receipt rows and sample-size controls are present;
- created Quality Inspection names route to native ERPNext forms;
- existing Professional Purchasing, Returns & Supplier Credits and Landed Cost Allocation remain present;
- no `frappe.ui.Dialog`, `frappe.prompt`, `frappe.msgprint` or old EdgeUI dependency introduced.

### Static safety contract

Production C19 code must not contain:

- `.submit(` on Purchase Receipt or Quality Inspection;
- `frappe.db.commit`;
- `ignore_permissions=True`;
- direct GL Entry creation;
- direct Stock Ledger Entry creation;
- a custom Quality Inspection DocType/schema.

## Validation gate

Before production C19 code:

1. commit this contract only on the existing E16 branch/PR #53;
2. freeze that exact SHA;
3. require RetailEdge Theme Compatibility green;
4. require both Linters green;
5. require both clean Frappe v16 CI runs green;
6. require both governed EdgeSuite UI Candidate Compatibility runs green;
7. only then implement production C19 on the same branch/PR.

After production implementation, freeze the new exact SHA and rerun the same complete gate before moving to another competitive-gap slice.

## Out of scope for C19 first slice

- submitted Purchase Receipt post-submission inspection guidance;
- Purchase Invoice quality-inspection guidance;
- Subcontracting Receipt quality-inspection guidance;
- outgoing inspection for Delivery Note/Sales Invoice;
- Stock Entry manufacturing/transfer inspection flows;
- Quality Inspection Template administration;
- Quality Inspection Parameter administration;
- custom acceptance formulas or readings engine;
- auto-submission or auto-acceptance/rejection;
- Supplier Scorecard, supplier scoring criteria, standings or scoring periods;
- supplier blocking/suspension policy changes.

## C19 decision

Proceed with **Guided Incoming Quality Inspection for persisted draft Purchase Receipts** as the next incremental E16 competitive-gap slice.

Keep Supplier Scorecard as a separate later audit/contract so supplier evaluation is not conflated with receipt-level quality control.
