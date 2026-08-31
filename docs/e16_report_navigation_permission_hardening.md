# E16 C15A — Report Navigation Permission Hardening

## Goal

Ensure EdgeSuite Business Hub never returns a Report navigation destination merely because the Report record exists. Report visibility must follow Frappe/ERPNext's own report-access rules before navigation metadata reaches the browser.

## Audit result

RetailEdge currently treats navigation targets differently in `retailedge/edgesuite_ui.py`:

- `DocType` targets require existence plus native `read` permission;
- `Page` and `Report` targets currently require only target existence.

That is too weak for Report metadata. Frappe v16's authoritative query-report gate is `frappe.desk.query_report.get_report_doc(report_name)`. It:

1. loads the Report;
2. enforces the Report's allowed-role/custom-role rules through `Report.is_permitted()`;
3. requires `report` permission on the Report's referenced DocType;
4. rejects disabled Reports.

RetailEdge should delegate to that native gate rather than reimplement Report role logic.

## Scope

For `target_type == "Report"` in the existing EdgeSuite navigation resolver:

- preserve the existing target-existence check;
- add a request-cached report-access check;
- delegate the actual permission decision to Frappe v16 `frappe.desk.query_report.get_report_doc`;
- return the navigation item only when that native gate succeeds;
- fail closed when the native gate rejects or cannot safely resolve the report.

Reuse the existing request-local permission cache passed through `get_retailedge_business_hub_context` so a Report target is checked at most once per context request.

## Out of scope

- no new Report links in C15A;
- no change to Report execution, filters, SQL, prepared-report behaviour or exports;
- no custom Report-role table or RetailEdge permission ledger;
- no `ignore_permissions`;
- no direct reads of `Has Role` or `Custom Role` to reproduce Frappe logic;
- no Page-permission redesign in this slice;
- no accounting, stock or business-document mutation;
- no browser-side permission assumptions.

## Safety rules

- Frappe remains the permission source of truth.
- The helper must be read-only and fail closed.
- Do not broaden any user's access.
- Preserve existing DocType permission behaviour and URL/Page behaviour.
- Keep request-local caching; do not introduce persistent permission caches that can outlive role changes.
- Do not leak the reason a hidden report was denied in navigation metadata.
- Preserve multi-app coexistence and existing navigation order.

## Tests required

Focused tests must prove:

- Report navigation delegates to Frappe `get_report_doc` rather than duplicating role logic;
- a permitted Report is returned;
- a denied/disabled/erroring Report is hidden without raising through Business Hub metadata;
- missing Report targets are rejected before the native permission call;
- repeated checks for the same Report in one request reuse the request-local cache;
- DocType navigation still uses native `read` permission;
- Page navigation behaviour is unchanged;
- no `ignore_permissions`, direct `Has Role` query, custom role reconstruction or write path is introduced.

## Expected delivery boundary

C15A is complete when the generic Report navigation path is permission-aware through Frappe's native report gate, focused tests pass, cumulative diff is bounded, and exact-head Theme/Linters/clean Frappe v16 CI/EdgeSuite candidate validation is green.
