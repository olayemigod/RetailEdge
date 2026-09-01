# E16 C7A — Governed Procurement Tracker Handoff

## Goal

Expose ERPNext's existing Procurement Tracker from the EdgeSuite Professional Purchasing experience without creating a second procurement lifecycle engine.

## Business value

Purchase users need one traceable request-to-procurement view across Material Request, Purchase Order, expected/actual delivery, Supplier and actual cost. ERPNext v16 already provides this calculation in the standard `Procurement Tracker` Script Report.

## Source of truth

C7A MUST reuse ERPNext's standard `Procurement Tracker` report. RetailEdge must not reproduce or persist its Material Request → Purchase Order → Purchase Receipt → Purchase Invoice calculation.

Native ERPNext fields include Material Request date/no, Cost Center, Project, requesting Warehouse, requestor, Item, quantity/UOM, PO date/no, Supplier, estimated/actual cost, PO amount, expected delivery date and actual delivery date.

## Scope

1. Add a governed capability to the existing Professional Purchasing context.
2. The capability is available only when:
   - the standard `Procurement Tracker` Report exists;
   - the current user can read the report; and
   - the current user has global/company-wide RetailEdge Branch access.
3. Add one `Procurement Tracker` action inside the existing EdgeSuite Professional Purchasing page.
4. The action opens the native ERPNext Query Report with the current Company passed as initial route/filter context where supported.
5. Branch-restricted users must not see the action in C7A.

## Why C7A is company-wide only

ERPNext v16's native Procurement Tracker filters by Company, Cost Center, Project and dates. It has no Branch filter. Some rows can represent Material Requests that have not yet become Purchase Orders, and the native result does not expose sufficient unambiguous row-level Branch attribution for RetailEdge to prove isolation safely.

Until a future audited branch-safe source contract exists, C7A must fail closed by hiding the native tracker handoff from branch-restricted users.

## Out of Scope

- no new Procurement Tracker report engine;
- no shadow procurement ledger or lifecycle state;
- no duplication of Material Request/RFQ/Supplier Quotation/PO/PR/PI logic;
- no new Supplier Scorecard engine;
- no submitted-document mutation;
- no automatic RFQ/PO/PR/PI creation from this tracker action;
- no Branch inference from Cost Center, Project or free-form Warehouse assumptions;
- no permission bypass;
- no replacement of ERPNext Procurement Tracker.

## Implementation Requirements

### Backend

- Add a constant for `Procurement Tracker` in `retailedge/professional_purchasing.py`.
- Add a helper that returns true only when the report is readable and the user has global Branch access.
- Surface `can_open_procurement_tracker` in the existing Professional Purchasing capability map.
- Do not execute the report server-side in C7A.

### EdgeSuite UI

- Modify only the existing `ProfessionalPurchasing.vue` experience.
- Add a secondary `Procurement Tracker` action near existing PO Analysis / sourcing drill-throughs.
- Open the standard ERPNext Query Report in a new tab or native report route without replacing the EdgeSuite shell.
- Seed current Company context only; do not pass an unsupported Branch filter.
- No Frappe Dialog or legacy EdgeUI UI.

## Files to Inspect / Change

- `retailedge/professional_purchasing.py`
- `retailedge/public/js/professional_purchasing/ProfessionalPurchasing.vue`
- existing Professional Purchasing tests
- ERPNext v16 `erpnext/buying/report/procurement_tracker/*`

## Safety Rules

- ERPNext remains authoritative for procurement documents, stock and accounting.
- Respect Report read permission and RetailEdge Branch access.
- Branch-restricted users must not receive the native tracker action.
- No `ignore_permissions=True`, direct GL/SLE writes, manual commit or submitted-document mutation.
- Preserve existing Professional Purchasing behavior.

## Tests Required

1. Capability true when report is readable and global Branch access is true.
2. Capability false when report is unavailable/unreadable.
3. Capability false for branch-restricted access even if the report is readable.
4. UI renders `Procurement Tracker` only behind the capability.
5. UI opens the native report and carries Company context without Branch.
6. Existing Professional Purchasing RFQ/PO/receipt behavior remains unchanged.
7. Contract guards against introducing a second tracker dataset or posting workflow.

## Acceptance

After implementation, freeze one exact head and require:

- RetailEdge Theme Compatibility green;
- Linters / pre-commit / Semgrep / vulnerable dependency audit green;
- clean Frappe v16 standalone CI green including full RetailEdge tests;
- governed EdgeSuite UI Candidate Compatibility green including build/migrate/full tests.

Manual/browser QA remains deferred to the consolidated QA branch.
