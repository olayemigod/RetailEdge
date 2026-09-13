# RIR2G2E1 — Payment Management State Consistency

## Goal

Bring the core Payment Management page into the shared EdgeSuite loading/error/empty-state contract without changing payment, reconciliation, workflow, accounting or permission semantics.

## Context

The governed EdgeSuite UI runtime already provides:

- `EdgeLoadingState` with status/live-region semantics;
- `EdgeErrorState` with alert and retry semantics;
- `EdgeEmptyState` for intentional no-data states.

Most RetailEdge core operational pages already use these components directly or inherit them through EdgeReportShell / EdgeDashboardShell.

Payment Management remains a core ordinary-user outlier. Its main lists currently use local text blocks for loading/error/empty states, and settlement uses one error field for both load failure and action/validation feedback.

## Scope

Only `retailedge/public/js/payment_management/PaymentManagement.vue` state presentation is changed.

### Page metadata

- metadata-load failure becomes a shared `EdgeErrorState`;
- successful retry continues through the existing `loadMetadata()` path;
- operational panels are not presented as healthy while metadata is unavailable.

### Draft Payments Awaiting Submission

- load failure uses `EdgeErrorState` with refresh/retry;
- initial loading uses `EdgeLoadingState`;
- zero eligible drafts uses `EdgeEmptyState`;
- "choose Company and Customer" remains instructional state, not an empty/error state;
- review/workflow/submit action errors remain local action feedback and do not masquerade as list-load failure.

### Mixed Customer Settlement

- settlement-context load failure is separated from action/validation feedback;
- load failure uses `EdgeErrorState` and retries the existing invoice-context loader;
- loading uses `EdgeLoadingState`;
- no eligible advances uses `EdgeEmptyState`;
- allocation validation, reconciliation failure, payment-mode lookup failure and receipt-draft failure remain local action feedback.

### Customer Advances

- load failure uses `EdgeErrorState`;
- loading uses `EdgeLoadingState`;
- zero advances uses `EdgeEmptyState`.

## Safety Rules

Do not change:

- Payment Entry creation/submission authority;
- ERPNext Payment Reconciliation;
- Sales Invoice outstanding truth;
- advance allocation identity or amounts;
- workflow actions or workflow precedence;
- Company/Branch/Customer filtering;
- permissions or Native Desk capability;
- backend APIs;
- accounting/Payment Ledger/GL semantics;
- document lifecycle;
- sorting behavior frozen in G2C1.

No backend, schema, `ignore_permissions`, transaction or shared EdgeSuite UI change is in scope.

## Tests Required

- Payment Management requires the three shared state components.
- Metadata, draft-list, settlement-load and customer-advance load failures use shared error states.
- Primary loading paths use shared loading states.
- Primary no-data paths use shared empty states.
- settlement load error and settlement action error remain distinct.
- draft load error and draft action/review error remain distinct.
- existing native fallback and payment ownership contracts remain green.

## Out of Scope

- Customer 360, Project Operations, Native ERPNext Workspace and planning/intelligence state cleanup;
- action-success toast redesign;
- modal/dialog state redesign;
- loading/error/empty changes to report/dashboard shells;
- browser/persona QA.

## Freeze Rule

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI, and EdgeSuite UI Candidate Compatibility all pass on one exact head.
