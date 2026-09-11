# RIR2G2F1 — User-Date Presentation Consistency

## Goal

Remove raw ISO/server date presentation from ordinary RetailEdge EdgeSuite pages and render display-only dates through Frappe's user-date formatter.

This is a presentation reconciliation slice only. It does not change stored dates, API filters, posting dates, accounting periods, timezone semantics, report calculations or date-input values.

## Scope

Confirmed ordinary-user date-display outliers:

1. Customer 360.
2. Project Operations.
3. Forecasting & Planning.
4. Sales Forecast.
5. Customer Sales Intelligence.
6. Customer Opportunity Intelligence.
7. Inventory Insights.
8. Inventory Intelligence Centre.
9. Profitability Intelligence.

Nearby governed surfaces such as Payment Management, Professional Purchasing, Branch Assignments, Supplier Document Review and Action Center already format displayed dates through Frappe and are not rewritten.

## Required behavior

- Date-only values shown as text must use Frappe's user-date formatter.
- Missing dates continue to render a neutral dash or existing empty-state text.
- Datetime surfaces keep their existing datetime formatter; this slice does not coerce datetimes into dates.
- Native HTML `type="date"` inputs keep ISO `YYYY-MM-DD` values because that is the browser control contract.
- Backend payloads and API arguments remain unchanged.
- Export/filter payloads remain machine-readable and unchanged unless they are already presentation labels.
- Forecast month/period labels may format the visible date while preserving the underlying period key.
- No hard-coded `dd/mm/yyyy`, `mm/dd/yyyy` or locale-specific format is introduced. Frappe/user settings remain authoritative.

## Safety rules

- No ERPNext accounting, stock, valuation, workflow or posting semantics change.
- No date arithmetic or period boundary changes.
- No timezone conversion changes.
- No permission or Branch-scope changes.
- No backend API/schema changes.
- No submitted-document mutation.
- No `ignore_permissions`.
- No manual database commits.
- No shared EdgeSuite UI runtime changes.
- Do not reopen frozen G2A–G2E2 contracts.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests required

- each scoped component renders known date text through a local Frappe-backed date formatter;
- direct raw date interpolation is removed from the audited presentation locations;
- Customer 360 no longer returns raw date strings from its formatter;
- Project Operations timeline and cash rows use formatted dates;
- forecast/planning period dates and comparison/scope date labels are formatted;
- date inputs and API payload fields remain unchanged;
- existing tests remain green.

## Freeze rule

Freeze G2F1 only when one exact authoritative head passes:

1. RetailEdge Theme Compatibility;
2. Linters / Semgrep / vulnerable dependency audit;
3. clean Frappe v16 CI;
4. EdgeSuite UI Candidate Compatibility.
