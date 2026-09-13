# RIR2F3F24 — Daily Sales Audit Native Detail Containment

## Goal

Keep the existing EdgeSuite Daily Sales Audit read surface from becoming a native-Desk escape for ordinary RetailEdge users.

This slice does not promote, redesign, calculate, approve, reject, reopen or post Daily Sales Audits. It changes frontend detail/navigation exposure only.

## Gap at F3F23 freeze

The Daily Sales Audit EdgeSuite report already reuses the hardened audit/register engines, but all of these columns were always clickable into native Desk:

- Daily Sales Audit record;
- Cashier/User;
- submitted/reviewed/rejected user references;
- POS Profile;
- POS Opening Shift;
- POS Closing Shift.

Generic DocType/Report navigation was also not independently access-gated, and the fallback navigation context used the base rather than final Business Hub context.

## Ownership Contract

1. Daily Sales Audit stays readable through its existing EdgeSuite report provider for permitted users.
2. Final `navigation.access.can_use_native_desk` defaults false and comes from the hooked final Business Hub context.
3. Audit/User/POS record columns are clickable only for Native Desk-authorised users.
4. The cell handler itself fails closed before any native Form route.
5. Generic DocType/Report navigation also requires Native Desk.
6. The fallback context uses `retailedge.master_experience.get_retailedge_business_hub_context`.
7. No route promotion is introduced by this slice; existing final Business Hub composition remains authoritative.

## Scope

Runtime:
- `retailedge/public/js/daily_sales_audit/DailySalesAuditReport.vue`

Tests:
- `retailedge/tests/test_rir2f3f24_daily_sales_audit_native_detail_containment_contract.py`
- existing Daily Sales Audit and prereporting scope tests remain authoritative.

Documentation:
- this record.

## Explicitly Unchanged

No Daily Sales Audit backend file is changed.

Unchanged areas include:

- `retailedge/daily_sales_audit.py`;
- `retailedge/daily_sales_audit_page.py`;
- `retailedge/daily_sales_audit_read_scope.py`;
- `retailedge/daily_sales_audit_register_read_scope.py`;
- audit calculations and variance rules;
- audit status/review/approval/rejection/reopen lifecycle;
- Cash Deposit semantics;
- Sales Invoice and Payment Entry lifecycle;
- POS shift lifecycle;
- Cashier Expense inclusion/review behavior;
- Company/Branch scope;
- rows, summaries, pagination and export.

B4B5 read/context scope remains unchanged.

B4B9 register scope remains unchanged.

## Safety Rules

- Do not broaden audit read/reviewer permissions.
- Do not mutate audit, POS, payment, sales or accounting documents.
- Do not replace backend permission checks with UI access checks.
- Treat Native Desk only as an explicit advanced inspection capability.
- Preserve the existing EdgeSuite report as read-only in this slice.

## Tests Required

Focused contracts must prove:

- final Native Desk access fails closed;
- all native-detail columns are non-clickable for EdgeSuite-only users;
- direct native cell navigation is defensively gated;
- generic native DocType/Report navigation is gated;
- no audit/read-scope/register backend changed.

## Freeze Rule

Freeze F3F24 only when RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and governed EdgeSuite UI Candidate Compatibility all pass on the same exact SHA.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.
