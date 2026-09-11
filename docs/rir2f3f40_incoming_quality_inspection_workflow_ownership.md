# RIR2F3F40 — Incoming Quality Inspection EdgeSuite Ownership Hardening

## Goal

Close the remaining workflow/idempotency gap in the existing F3F18 Incoming Quality Inspection EdgeSuite owner without replacing ERPNext quality-control truth.

## Context

F3F18 already provides a persistence-free review for standard incoming inspections and can directly insert + submit ERPNext Quality Inspections when no active Quality Inspection Workflow exists. The remaining gap is active Frappe Workflow: direct submission must not bypass it, and an approval path must not create duplicate drafts on retry.

## Frozen Contract

- ERPNext `Quality Inspection` remains the only inspection document and acceptance/rejection authority.
- Active Frappe Workflow on `Quality Inspection` is authoritative.
- The existing Purchase Receipt review remains persistence-free.
- Sites without an active Quality Inspection Workflow preserve the existing F3F18 standard `insert() + submit()` path.
- When an active Quality Inspection Workflow exists, EdgeSuite must not call direct `submit()` from the review.
- Instead EdgeSuite exposes **Start Inspection Approval** for standard-eligible reviewed rows.
- Start Approval must:
  1. lock and re-read the exact draft Purchase Receipt;
  2. revalidate read/create permissions, Company/Branch scope and current inspection eligibility;
  3. reject stale source snapshots;
  4. rebuild the Quality Inspection from current ERPNext Item/template truth;
  5. reapply only the reviewed reading input values;
  6. inspect existing draft Quality Inspections linked by exact Purchase Receipt + child row;
  7. reuse exactly one readable draft only when it still matches the current standard mapping and reviewed readings;
  8. fail closed on multiple, unreadable or non-standard linked drafts;
  9. otherwise insert exactly one draft under normal permissions;
  10. return authoritative Frappe Workflow readiness for each saved draft.
- A saved standard inspection must remain an Incoming Quality Inspection for the same Purchase Receipt row, Company, Item, batch/serial identity, sample size, template and specification shape.
- Saved-draft workflow actions must:
  - lock and re-read the source Purchase Receipt and exact Quality Inspection;
  - verify read permission and Branch/Company scope;
  - verify exact source/child-row linkage and standard inspection equivalence;
  - reject stale source and Quality Inspection snapshots;
  - require current active Frappe Workflow and expected workflow state;
  - delegate to `retailedge.workflow_actions.apply_document_workflow_action`.
- Frappe `apply_workflow()` remains authoritative for role, condition, self-approval, update-field, workflow-state, docstatus and submit behavior.
- If a workflow transition submits the Quality Inspection, ERPNext alone computes final Accepted/Rejected status and updates the source inspection reference.
- EdgeSuite never assigns workflow state, inspection status or docstatus directly.
- No RetailEdge fallback workflow is invented for Quality Inspection.
- Existing **Advanced: Prepare in ERPNext** remains available only to Native-Desk-capable users and remains outside the standard workflow path.

## Safety Rules

- No `ignore_permissions`.
- No manual database commit.
- No direct GL Entry or Stock Ledger Entry write.
- No Purchase Receipt submit/cancel/mutation outside normal ERPNext Quality Inspection linkage.
- No Quality Inspection Template/Parameter mutation.
- No browser authority over Company, Branch, Item, Supplier, template criteria, status, lifecycle or source linkage.
- Restricted-zero Branch access must continue to fail closed.

## Out of Scope

- Landed Cost Voucher ownership.
- Partial/custom inspection redesign.
- Manual-inspection status support.
- Outgoing/In Process Quality Inspection.
- Purchase Invoice/Subcontracting/Stock Entry inspection ownership.
- Quality Inspection Template administration.
- Workflow configuration UI.
- Purchase Receipt submission.
- Reporting expansion.
- Manual browser/persona QA before consolidated RIR2E acceptance.

## Required Tests

- active Workflow blocks direct standard Quality Inspection submit;
- no-Workflow path still uses ERPNext insert + submit;
- workflow start is row-lock/stale protected and creates at most one standard draft per source child row;
- one valid readable draft is idempotently reused;
- multiple/unreadable/non-standard linked drafts fail closed;
- saved draft equivalence is rebuilt from ERPNext source/template truth;
- workflow action relocks/revalidates source + inspection and delegates through F3F27 with expected state;
- UI switches from Submit to Start Approval when Workflow owns the document;
- UI renders only returned workflow actions;
- transition refreshes inspection/source context;
- UI never assigns workflow state/docstatus/status directly;
- native fallback remains capability-gated.

## Freeze Rule

F3F40 may become **CODE-FROZEN / QA-PENDING** only after RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI, and EdgeSuite UI Candidate Compatibility all pass on the same exact head.
