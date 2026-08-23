# R10 — ERPNext v16 Reorder Contract

## Verified source

R10 must consume ERPNext v16 reorder configuration rather than creating a RetailEdge reorder master.

Verified against upstream ERPNext `version-16` source on 2026-08-23:

- `erpnext/stock/doctype/item/item.json`
  - Item field: `reorder_levels`
  - Field type: Table
  - Child DocType: `Item Reorder`
- `erpnext/stock/doctype/item_reorder/item_reorder.json`
  - `warehouse` — Request for
  - `warehouse_group` — Check Availability in Warehouse
  - `warehouse_reorder_level` — Re-order Level
  - `warehouse_reorder_qty` — Re-order Qty
  - `material_request_type` — Purchase / Transfer / Material Issue / Manufacture
- `erpnext/stock/reorder_item.py`
  - a configured rule is evaluated when either reorder level or reorder quantity is non-zero;
  - it triggers when projected quantity is at or below reorder level;
  - deficiency is `reorder_level - projected_qty`;
  - the effective reorder quantity is the greater of configured reorder quantity or the deficiency;
  - a missing Bin is treated as projected quantity zero;
  - variants inherit template reorder rows only when the variant has no direct rows.

## R10 interpretation rules

1. Reorder configuration is warehouse-specific ERPNext truth.
2. RetailEdge must not collapse multiple warehouse reorder rows into one undocumented item-level reorder level.
3. Any company/branch view spanning multiple warehouses should expose either location-level reorder signals or an explicitly aggregated count of affected locations.
4. `warehouse_reorder_qty` remains the configured ERPNext quantity. R10 may separately show the effective recommended quantity calculated with the same ERPNext v16 rule: `max(configured reorder quantity, reorder-level deficiency)`. This is a read-only interpretation of ERPNext behavior, not a RetailEdge forecast or replacement reorder policy.
5. `warehouse_group` is an ERPNext availability-check context and must not be silently treated as the request destination warehouse. R10 does not score warehouse-group rules unless full descendant visibility can be proven permission-safely.
6. `material_request_type` controls the ERPNext replenishment workflow type and must remain visible to the recommendation layer where relevant.
7. Suggested replenishment remains advisory. R10 must not automatically create or submit Material Requests.
8. If a user starts replenishment from R10, the safe implementation should use a permission-aware guided/native ERPNext workflow and leave submission to the existing ERPNext workflow.
9. R10 must validate the installed DocType metadata at runtime before querying Item Reorder fields so patch-level schema changes fail with a controlled compatibility error rather than a database/query failure.

## Runtime compatibility guard

Before querying reorder rows, R10 validates:

- `Item.reorder_levels` exists, is a Table field, and points to `Item Reorder`;
- `Item Reorder.warehouse` exists;
- `Item Reorder.warehouse_group` exists;
- `Item Reorder.warehouse_reorder_level` exists;
- `Item Reorder.warehouse_reorder_qty` exists;
- `Item Reorder.material_request_type` exists.

The check is cached only for the current request. If the installed ERPNext schema is incompatible, replenishment intelligence fails closed with a clear validation message. Current Bin stock remains independently usable by the resilient Action Centre stock summary.

## Current implementation boundary

Current stock and historical demand remain independently grounded in ERPNext `Bin` and bounded `Stock Ledger Entry` evidence.

R10E uses a dedicated read-only warehouse-level reorder adapter that joins native reorder rows to permitted warehouse projected quantity and observed demand without introducing persistent derived inventory truth. Direct warehouse rules are scored with ERPNext v16 semantics; warehouse-group rules are surfaced for review when full group visibility cannot be established safely.
