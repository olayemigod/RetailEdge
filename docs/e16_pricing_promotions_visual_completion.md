# E16 C28 — Pricing & Promotions EdgeSuite Visual Completion

## Goal

Make Pricing & Promotions an EdgeSuite-first RetailEdge experience while keeping ERPNext as the sole authority for Price List, Item Price, Pricing Rule, Promotional Scheme, Coupon Code and Loyalty Program master data and transaction-time pricing evaluation.

## Context

C16 previously delivered permission-aware native discoverability for the six ERPNext pricing and promotion masters. That was safe but left normal RetailEdge users without a primary EdgeSuite surface. C28 closes that visual gap without introducing another pricing engine.

## Scope

- Add `pricing-promotions-control` as the primary Pricing & Promotions destination.
- Reuse the existing C27 `native_visual_workspaces` EdgeSuite composition and shared `NativeERPNextWorkspace.vue` surface.
- Show only native capabilities the current user may read.
- Show bounded recent records for permitted DocTypes.
- Preserve native create/list/form handoffs for advanced master maintenance.
- Keep all six original native destinations in navigation as advanced/fallback routes.

## ERPNext authority

ERPNext remains authoritative for:

- Price List selling/buying configuration;
- Item Price rates, currencies, UOM and validity;
- Pricing Rule conditions, priorities and discounts;
- Promotional Scheme generation and rule behaviour;
- Coupon Code validity and usage;
- Loyalty Program configuration and points rules;
- final pricing evaluation on Quotation, Sales Order, Delivery Note, Sales Invoice, POS and purchasing documents.

C28 does not calculate an alternative selling price, promotion result, coupon eligibility or loyalty balance.

## Permission and safety rules

- No hard-coded RetailEdge role gate is added to the Pricing & Promotions group.
- Each ERPNext DocType is independently checked for existence and native `read` permission before its data is exposed.
- Recent-record queries use `frappe.get_list`, so normal Frappe permission query conditions remain active.
- Native create actions are shown only when ERPNext grants `create` permission.
- No `ignore_permissions`, manual commit, custom pricing ledger, pricing-rule write API, GL Entry write, Stock Ledger Entry write or submitted transaction mutation is introduced.
- The workspace is a read-only operational overview; authoritative edits remain native ERPNext lifecycle actions.

## Files

- `retailedge/native_visual_workspaces.py`
- `retailedge/edgesuite_ui.py`
- `retailedge/retailedge/page/pricing_promotions_control/pricing_promotions_control.js`
- `retailedge/retailedge/page/pricing_promotions_control/pricing_promotions_control.json`
- `retailedge/retailedge/page/pricing_promotions_control/pricing_promotions_control.py`
- `retailedge/tests/test_pricing_promotions_navigation_contract.py`

## Tests required

1. Pricing & Promotions has exactly one primary EdgeSuite Page target.
2. The original six ERPNext native masters remain present exactly once and in the approved order.
3. The Page loads `edgeui.bundle.js` and `native_visual_workspaces.bundle.js` and mounts `pricing-promotions`.
4. The new page does not introduce legacy `window.EdgeUI` or Frappe modal/prompt workflow surfaces.
5. The workspace backend remains read-only and permission-aware.
6. Full RetailEdge CI, Theme compatibility and governed EdgeSuite candidate compatibility must pass at one frozen exact head.

## Manual QA

Deferred to the consolidated RetailEdge QA branch. When reached, verify light/dark/mobile layout, permission-filtered work areas, recent-record tables, native advanced handoffs, and that users lacking access to an individual pricing master do not see its data.
