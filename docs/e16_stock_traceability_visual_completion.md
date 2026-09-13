# E16 C30 — Stock Traceability EdgeSuite Visual Completion

## Goal

Make batch and serial traceability an EdgeSuite-first RetailEdge experience while keeping ERPNext as the sole stock, expiry, valuation, warranty and traceability source of truth.

## Context

C14A exposed native ERPNext Batch and Serial No destinations. C15 later hardened RetailEdge report navigation through Frappe's native `get_report_doc` permission gate. C30 can therefore safely add a primary EdgeSuite traceability overview and permission-gated native report handoffs without duplicating ERPNext report datasets.

## Scope

- Add `stock-traceability-control` after Stock Locations as the primary traceability destination.
- Reuse the established `native_visual_workspaces` / `NativeERPNextWorkspace.vue` composition.
- Show bounded recent Batch records when native Batch read permission is available.
- Show bounded recent Serial No records when native Serial No read permission is available.
- Retain Batches and Serial Numbers exactly once as native advanced/fallback routes.
- Add workspace handoffs to native ERPNext reports only when `get_report_doc` grants report access:
  - Batch Item Expiry Status;
  - Available Batch Report;
  - Available Serial No.
- Keep `Serial and Batch Bundle` hidden from business navigation.

## Native fields surfaced

Batch preview uses metadata-present fields such as Item, Item Name, Batch Quantity, UOM, Manufacturing Date, Expiry Date, Disabled state and Supplier.

Serial preview uses metadata-present fields such as Item, Batch, Warehouse, Status, Company, Customer, Warranty Expiry, AMC Expiry and Maintenance Status.

The generic provider applies `meta.has_field` before querying, so schema/version differences fail safely.

## ERPNext authority

ERPNext remains authoritative for:

- batch and serial identity;
- current stock quantity and warehouse state;
- manufacturing and expiry dates;
- warranty/AMC status;
- Serial and Batch Bundle transactions;
- movement, split and stock reconciliation behaviour;
- Stock Ledger and valuation;
- buying/selling/stock transaction validation;
- the three native reports and their filters/calculations.

RetailEdge does not reconstruct available quantity, expiry status, valuation or serial/batch movement.

## Permission and safety rules

- DocType previews require native ERPNext read permission and use permission-aware `frappe.get_list`.
- Native report handoffs require Frappe's `get_report_doc` permission check.
- No hard-coded RetailEdge role gate is used to broaden access.
- No custom Batch/Serial creation, movement, split or reconciliation wrapper is introduced.
- No direct Serial and Batch Bundle, Stock Ledger Entry or GL Entry write.
- No `ignore_permissions`, manual commit, shadow traceability ledger or submitted stock-document mutation.

## Files

- `retailedge/native_visual_workspaces.py`
- `retailedge/edgesuite_ui.py`
- `retailedge/retailedge/page/stock_traceability_control/stock_traceability_control.js`
- `retailedge/retailedge/page/stock_traceability_control/stock_traceability_control.json`
- `retailedge/retailedge/page/stock_traceability_control/stock_traceability_control.py`
- `retailedge/tests/test_stock_traceability_navigation_contract.py`

## Validation required

- focused traceability navigation/UI/safety contract;
- Theme compatibility;
- Linters/pre-commit/Semgrep/dependency audit;
- clean Frappe v16 install/build/full RetailEdge tests;
- governed EdgeSuite UI candidate build/migrate/full RetailEdge tests.

## Manual QA

Deferred to the consolidated RetailEdge QA branch. Validate permission-filtered Batch/Serial previews, native report handoffs, expiry/warranty display, advanced native links, dark mode, responsive layout and absence of internal Serial and Batch Bundle navigation.
