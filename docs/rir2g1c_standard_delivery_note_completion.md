# RIR2G1C — Standard Delivery Note Completion

## Goal

Remove the ordinary EdgeSuite dead end after a standard Delivery Note draft is created from a submitted Sales Order, while preserving ERPNext as the sole authority for stock posting, valuation and Delivery Note lifecycle truth.

RIR2G1C is a separate stock-submission checkpoint. It must not be combined with Sales Invoice accounting submission.

## Business Boundary

Supported standard path:

submitted Sales Order → ERPNext native mapped Delivery Note draft → EdgeSuite completion review → Frappe Workflow action or ERPNext native submit.

The draft must remain the exact ERPNext Delivery Note produced by the existing Professional Selling mapper. RetailEdge does not rebuild delivery quantities, packed items, stock rows, taxes or valuation.

## Standard Eligibility

A Delivery Note may use RIR2G1C only when all of the following are true:

- it is a draft Delivery Note;
- it is not a return and has no `return_against`;
- it is not amended;
- it belongs to a readable Company and current operational Branch scope;
- it has a Customer;
- it has at least one item;
- every item belongs to exactly one submitted Sales Order through `against_sales_order`;
- that source Sales Order is readable, submitted and belongs to the same Company, Customer and Branch;
- every delivery item has a Warehouse;
- every Warehouse is readable, belongs to the same Company and resolves to one permitted operational Branch;
- the resolved warehouse Branch matches the Delivery Note/source Branch when either is attributed;
- no packed-item rows are present;
- no delivery item contains Serial No, Batch No or Serial and Batch Bundle state;
- the document is not internal/inter-company delivery.

Anything outside that shape is **Advanced ERPNext**, not a standard EdgeSuite completion case.

## Preview

The completion preview must be persistence-free and expose:

- Delivery Note identity and immutable `modified` snapshot;
- Company, Branch, Customer and source Sales Order;
- item summary and total;
- standard-shape blockers;
- Frappe Workflow readiness;
- whether direct native submit is currently allowed.

Preview must not save, insert, submit, mutate workflow state, create Stock Ledger rows or alter the submitted Sales Order.

## No Active Workflow

Direct submit is permitted only when:

1. the exact Delivery Note is row-locked;
2. the reviewed `modified` snapshot still matches;
3. read/submit permission is valid;
4. Company/Branch/source Sales Order/Warehouse context is revalidated;
5. standard-shape blockers are empty;
6. no active Frappe Workflow owns the document.

RetailEdge then calls only native `doc.submit()`.

ERPNext owns:

- Delivery Note validation;
- stock ledger posting;
- valuation consequences;
- Sales Order delivered quantities/status;
- stock and document status truth.

RetailEdge must not reproduce these effects.

## Active Frappe Workflow

If an active Workflow exists:

- direct submit fails closed before submit permission is used as an alternate path;
- only `available_actions` returned by Frappe are rendered;
- workflow action execution uses the shared F3F27 `apply_document_workflow_action` bridge;
- the exact immutable snapshot and expected workflow state are supplied;
- EdgeSuite never assigns `workflow_state` or `docstatus`.

## UI Ownership

Professional Selling must:

- open Delivery completion review immediately after a standard Delivery draft is created;
- expose Review Completion on permitted recent draft Delivery Notes;
- keep the G1B Quotation/Sales Order completion path unchanged;
- not expose Sales Invoice completion from this checkpoint;
- show Advanced ERPNext only when Native Desk capability exists.

## Scope

Runtime:

- `retailedge/standard_delivery_completion.py`
- `retailedge/public/js/professional_selling/StandardDeliveryCompletionDialog.vue`
- `retailedge/public/js/professional_selling/ProfessionalSelling.vue`

Reused authorities:

- `retailedge/professional_delivery.py`
- `retailedge/professional_selling.py`
- `retailedge/workflow_readiness.py`
- `retailedge/workflow_actions.py`

Tests/documentation:

- focused RIR2G1C contract/regression tests;
- Godmode state update only after exact-head freeze.

## Out of Scope

- Sales Invoice submit/accounting completion;
- Sales Return / Credit Note;
- Delivery Note return;
- Serial/Batch or Serial and Batch Bundle handling;
- Product Bundle / packed-item completion;
- multiple Sales Orders in one Delivery Note;
- internal/inter-company delivery;
- cancellation/amendment;
- custom stock-posting engine;
- Stock Entry or Stock Reconciliation;
- direct Stock Ledger or valuation writes;
- schema/migration work;
- manual browser/persona acceptance.

## Tests Required

Backend:

1. completion service is Delivery Note-only;
2. preview is persistence-free;
3. only draft standard Delivery Note is eligible;
4. return/amended/internal/inter-company delivery fails closed;
5. exactly one source submitted Sales Order is required;
6. source Sales Order Company, Customer and Branch must match;
7. restricted stored Branch is revalidated operationally;
8. restricted missing Branch fails closed;
9. every item Warehouse is readable and Company-valid;
10. all warehouse Branches collapse to one permitted operational Branch;
11. packed items fail closed;
12. Serial/Batch/Serial-and-Batch-Bundle state fails closed;
13. active Workflow blocks direct submit;
14. direct submit row-locks, stale-checks, revalidates, checks submit permission and then calls only `doc.submit()`;
15. workflow action row-locks, stale-checks, revalidates and delegates to F3F27;
16. no direct GL/SLE creation, valuation write, `ignore_permissions`, manual commit, docstatus/workflow assignment or submitted-source mutation.

UI:

17. saved Delivery Note opens Delivery completion review;
18. recent draft Delivery Note exposes Review Completion;
19. G1B Quotation/Sales Order completion remains unchanged;
20. Sales Invoice receives no G1C completion control;
21. Submit is hidden when active Workflow owns progression;
22. workflow buttons come only from server `available_actions`;
23. successful completion refreshes workspace/recent rows;
24. Advanced ERPNext remains Native-Desk-capability-gated.

Regression:

25. Delivery draft creation still uses ERPNext native Sales Order mapper and remains draft-only;
26. G1B tests remain green;
27. Branch-cascade and operating-scope tests remain green.

## Safety Rules

- no direct `Stock Ledger Entry` creation;
- no direct valuation mutation;
- no submitted Sales Order mutation;
- no `ignore_permissions`;
- no manual DB commit;
- no direct `docstatus` or workflow-state assignment;
- no schema migration.

## Freeze Rule

RIR2G1C may freeze only when all four governed exact-head gates pass on one SHA:

1. RetailEdge Theme Compatibility;
2. Linters / Semgrep / vulnerable dependency audit;
3. clean Frappe v16 CI;
4. EdgeSuite UI Candidate Compatibility.

After RIR2G1C freeze, RIR2G1 continues to the separate Sales Invoice accounting-submission boundary unless repository evidence identifies a higher-priority core-journey blocker.
