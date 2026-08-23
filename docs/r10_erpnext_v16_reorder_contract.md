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

## R10 interpretation rules

1. Reorder configuration is warehouse-specific ERPNext truth.
2. RetailEdge must not collapse multiple warehouse reorder rows into one undocumented item-level reorder level.
3. Any company/branch view spanning multiple warehouses should expose either location-level reorder signals or an explicitly aggregated count of affected locations.
4. `warehouse_reorder_qty` is ERPNext configuration. R10 may display it, but must not invent a replacement order quantity when it is zero or absent.
5. `warehouse_group` is an ERPNext availability-check context and must not be silently treated as the request destination warehouse.
6. `material_request_type` controls the ERPNext replenishment workflow type and must remain visible to the recommendation layer where relevant.
7. Suggested replenishment remains advisory. R10 must not automatically create or submit Material Requests.
8. If a user starts replenishment from R10, the safe first implementation should create a draft ERPNext document through a permission-aware guided/native flow and leave submission to the existing ERPNext workflow.
9. R10 must validate the installed DocType metadata at runtime before relying on these fields so patch-level schema changes fail safely.

## Current implementation boundary

R10A/R10B can proceed without reorder configuration because current stock and historical demand are already independently grounded in ERPNext `Bin` and bounded `Stock Ledger Entry` evidence.

R10E may now implement a dedicated warehouse-level reorder adapter using this verified contract. The adapter should join native reorder rows to current permitted warehouse projected quantity and observed demand without introducing persistent derived inventory truth.
