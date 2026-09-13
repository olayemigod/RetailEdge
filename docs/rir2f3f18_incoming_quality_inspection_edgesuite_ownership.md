# RIR2 F3F18 — Incoming Quality Inspection EdgeSuite Ownership

## Goal
Close the ordinary-user Native Desk dependency in Professional Purchasing Incoming Quality Inspection without replacing ERPNext quality-control truth.

## Existing gap
The current EdgeSuite panel identifies eligible draft Purchase Receipt rows and then calls ERPNext `make_quality_inspections`, which immediately persists draft Quality Inspection documents. Users must then enter readings, review acceptance and submit those drafts in native ERPNext Desk. In EdgeSuite-only mode this leaves an incomplete operational path and can create drafts before the user has a permitted completion surface.

## Ownership contract
For the standard EdgeSuite path:

1. The selected Purchase Receipt must remain a saved, non-return draft inside the current company/branch scope.
2. ERPNext `check_item_quality_inspection` remains authoritative for which receipt rows require inspection.
3. Preview must be persistence-free. RetailEdge may construct an unsaved ERPNext Quality Inspection document in memory and load the current Item Quality Inspection Template, but preview must not call `save`, `insert`, `submit`, `frappe.db.commit`, or write the Purchase Receipt row.
4. The browser may submit only:
   - Purchase Receipt child-row reference;
   - sample size;
   - reading values for the current ERPNext template.
5. The browser must not be allowed to override item, supplier, company, branch, template, specification, min/max criteria, expected value, formula, inspection type, source document, status, or document lifecycle fields.
6. Standard submission must:
   - require Quality Inspection create and submit permission;
   - lock the source Purchase Receipt;
   - reject a stale preview when the source `modified` value changed;
   - rebuild eligibility and template criteria from ERPNext under the lock;
   - apply only validated reading values to the rebuilt unsaved Quality Inspection;
   - call normal ERPNext `insert()` and `submit()` as the current user;
   - never write GL Entry or Stock Ledger Entry directly.
7. ERPNext Quality Inspection validation remains authoritative for numeric/value/formula criteria and final Accepted/Rejected status.
8. Missing templates, missing specification rows, manual/unsupported inspection modes, stale sources, changed eligibility, or malformed reading payloads must fail closed. They must not be auto-accepted or approximated by RetailEdge.
9. Native draft creation may remain only as an explicit advanced compatibility fallback for users who are not in EdgeSuite-only mode. It must not be the ordinary completion path.
10. Direct Purchase Receipt / Quality Inspection Native Desk routes must not be exposed to EdgeSuite-only users from this surface.

## Scope
- `retailedge/incoming_quality_inspection.py`
- `retailedge/public/js/professional_purchasing/IncomingQualityInspection.vue`
- focused contract/regression tests
- Godmode ledger after all governed gates pass

## Out of scope
- changing ERPNext Quality Inspection DocTypes or templates;
- automatically submitting the Purchase Receipt;
- changing Stock Settings quality-inspection policy;
- direct stock or accounting posting;
- redesigning branch architecture or permissions;
- Landed Cost ownership.

## Required tests
- preview performs no persistence;
- source and branch permission checks remain enforced;
- preview exposes current ERPNext criteria but not writable authoritative fields;
- tampered criteria/status/source fields are rejected;
- stale Purchase Receipt preview is rejected under lock;
- changed row eligibility is rejected;
- standard submit rebuilds the Quality Inspection and uses `insert()` + `submit()` only;
- ERPNext-produced Accepted/Rejected status is returned rather than recomputed by RetailEdge;
- missing/unsupported template cases fail closed to advanced handling;
- EdgeSuite-only UI contains no direct native form completion route;
- legacy draft-first helper remains available only as explicit advanced compatibility.

## Freeze rule
F3F18 may become **CODE-FROZEN / QA-PENDING** only when Theme Compatibility, Linters/Semgrep, EdgeSuite UI Candidate Compatibility, and clean Frappe v16 CI all pass on the same exact head. Browser/persona QA remains separately required for full FROZEN state.
