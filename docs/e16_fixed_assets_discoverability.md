# E16 C13A — Fixed Assets Discoverability

## Goal

Expose ERPNext's native fixed-asset capability through RetailEdge without creating a parallel asset register, depreciation engine, maintenance workflow, disposal workflow or accounting model.

## Audit Result

ERPNext v16 already provides the required fixed-asset source of truth:

- `Asset` is a submittable native DocType linked to Item, Company, Asset Category, Location, Purchase Receipt/Purchase Invoice, accounting dimensions and depreciation schedules.
- The native Asset form owns Asset Value Adjustment, Asset Repair, Depreciation Entry, Asset Maintenance, Split Asset, Asset Transfer, Scrap Asset, Sell Asset/restore and General Ledger drill-through.
- `Asset Category` owns finance-book, depreciation and account configuration.
- Native permissions include Accounts and Quality roles as defined by ERPNext. RetailEdge must not narrow these through a hard-coded product-role gate.

The RetailEdge gap is discoverability, not asset accounting or lifecycle implementation.

## Scope

Add one standalone `Assets` navigation group to the EdgeSuite Business Hub registry with two native DocType destinations:

1. `Fixed Assets` → ERPNext `Asset`
2. `Asset Categories` → ERPNext `Asset Category`

The group must not define a hard-coded `required_roles` list. Existing `_can_open_target` / `_has_permission_cached(..., "read", ...)` logic must determine whether each destination is visible to the current user.

If the caller can read only one destination, show only that destination. If neither destination is readable, the group naturally disappears through the existing empty-group behaviour.

## Out of Scope

- RetailEdge Asset DocType or asset ledger.
- Asset creation wizard.
- Custom depreciation calculations or schedules.
- Asset Movement, Repair, Maintenance, Value Adjustment, Capitalization, Sale, Scrap or Restore wrappers.
- Direct Journal Entry or GL Entry creation.
- Auto-submit of Asset or related accounting documents.
- New role grants or permission overrides.
- Branch-specific asset ownership semantics not present in ERPNext.

## Safety Rules

- ERPNext remains asset and accounting source of truth.
- Do not mutate submitted Asset, Purchase Invoice, Purchase Receipt, Journal Entry or GL Entry documents.
- Do not use `ignore_permissions`.
- Do not add manual database commits.
- Do not create a parallel asset status or depreciation calculation.
- Do not hard-code Accounts-only navigation because ERPNext also grants Asset access to Quality Manager in v16.
- Native ERPNext forms remain authoritative completion surfaces.

## Files to Inspect

- `retailedge/edgesuite_ui.py`
- `retailedge/tests/`
- ERPNext v16:
  - `erpnext/assets/doctype/asset/asset.json`
  - `erpnext/assets/doctype/asset/asset.js`
  - `erpnext/assets/doctype/asset_category/asset_category.json`

## Tests Required

Source-contract coverage must verify:

- exactly one `Assets` navigation group exists;
- `Fixed Assets` targets native `Asset`;
- `Asset Categories` targets native `Asset Category`;
- the Assets group has no hard-coded `required_roles` gate;
- DocType destinations continue through the existing read-permission resolver;
- no RetailEdge asset posting/depreciation/repair/sale/scrap wrapper or permission bypass is added to the navigation backend.

## Expected Deliverable

A small permission-aware native navigation handoff only. No new operational page, API, scheduler, accounting service or DocType.

## Manual QA

Deferred to the consolidated RetailEdge QA branch. At that stage verify visibility for permitted Accounts/Quality roles and absence for users without native Asset permissions.