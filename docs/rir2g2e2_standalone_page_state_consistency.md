# RIR2G2E2 — Standalone Page State Consistency

## Goal

Reconcile the remaining ordinary standalone RetailEdge pages whose primary loading, failure and instructional-empty states are still locally implemented instead of following the shared EdgeSuite state contract.

## Scope

This slice is limited to:

1. Customer 360.
2. Project Operations.
3. Forecasting & Planning.

These pages are ordinary EdgeSuite operational/intelligence surfaces and do not currently delegate primary page state handling to `EdgeReportShell` or `EdgeDashboardShell`.

## Audit classification

### Customer 360

Current primary state behavior uses local alert/loading blocks. It has no standard retry affordance for failed metadata/data loads and presents no explicit instructional state before a Customer is selected.

Required correction:

- use `EdgeLoadingState` for primary data loading;
- use `EdgeErrorState` with a retry path that targets the failed owner;
- use `EdgeEmptyState` to guide selection when no Customer is selected;
- keep table-local no-activity rows as contextual table content;
- preserve Company → Branch → Customer cascade behavior.

### Project Operations

Current navigation and project-context failures share one local `error` field even though they have different retry owners. Primary loading is a local text block and no-project selection has no shared instructional state.

Required correction:

- separate navigation/bootstrap failure from project-context load failure;
- use shared error states with retry actions that call the correct existing loader;
- use shared loading state for project-context loading;
- use shared instructional empty state when no Project is selected;
- keep section-local no-task/no-budget/no-timeline/no-payment messages as contextual section content;
- do not change project accounting, task, budget, payment or native-lifecycle ownership.

### Forecasting & Planning

The top-level error block is independent of the loading/content `v-if/v-else` chain. A failed request can therefore show an error while normal planning content still renders underneath it.

Required correction:

- make primary error/loading/content states mutually exclusive;
- distinguish metadata/bootstrap failure from data-refresh failure sufficiently to retry the correct owner;
- use shared loading and error components;
- use shared instructional empty state when Company is not selected;
- standardize scenario-performance loading/failure/no-results presentation without changing forecast calculations;
- preserve domain-specific unavailability/reason messages inside their own panels.

## Explicit non-blockers / out of scope

The following are not changed in this slice:

- Native ERPNext Workspace: it already has explicit loading, failure, retry and empty semantics; visual replacement alone is not a blocker.
- EdgeReportShell and EdgeDashboardShell consumers: primary state ownership already exists in the shared shells.
- table-local and panel-local domain empty messages that explain valid zero-data conditions.
- modal/dialog/action feedback.
- Native Desk capability or route containment.
- date formatting.
- Link-field query/cascade hardening beyond preserving current behavior.
- business calculations, accounting, stock, workflow, permissions, schemas or backend APIs.

## Safety rules

- No ERPNext accounting or stock semantics change.
- No submitted-document mutation.
- No permission or Branch-scope broadening.
- No `ignore_permissions`.
- No manual database commits.
- No shared EdgeSuite UI runtime changes.
- Do not reopen frozen G2A–G2E1 contracts.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests required

- all three pages require the shared loading/error/empty components;
- Customer 360 metadata/data failures have retryable primary error states;
- Customer 360 no-Customer state is explicit;
- Project Operations separates navigation and context failures and retries the correct owner;
- Project Operations no-Project state is explicit;
- Forecasting primary error/loading/content rendering is mutually exclusive;
- Forecasting metadata and data failures retain distinct retry authority;
- scenario-performance state handling is explicit and does not alter calculations;
- existing cascade, permission, routing, accounting and state contracts remain green.

## Freeze rule

Freeze G2E2 only when one exact authoritative head passes:

1. RetailEdge Theme Compatibility;
2. Linters / Semgrep / vulnerable dependency audit;
3. clean Frappe v16 CI;
4. EdgeSuite UI Candidate Compatibility.
