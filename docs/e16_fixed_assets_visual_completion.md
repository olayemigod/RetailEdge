# E16 C29 — Fixed Assets EdgeSuite Visual Completion

## Goal

Make Assets an EdgeSuite-first RetailEdge experience while preserving ERPNext as the sole fixed-asset and accounting source of truth.

## Context

C13A exposed native ERPNext `Asset` and `Asset Category` safely, but the Assets group still opened native Desk as its only operating experience. C29 adds a primary EdgeSuite overview without recreating ERPNext Asset lifecycle behaviour.

## Scope

- Add `assets-control` as the first and primary Assets navigation destination.
- Reuse the established `native_visual_workspaces` / `NativeERPNextWorkspace.vue` composition already used by other visual-completion slices.
- Show a bounded recent Asset register only when the current user has native Asset read permission.
- Show bounded Asset Category configuration only when the current user has native Asset Category read permission.
- Retain native `Asset` and `Asset Category` destinations exactly once as advanced/fallback routes.
- Surface native create actions only where ERPNext already grants create permission.

## Asset overview fields

The Asset preview uses only fields present in the installed ERPNext metadata. Candidate fields include:

- Asset Name;
- Item Code;
- Company;
- Asset Category;
- Location;
- Status;
- Custodian;
- Maintenance Required;
- Calculate Depreciation;
- Next Depreciation Date.

The generic workspace provider filters candidate fields through `meta.has_field`, so version/schema differences fail safely rather than causing an invalid query.

Asset Category preview includes native category name, CWIP setting and non-depreciable classification where present.

## ERPNext authority

ERPNext remains authoritative for:

- Asset creation, submission, cancellation and amendment;
- purchase/capitalisation linkage;
- depreciation methods, finance books and schedules;
- Asset Movement / transfer;
- Asset Repair and Maintenance;
- Asset Value Adjustment;
- asset split;
- sale, scrap and restore;
- Journal Entry / General Ledger effects;
- Asset Category finance-book and account configuration.

C29 does not implement wrappers for any of those lifecycle operations.

## Permission and safety rules

- The Assets navigation group has no hard-coded RetailEdge role gate; native ERPNext permissions remain authoritative, including valid non-Accounts roles such as Quality Manager where ERPNext grants them.
- Each source is independently checked for DocType existence and native `read` permission.
- Recent records are loaded through permission-aware `frappe.get_list`.
- No `ignore_permissions`, manual commit, asset ledger, depreciation calculation, Journal Entry creation, GL Entry write, Stock Ledger Entry write or submitted-document mutation is introduced.
- Branch-specific asset ownership is not fabricated; Company/Location/Cost Center semantics remain native ERPNext concepts.

## Files

- `retailedge/native_visual_workspaces.py`
- `retailedge/edgesuite_ui.py`
- `retailedge/retailedge/page/assets_control/assets_control.js`
- `retailedge/retailedge/page/assets_control/assets_control.json`
- `retailedge/retailedge/page/assets_control/assets_control.py`
- `retailedge/tests/test_fixed_assets_navigation_contract.py`

## Validation required

- focused Assets navigation/UI/safety contract;
- Theme compatibility;
- Linters, pre-commit, Semgrep and vulnerable dependency audit;
- clean Frappe v16 install/build/full RetailEdge tests;
- governed EdgeSuite UI candidate clean build/migrate/full RetailEdge tests.

## Manual QA

Deferred to the consolidated RetailEdge QA branch. Validate permission-filtered Asset/Category visibility, recent-record rendering, create/list/form native handoffs, responsive/dark-mode presentation and absence of Asset data for users without native read permission.
