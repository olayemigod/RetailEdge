# E16 C24 — Warranty & After-sales Service Discoverability

## Goal

Expose ERPNext v16's native warranty and maintenance capability through the RetailEdge EdgeSuite Business Hub without creating a parallel warranty register, claim workflow, maintenance scheduler or service ledger.

## Audit Result

ERPNext v16 already provides the authoritative after-sales lifecycle:

- `Warranty Claim` owns customer, serial number, item, complaint, warranty/AMC status and expiry, resolution status and resolution details.
- The native Warranty Claim form validates the customer and serial context, controls resolution dates, and provides ERPNext's mapped `Maintenance Visit` action for open or work-in-progress claims.
- `Maintenance Schedule` is a native submittable document. It owns customer/item service periods, scheduled dates and visit generation.
- `Maintenance Visit` is a native submittable document. It owns scheduled/unscheduled/breakdown visits, purposes, completion status and customer feedback.
- ERPNext permissions differ by document: Warranty Claim and Maintenance Visit are available to `Maintenance User`; Maintenance Schedule is available to `Maintenance Manager`. RetailEdge must therefore use native per-DocType permissions rather than a hard-coded product-role gate.

The RetailEdge gap is safe discovery and entry, not warranty or maintenance lifecycle implementation.

## Scope

Add one standalone `Service & Warranty` navigation group to the EdgeSuite Business Hub registry with three native DocType destinations:

1. `Warranty Claims` → ERPNext `Warranty Claim`
2. `Maintenance Schedules` → ERPNext `Maintenance Schedule`
3. `Maintenance Visits` → ERPNext `Maintenance Visit`

The group must not define a hard-coded `required_roles` list. Existing `_can_open_target` / `_has_permission_cached(..., "read", ...)` logic must determine whether each destination is visible.

If a user can read only some destinations, show only those destinations. If none are readable, the existing empty-group behavior must omit the group.

Add one `New Warranty Claim` quick action targeting native `Warranty Claim`. Existing quick-action resolution must require both DocType existence and native `create` permission before exposing it. The action opens ERPNext's normal unsaved form; RetailEdge does not insert or save a claim server-side.

## Company and Branch Semantics

These native documents carry ERPNext Company/customer/serial context but do not provide a RetailEdge Branch ownership model. This slice must not fabricate Branch-level filtering or aggregate claim data. ERPNext user permissions, link-field permissions and native document validation remain authoritative.

## Out of Scope

- RetailEdge Warranty Claim, Maintenance Schedule, Maintenance Visit or service ledger DocTypes.
- Custom claim list/report, dashboard, SLA engine or status store.
- Automatic claim creation from Sales Invoice, Delivery Note, Serial No or POS.
- Custom warranty eligibility, expiry, AMC or serial-number calculations.
- Custom claim-to-visit mapping.
- RetailEdge schedule generation, submission, cancellation, closing or resolution endpoints.
- Direct Event creation or maintenance notification scheduling.
- Mutation of submitted warranty, maintenance, sales, delivery, stock or accounting documents.
- New role grants, permission overrides or fabricated Branch ownership semantics.
- Migration, schema patch or data backfill.

## Safety Rules

- ERPNext remains warranty, serial and maintenance source of truth.
- Native forms remain the authoritative completion and validation surfaces.
- The quick action may only navigate to an unsaved native Warranty Claim form.
- Do not call ERPNext's Warranty Claim → Maintenance Visit mapper from RetailEdge.
- Do not generate Maintenance Schedule rows or Events from RetailEdge.
- Do not insert, save, submit, cancel or close any native service document server-side.
- Do not use `ignore_permissions`.
- Do not add manual database commits.
- Do not create stock, GL, SLE, Sales Invoice, Delivery Note or accounting writes.

## Files to Inspect

- `retailedge/edgesuite_ui.py`
- `retailedge/tests/`
- ERPNext v16:
  - `erpnext/support/doctype/warranty_claim/warranty_claim.json`
  - `erpnext/support/doctype/warranty_claim/warranty_claim.py`
  - `erpnext/support/doctype/warranty_claim/warranty_claim.js`
  - `erpnext/maintenance/doctype/maintenance_schedule/maintenance_schedule.json`
  - `erpnext/maintenance/doctype/maintenance_schedule/maintenance_schedule.py`
  - `erpnext/maintenance/doctype/maintenance_visit/maintenance_visit.json`
  - `erpnext/maintenance/doctype/maintenance_visit/maintenance_visit.py`

## Tests Required

Source-contract coverage must verify:

- exactly one `Service & Warranty` navigation group exists;
- the three destinations target their native ERPNext DocTypes;
- the group has no hard-coded `required_roles` gate;
- each destination continues through the existing native read-permission resolver;
- exactly one `New Warranty Claim` quick action targets native `Warranty Claim`;
- quick actions remain gated by DocType existence and native create permission;
- no RetailEdge claim mapper, schedule generator, service-document write, permission bypass or manual commit is added.

## Expected Deliverable

A small permission-aware native navigation and unsaved-entry handoff only. No new operational Page, API, scheduler, DocType, schema or migration.

## Manual QA

Deferred to the consolidated RetailEdge QA branch. Verify:

- a permitted Maintenance User sees Warranty Claims and Maintenance Visits;
- a permitted Maintenance Manager sees Maintenance Schedules;
- users without native read permission do not see the corresponding destinations;
- users without native Warranty Claim create permission do not see the quick action;
- the quick action opens an unsaved native Warranty Claim form;
- native Warranty Claim → Maintenance Visit behavior remains unchanged.
