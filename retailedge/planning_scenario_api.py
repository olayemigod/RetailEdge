from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.operating_context import get_operational_branch_scope
from retailedge.planning_scope import resolve_planning_branch_scope

SCENARIO_DOCTYPE = "RetailEdge Planning Scenario"
MAX_SCENARIO_RESULTS = 20

SCENARIO_PAGE_FIELDS = (
	"name",
	"scenario_name",
	"scenario_type",
	"status",
	"company",
	"branch",
	"as_of_date",
	"history_months",
	"horizon_months",
	"sales_adjustment_percent",
	"expense_adjustment_percent",
	"cash_adjustment_percent",
	"inventory_safety_percent",
)


@frappe.whitelist()
def search_planning_scenarios(
	txt: str = "",
	company: str = "",
	branch: str = "",
) -> list[dict[str, Any]]:
	"""Return permission-aware Planning Scenario options inside operational Branch scope."""
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	txt = str(txt or "").strip()
	if not company:
		return []
	_assert_company_read(company)
	if not frappe.has_permission(SCENARIO_DOCTYPE, "read"):
		return []

	filters: dict[str, Any] = {"company": company}
	if branch:
		filters["branch"] = resolve_planning_branch_scope(
			company,
			branch,
			user=frappe.session.user,
		)
	else:
		scope = get_operational_branch_scope(company, user=frappe.session.user)
		if scope.get("restricted"):
			allowed = [
				str(value).strip()
				for value in scope.get("allowed_branches") or []
				if str(value or "").strip()
			]
			if not allowed:
				return []
			filters["branch"] = allowed[0] if len(allowed) == 1 else ["in", allowed]

	or_filters = None
	if txt:
		pattern = f"%{txt}%"
		or_filters = {
			"name": ["like", pattern],
			"scenario_name": ["like", pattern],
		}

	rows = frappe.get_list(
		SCENARIO_DOCTYPE,
		filters=filters,
		or_filters=or_filters,
		fields=["name", "scenario_name", "scenario_type", "status", "company", "branch"],
		order_by="modified desc, name desc",
		limit_page_length=MAX_SCENARIO_RESULTS,
	)
	return [
		{
			"value": row.name,
			"label": row.scenario_name or row.name,
			"description": " · ".join(
				value
				for value in (
					row.scenario_type,
					row.status,
					row.branch or _("Company-wide"),
				)
				if value
			),
		}
		for row in rows
	]


@frappe.whitelist()
def get_planning_scenario(name: str) -> dict[str, Any]:
	"""Return only the fields required by the EdgeSuite planning page after scope validation."""
	name = str(name or "").strip()
	if not name:
		frappe.throw(_("Planning Scenario is required."))
	if not frappe.has_permission(SCENARIO_DOCTYPE, "read", doc=name):
		frappe.throw(
			_("You do not have permission to view this Planning Scenario."),
			frappe.PermissionError,
		)

	doc = frappe.get_doc(SCENARIO_DOCTYPE, name)
	resolved_branch = resolve_planning_branch_scope(
		doc.company,
		doc.branch or "",
		user=frappe.session.user,
	)
	if str(doc.branch or "").strip() != resolved_branch:
		frappe.throw(
			_("You do not have permission to view this Planning Scenario in the current Branch scope."),
			frappe.PermissionError,
		)

	result: dict[str, Any] = {}
	for fieldname in SCENARIO_PAGE_FIELDS:
		value = doc.get(fieldname)
		if fieldname == "as_of_date" and value:
			value = str(value)
		result[fieldname] = value
	return result


def _assert_company_read(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(
			_("You do not have permission to use Company {0}.").format(company),
			frappe.PermissionError,
		)
