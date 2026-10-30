from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

import frappe

from retailedge.bank_transaction_matching import assert_can_access_bank_transaction_matching
from retailedge.dashboard_capabilities import get_dashboard_capabilities
from retailedge.native_visual_workspaces import WORKSPACES
from retailedge.reporting_capabilities import _REPORT_SPECS, get_report_capabilities


DASHBOARD_PAGE_SCOPES = {
	"owner-dashboard": "owner-dashboard",
	"sales-overview": "sales-overview",
	"money-overview": "money-overview",
	"expense-overview": "expense-overview",
	"branch-performance-dashboard": "branch-performance",
	"salesperson-performance-dashboard": "salesperson-performance",
	"profitability-intelligence": "profitability-intelligence",
}

NATIVE_WORKSPACE_BY_PAGE = {
	str(config.get("page_route") or ""): workspace
	for workspace, config in WORKSPACES.items()
	if config.get("page_route")
}

REPORT_PAGE_TARGETS = frozenset(_REPORT_SPECS)
BANK_MATCHING_PAGE = "bank-matching-reconciliation"
CASHIER_ROLES = {"RetailEdgeCashier", "RetailEdge Cashier"}
CASHIER_MANAGEMENT_ROLES = {
	"System Manager",
	"RetailEdgeManager",
	"RetailEdge Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Branch Manager",
	"RetailEdgeAuditor",
	"RetailEdge Auditor",
}
CASHIER_ALLOWED_PAGE_TARGETS = {
	"cashier-my-work",
	"cashier-expenses",
	"operating-context",
	"make-sale",
}
CASHIER_ALLOWED_URL_TARGETS = {"/pos/"}


def _quiet_probe(callback: Callable[[], bool]) -> bool:
	"""Fail closed for menu discovery without leaking probe messages to Desk."""
	previous_messages = list(getattr(frappe.local, "message_log", []) or [])
	try:
		return bool(callback())
	except Exception:
		return False
	finally:
		frappe.local.message_log = previous_messages


def _page_is_permitted(page_name: str) -> bool:
	def probe() -> bool:
		if not frappe.db.exists("Page", page_name):
			return False
		page = frappe.get_doc("Page", page_name)
		return bool(page.is_permitted())

	return _quiet_probe(probe)


def _report_is_permitted(report_name: str) -> bool:
	def probe() -> bool:
		from frappe.desk.query_report import get_report_doc

		return bool(get_report_doc(report_name))

	return _quiet_probe(probe)


def _native_source_is_available(source: dict[str, Any]) -> bool:
	kind = str(source.get("kind") or "").strip().lower()
	target = str(source.get("target") or "").strip()
	if not kind or not target:
		return False
	if kind == "doctype":
		return _quiet_probe(
			lambda: bool(frappe.db.exists("DocType", target))
			and bool(frappe.has_permission(target, ptype="read", user=frappe.session.user))
		)
	if kind == "report":
		return _report_is_permitted(target)
	if kind == "page":
		# A native control workspace must not stay visible merely because a nested
		# RetailEdge Page record is readable. Reuse the same functional dashboard /
		# report capability gate that applies to top-level navigation.
		return _page_is_functionally_available(target)
	return False


def _native_workspace_is_available(workspace: str) -> bool:
	config = WORKSPACES.get(workspace) or {}
	return any(_native_source_is_available(source) for source in config.get("sources") or ())


def _page_is_functionally_available(
	page_name: str,
	*,
	company: str = "",
	branch: str = "",
) -> bool:
	"""Check product/business capability in addition to Frappe Page permission."""
	if page_name in DASHBOARD_PAGE_SCOPES:
		scope_key = DASHBOARD_PAGE_SCOPES[page_name]
		return _quiet_probe(
			lambda: bool(
				get_dashboard_capabilities(
					scope_key,
					company=company,
					branch=branch,
					user=frappe.session.user,
				).get("can_view")
			)
		)

	if page_name in REPORT_PAGE_TARGETS:
		return _quiet_probe(
			lambda: bool(
				get_report_capabilities(
					page_name,
					company=company,
					branch=branch,
					user=frappe.session.user,
				).get("can_view")
			)
		)

	workspace = NATIVE_WORKSPACE_BY_PAGE.get(page_name)
	if workspace:
		return _native_workspace_is_available(workspace)

	if page_name == BANK_MATCHING_PAGE:
		return _quiet_probe(
			lambda: bool(assert_can_access_bank_transaction_matching(user=frappe.session.user))
		)

	# Re-check ordinary Page permission at the final composition boundary. This is
	# intentionally redundant for master-registry links and also protects Pages that
	# final composition adds dynamically (for example cashier My Work).
	return _page_is_permitted(page_name)


def _item_is_functionally_available(
	item: dict[str, Any],
	*,
	company: str = "",
	branch: str = "",
) -> bool:
	target_type = str(item.get("target_type") or "").strip()
	target = str(item.get("target") or "").strip()
	if not target:
		return False
	if target_type != "Page":
		return True
	return _page_is_functionally_available(target, company=company, branch=branch)


def _is_cashier_home_persona() -> bool:
	"""Return True for the thin cashier persona, not managers who also carry Cashier."""
	roles = set(frappe.get_roles(frappe.session.user) or [])
	return bool(roles.intersection(CASHIER_ROLES)) and not bool(roles.intersection(CASHIER_MANAGEMENT_ROLES))


def _cashier_item_is_relevant(item: dict[str, Any]) -> bool:
	"""Keep the cashier menu task-focused after normal permission filtering.

	A cashier should see their own work, POS launch, cashier expense entry and working
	Branch context. Make Sale remains available only where the merchant has separately
	granted normal Sales Invoice create permission. This projection grants nothing.
	"""
	target_type = str(item.get("target_type") or "").strip()
	target = str(item.get("target") or "").strip()
	if target_type == "URL":
		return target in CASHIER_ALLOWED_URL_TARGETS
	if target_type == "Page":
		if target not in CASHIER_ALLOWED_PAGE_TARGETS:
			return False
		if target == "make-sale":
			return _quiet_probe(
				lambda: bool(frappe.db.exists("DocType", "Sales Invoice"))
				and bool(frappe.has_permission("Sales Invoice", ptype="create", user=frappe.session.user))
			)
		return True
	# Quick Sale may be represented as the Sales Invoice DocType in quick actions.
	if target_type == "DocType" and target == "Sales Invoice":
		return _quiet_probe(
			lambda: bool(frappe.has_permission("Sales Invoice", ptype="create", user=frappe.session.user))
		)
	return False


def _project_cashier_navigation(context: dict[str, Any]) -> None:
	if not _is_cashier_home_persona():
		return

	groups: list[dict[str, Any]] = []
	for group in context.get("navigation_groups") or []:
		items = [item for item in group.get("items") or [] if _cashier_item_is_relevant(item)]
		if not items:
			continue
		clean_group = deepcopy(group)
		clean_group["items"] = items
		groups.append(clean_group)
	context["navigation_groups"] = groups
	context["quick_actions"] = [
		action for action in context.get("quick_actions") or [] if _cashier_item_is_relevant(action)
	]


def filter_context_for_runtime_capabilities(context: dict[str, Any]) -> dict[str, Any]:
	"""Remove links that would immediately reject the current user.

	This is a presentation filter only. It grants no permissions and does not replace
	the destination's server-side authorization. The goal is to avoid advertising
	manager/native capabilities to thin operational personas such as cashiers.
	"""
	filtered = deepcopy(context or {})
	operating_context = filtered.get("context") or {}
	company = str(operating_context.get("company") or "").strip()
	branch = str(operating_context.get("branch") or "").strip()

	groups: list[dict[str, Any]] = []
	for group in filtered.get("navigation_groups") or []:
		items = [
			item
			for item in group.get("items") or []
			if _item_is_functionally_available(item, company=company, branch=branch)
		]
		if not items:
			continue
		clean_group = deepcopy(group)
		clean_group["items"] = items
		groups.append(clean_group)
	filtered["navigation_groups"] = groups

	filtered["quick_actions"] = [
		action
		for action in filtered.get("quick_actions") or []
		if _item_is_functionally_available(action, company=company, branch=branch)
	]
	_project_cashier_navigation(filtered)
	return filtered
