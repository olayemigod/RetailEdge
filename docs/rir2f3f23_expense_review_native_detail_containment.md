# RIR2F3F23 — Expense Review Native Detail Containment

## Goal

Keep Expense Review as the EdgeSuite-owned operational review surface while preventing ordinary EdgeSuite-only users from escaping into native Frappe/ERPNext forms through informational report columns.

The existing Include / Exclude / Needs Clarification review action remains the normal operational workflow.

## Gap at F3F22 freeze

Expense Review already has an EdgeSuite review dialog backed by the existing permission-aware review endpoints, but four report columns were all marked clickable:

- Cashier Expense record;
- Cashier / User;
- Expense Category;
- Review Action.

The first three open native forms directly. Generic DocType/Report navigation from the page also had no independent Native Desk check, and the page fallback used the base Business Hub context rather than the hooked final context.

## Ownership Contract

1. Expense Review remains available to its existing permitted readers.
2. Reviewer authority continues to come from the existing Expense Review context and server-side review endpoint.
3. **Review Action** remains EdgeSuite-owned and clickable only when `canReview` is true.
4. Cashier Expense details open in a shared read-only EdgeSuite detail viewer backed by the governed Cashier Expense read scope.
5. Expense Category remains EdgeSuite-owned through Setup; User detail remains Native Desk-only.
6. The Cashier Expense detail viewer exposes an Advanced native form action only when `can_use_native_desk` is true.
7. Generic DocType/Report navigation also requires final Native Desk access.
8. The fallback navigation context uses `retailedge.master_experience.get_retailedge_business_hub_context`.
9. A read-only EdgeSuite user can inspect the scoped expense detail without gaining reviewer authority or Native Desk access.

## Scope

Runtime:
- `retailedge/public/js/expense_review/ExpenseReviewReport.vue`
- `retailedge/public/js/expense_register/CashierExpenseDetailDialog.vue`
- `retailedge/cashier_expense_detail.py` — dedicated permission/Branch-scoped read service for the shared detail viewer

Tests:
- `retailedge/tests/test_rir2f3f23_expense_review_native_detail_containment_contract.py`
- existing Expense Review and B4B10 scope tests remain authoritative.

Documentation:
- this record.

## Explicitly Unchanged

No Expense Review backend file is changed.

The following remain unchanged:

- `retailedge/expense_review.py`;
- `retailedge/cashier_expense_audit.py`;
- Include / Exclude / Needs Clarification mutation behavior;
- reviewer role/permission evaluation;
- posting-readiness calculation;
- Cashier Expense lifecycle;
- accounting posting;
- report rows, summaries, pagination and export;
- Company/Branch scope.

The review mutation endpoints remain unchanged.

The B4B10 read-scope contract remains authoritative. The new detail endpoint reuses that scope rather than creating a parallel visibility rule.

## Safety Rules

- Do not broaden reviewer authority.
- Do not use frontend Native Desk access as a replacement for backend review permission.
- Do not mutate submitted accounting documents.
- Do not change Cashier Expense posting or Daily Sales Audit inclusion semantics.
- Keep review operations inside EdgeSuite where already supported.
- Treat native record-detail forms only as explicit advanced inspection.

## Tests Required

Focused contracts must verify:

- final access context is fail-closed;
- Review Action remains EdgeSuite-owned and permission-gated by `canReview`;
- Cashier Expense detail opens inside EdgeSuite for permitted readers;
- the detail endpoint reuses authoritative Cashier Expense Company/Branch read scope;
- the Advanced native Cashier Expense action is hidden for EdgeSuite-only users;
- the direct native User path remains defensively gated;
- generic DocType/Report navigation is gated;
- review mutations, posting behavior and accounting truth remain unchanged.

## Freeze Rule

Freeze F3F23 only when RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and governed EdgeSuite UI Candidate Compatibility all pass on the same exact SHA.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.
