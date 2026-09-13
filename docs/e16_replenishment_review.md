# E16 C21 — Replenishment Review

## Goal
Extend RetailEdge Stock Position with ERPNext-native replenishment signals so users can see where projected stock has reached configured reorder thresholds and act without introducing a second reorder engine.

## Business context
RetailEdge already exposes native Stock Count (`Stock Reconciliation`) and Reorder Requests (`Material Request`) in Stock navigation. It also already provides:
- `guided_stock_adjustment.py`, which creates quantity-only draft ERPNext Stock Reconciliations;
- Stock Position with actual, reserved, available, ordered and projected quantities;
- Professional Purchasing with submitted Purchase Material Requests and RFQ handoff.

The remaining gap is action-oriented visibility between current/projected stock and ERPNext `Item Reorder` rules.

## Native ERPNext authority
ERPNext v16 `Item Reorder` defines, per rule:
- `warehouse` — Request for;
- `warehouse_group` — Check Availability in Warehouse;
- `warehouse_reorder_level` — Re-order Level;
- `warehouse_reorder_qty` — Re-order Qty;
- `material_request_type` — Purchase, Transfer, Material Issue or Manufacture.

For a direct warehouse rule, ERPNext considers replenishment due when:

`projected_qty <= warehouse_reorder_level`

When due, the native requested stock quantity is at least `warehouse_reorder_qty`, but increases to the deficiency when `warehouse_reorder_level - projected_qty` is larger.

ERPNext's scheduled auto-reorder path may create and submit Material Requests automatically. RetailEdge must not invoke that scheduler from an interactive page.

## Scope
### Existing EdgeSuite Stock Position
Enhance the existing Stock Position dataset and UI; do not create a parallel stock/replenishment page.

For direct-warehouse `Item Reorder` rules inside the user's already permitted Company/Branch/Warehouse scope, expose read-only signals such as:
- Replenishment Status: `Reorder Due` / `Configured` / no direct rule;
- Reorder Due Locations count;
- Suggested Reorder Qty (stock UOM, aggregated from due direct-warehouse rules);
- configured direct-rule count;
- optionally a concise due-location summary where bounded and useful.

Add a `Reorder Due` Stock Status/filter option so users can isolate exceptions.

Rows with a valid direct-warehouse reorder rule must be considered even when no `Bin` exists for that item/warehouse; ERPNext treats that projected quantity as zero for reorder evaluation.

### Action handoff
Where the user has native Material Request create permission, provide a safe action from Stock Position to start a standard ERPNext Material Request workflow. The first implementation should prefer a native form/new-document handoff with server-derived Company/Branch/Warehouse/item context rather than invoking ERPNext's scheduled auto-reorder function.

If a prefilled draft is implemented, it must:
- create only a draft `Material Request` (`docstatus = 0`);
- use only currently due direct-warehouse rules that are revalidated server-side;
- preserve the native rule's `material_request_type` and warehouse;
- never submit automatically;
- never create Purchase Orders, Stock Entries, GL Entries or Stock Ledger Entries;
- never call `erpnext.stock.reorder_item.reorder_item`, `_reorder_item`, or `create_material_request`.

If mixed Material Request types are selected, do not merge them into one invalid document; either require one type per handoff or use separate draft documents only when explicitly designed and tested.

## Warehouse-group rules
Warehouse-group reorder rules are out of scope for C21 guided evaluation.

Reason: ERPNext can evaluate projected quantity across a warehouse hierarchy. RetailEdge branch scope may cover only part of that hierarchy, so reproducing the group aggregation inside a branch-scoped report could distort the native result or expose stock outside the user's permitted operational scope.

C21 must therefore:
- evaluate only direct `Item Reorder.warehouse` rules;
- not reinterpret `warehouse_group` rules;
- optionally indicate that group-based rules remain managed by native ERPNext auto-reorder/setup when that can be shown without exposing out-of-scope warehouse data.

## Backend requirements
Prefer extending `retailedge/stock_position.py` rather than creating a second stock dataset.

### Read path
- Reuse `_resolve_warehouse_scope(filters)` as the authoritative permitted warehouse scope.
- Retain existing Company, Branch, Warehouse, Item Group and Item permission checks.
- Read only active stock Items.
- Load direct `Item Reorder` child rows for relevant items and permitted warehouses only.
- Bound reorder-rule scanning; do not load every Item Reorder row in the database when filters/scope can narrow it.
- For each direct rule, use the projected quantity of that exact item/warehouse Bin; if no Bin exists, use zero, matching ERPNext behavior.
- Reorder is due only when `(reorder_level or reorder_qty)` and `projected_qty <= reorder_level`.
- Suggested stock quantity is `max(reorder_qty, reorder_level - projected_qty)` in stock UOM for the read model.
- Do not copy ERPNext's automatic Material Request submission engine.
- Preserve existing Stock Position cost-visibility behavior.
- Ensure reorder-only rows with zero/no Bin are not discarded by the existing `include_zero` rule when they are `Reorder Due`.

### Optional draft handoff
If implemented, add a narrow POST API separate from the report read path. It must:
- require native `Material Request` create permission;
- re-resolve Company/Branch/Warehouse scope server-side;
- re-read and re-evaluate each selected direct reorder rule at execution time;
- reject stale/not-due/out-of-scope rules;
- cap selected rules/items;
- create draft only;
- use standard Frappe/ERPNext document validation;
- not use `ignore_permissions` or manual commits.

## Frontend requirements
Modify only the existing EdgeSuite Stock Position experience unless a dedicated child component materially reduces risk.

Required UX:
- keep `EdgeAppShell` / `EdgeReportShell` and current filters/export behavior;
- add `Reorder Due` to Stock Status options;
- expose clear replenishment columns/cards without showing valuation to users whose RetailEdge cost visibility hides it;
- make due rows actionable through native Material Request workflow only when permission allows;
- preserve item click-through and existing sorting/pagination/export behavior;
- no `frappe.ui.Dialog`, `frappe.prompt`, `frappe.msgprint`, classic parallel page, or browser-only authority.

Export must use the same server-side replenishment dataset and must not export out-of-scope reorder rules.

## Out of scope
- no new reorder master or shadow reorder settings;
- no RetailEdge-specific forecast formula;
- no automatic Material Request submission;
- no automatic Purchase Order creation;
- no supplier selection/PO generation from Stock Position;
- no direct stock/valuation/GL/SLE writes;
- no group-warehouse reorder recreation in C21;
- no replacement of ERPNext Stock Settings auto reorder;
- no change to existing guided Stock Adjustment behavior;
- no new schema/patch unless later evidence proves it unavoidable.

## Safety rules
- ERPNext `Item Reorder`, `Bin`, `Material Request`, Warehouse and Item remain authoritative.
- No `ignore_permissions`.
- No direct SQL/DB writes to Bin, Item Reorder, Material Request, GL Entry or Stock Ledger Entry.
- No call to ERPNext scheduled auto-reorder creation/submission functions from the interactive RetailEdge flow.
- Company/Branch/Warehouse scope must be resolved server-side.
- Do not expose group-warehouse projected quantities across branch boundaries.
- Do not mutate submitted documents.

## Tests required
### Backend/read model
- direct rule due when projected quantity is below reorder level;
- direct rule due when projected quantity equals reorder level;
- configured but not due when projected quantity is above reorder level;
- rule with both level and qty zero is not due;
- suggested stock quantity uses configured reorder qty when it is larger than deficiency;
- suggested stock quantity uses deficiency when deficiency is larger;
- missing Bin is evaluated as projected quantity zero;
- reorder-only item can appear even with no Bin when due;
- direct rules outside permitted warehouse/branch/company scope are excluded;
- warehouse-group-only rules are not evaluated as C21 direct rules;
- existing cost visibility, pagination and export remain intact;
- scans remain bounded.

### Draft handoff, if included
- requires Material Request create permission;
- revalidates due state and warehouse scope server-side;
- rejects stale/not-due rules;
- creates draft only;
- preserves material request type and warehouse;
- no submit, auto-reorder scheduler call, Purchase Order, GL Entry, Stock Ledger Entry, `ignore_permissions` or manual commit.

### UI/static contract
- Stock Position remains EdgeSuite UI;
- `Reorder Due` filter/status is available;
- replenishment columns/cards are present;
- existing stock filters/export/item click-through remain present;
- no classic dialog/prompt/msgprint flow;
- no second replenishment page is introduced.

## Migration and backward compatibility
No migration should be required. Existing Items, Item Reorder rows, Bins, Material Requests, Stock Settings, guided stock adjustment, Stock Position and Professional Purchasing behavior must remain compatible.

ERPNext installations that do not configure reorder rules continue to see normal Stock Position without false replenishment exceptions.

## Manual QA deferred
Manual/browser QA remains deferred to the cumulative reconciliation/QA branch. C21 must first pass the standard exact-head Theme, duplicate Linters, duplicate clean Frappe v16 CI and duplicate EdgeSuite compatibility gates before production implementation begins, and the same full gate must pass again on the frozen production head.
