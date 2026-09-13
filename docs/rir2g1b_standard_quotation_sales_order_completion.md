# RIR2G1B — Standard Quotation and Sales Order Completion

## Goal

Allow ordinary EdgeSuite Professional Selling users to complete the standard Quote → Order commitment path without an unintended Native Desk escape, while keeping ERPNext/Frappe authoritative for validation, submission and Workflow.

This checkpoint deliberately excludes Delivery Note stock posting and Sales Invoice accounting submission. Those are higher-risk completion boundaries and remain separate RIR2G1 checkpoints.

## Confirmed Gap

Professional Selling currently owns guided creation and recent read for:

- Quotation;
- Sales Order;
- Delivery Note;
- Sales Invoice.

Quotation and Sales Order creation are explicitly draft-only. Professional Selling has no standard submit or Frappe Workflow action for those drafts.

This creates an operational dead end for EdgeSuite-only users:

1. a Quotation can be created but not submitted;
2. ERPNext requires a submitted Quotation before native mapping to a Sales Order;
3. a Sales Order can be created but not submitted;
4. ERPNext requires a submitted Sales Order before native mapping to a Delivery Note.

## Standard Completion Scope

Supported in this checkpoint:

- Customer Quotation;
- standard Sales Order;
- draft documents only for initial completion;
- current user's normal ERPNext read/submit permissions;
- authoritative Company/Branch operating scope;
- active Frappe Workflow when configured;
- no-Workflow ERPNext native `doc.submit()`;
- stale-document protection using the reviewed `modified` timestamp.

## Advanced / Fail-Closed Scope

The following remain Advanced ERPNext:

- non-Customer Quotation;
- amended Quotation or Sales Order;
- inter-company/internal-customer Sales Order;
- non-standard Sales Order type;
- cancelled/closed/on-hold or otherwise incompatible draft state;
- documents without valid Company/Branch attribution for a restricted user;
- unsupported document types;
- any case whose standard-shape validation fails.

The checkpoint must not silently normalize an advanced document into a standard one.

## Backend Contract

Add one bounded selling-completion service for exactly:

- `Quotation`;
- `Sales Order`.

The service must expose:

1. persistence-free completion preview;
2. direct standard submit for sites without an active Frappe Workflow;
3. scoped workflow-action execution for sites with an active Frappe Workflow.

### Preview

Preview must:

- require readable named document;
- validate supported DocType;
- validate Company and operational Branch scope;
- re-read current ERPNext document truth;
- report `modified`, `docstatus`, party, total, currency and bounded item summary;
- read shared `get_workflow_readiness()`;
- expose blockers;
- expose `can_submit`;
- expose `workflow_eligible`;
- expose only actions returned by Frappe workflow readiness;
- make no writes.

### Direct submit

Direct submit must:

- be POST-only;
- lock the exact document row `FOR UPDATE`;
- re-read the exact document;
- revalidate Company/Branch, standard shape and items;
- require exact reviewed `modified`;
- fail if an active Frappe Workflow owns progression;
- require normal document submit permission;
- call native ERPNext `doc.submit()`;
- verify ERPNext returned submitted `docstatus == 1`;
- never mutate workflow state/docstatus directly.

### Workflow action

Workflow action must:

- be POST-only;
- lock/re-read/revalidate the exact document;
- require exact reviewed `modified`;
- require the document to remain standard-shape eligible;
- require active Frappe Workflow;
- delegate to the shared F3F27 `apply_document_workflow_action()`;
- pass expected workflow state from preview;
- never invent a RetailEdge fallback workflow.

## Branch / Company Contract

For the stored document:

- Company is mandatory and readable;
- the document's stored Branch is used where the DocType supports Branch attribution;
- restricted users must have a stored valid Branch on the document;
- explicit Branch is revalidated through `resolve_operational_branch()`;
- restricted-zero must fail closed;
- unrestricted documents may retain blank Branch compatibility;
- no frontend filter is treated as authorization.

No document Branch is silently rewritten during completion.

## UI Contract

Professional Selling must provide a standard completion surface for Quotation and Sales Order:

- immediately after a new draft is created;
- from a permitted recent draft row.

The completion surface must:

- stay inside Professional Selling;
- show review summary and blockers;
- show **Submit** only when no Workflow owns the document and preview says `can_submit`;
- show only returned Frappe Workflow actions when `workflow_eligible`;
- refresh after transition/submit;
- close or show submitted state when `docstatus == 1`;
- never assign `workflow_state` or `docstatus` in JavaScript;
- not expose this checkpoint's completion controls for Delivery Note or Sales Invoice.

Native Desk-capable users retain the existing explicit Advanced ERPNext action.

## ERPNext Truth

ERPNext remains authoritative for:

- Quotation submission;
- Sales Order submission;
- pricing/taxes;
- item validation;
- sales commitment/status updates;
- linked quotation ordered quantities/status;
- Workflow transitions;
- permissions and validation hooks.

RetailEdge must not:

- update submitted sources directly;
- write GL/SLE;
- use `ignore_permissions`;
- manually commit;
- set `docstatus` directly;
- set workflow state directly.

## Tests Required

Backend:

1. only Quotation/Sales Order are supported;
2. Customer Quotation standard shape accepted;
3. non-Customer/amended Quotation fails closed;
4. standard Sales Order accepted;
5. internal/inter-company/non-standard-order Sales Order fails closed;
6. restricted stored Branch is revalidated with operational Branch authority;
7. restricted missing Branch fails closed;
8. unrestricted blank Branch remains compatible;
9. preview is persistence-free;
10. active Workflow blocks direct submit before submit permission;
11. workflow eligibility requires no non-workflow blocker;
12. direct submit row-locks, stale-checks, revalidates, then calls `doc.submit()`;
13. workflow action row-locks, stale-checks, revalidates and delegates to F3F27;
14. no `ignore_permissions`, manual commit, direct workflow/docstatus assignment, GL or SLE creation.

UI:

15. Quotation/Sales Order saved result opens or offers completion review;
16. recent draft Quotation/Sales Order exposes completion review;
17. Delivery Note/Sales Invoice do not receive Checkpoint-B completion controls;
18. Submit button hidden when active Workflow owns progression;
19. workflow buttons come only from returned `available_actions`;
20. UI never sets workflow state/docstatus;
21. successful completion refreshes Professional Selling and recent rows.

Regression:

22. existing draft creation/conversion remains unchanged;
23. existing F3F27 tests remain green;
24. active Company/Branch and EdgeSuite-only guards remain green.

## Out of Scope

- Delivery Note submit;
- Sales Invoice submit;
- Sales Return / Credit Note completion;
- Stock Entry / Stock Reconciliation submit;
- POS lifecycle;
- accounting or stock-ledger semantics;
- reporting;
- Business Hub redesign;
- manual browser/persona acceptance;
- schema/migration work.

## Freeze Rule

RIR2G1B may freeze only when all four governed exact-head gates pass:

1. RetailEdge Theme Compatibility;
2. Linters / Semgrep / vulnerable dependency audit;
3. clean Frappe v16 CI;
4. governed EdgeSuite UI Candidate Compatibility.

RIR2G1 remains active after this checkpoint.
