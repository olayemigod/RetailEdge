from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from retailedge.professional_purchasing import (
	SUPPLIER_DOCTYPE,
	_assert_read,
	_permission,
	_resolve_scope,
)

SUPPLIER_SCORECARD_DOCTYPE = "Supplier Scorecard"
SUPPLIER_SCORECARD_PERIOD_DOCTYPE = "Supplier Scorecard Period"
MAX_SCORECARD_PERIODS = 12


def _assert_scorecard_read(name: str | None = None) -> None:
	if not _permission(SUPPLIER_SCORECARD_DOCTYPE, "read", name):
		frappe.throw(
			_("ERPNext does not permit you to read Supplier Scorecards."),
			frappe.PermissionError,
		)


def _effective_supplier_governance(supplier: Any) -> dict[str, bool]:
	return {
		"warn_rfqs": bool(cint(getattr(supplier, "warn_rfqs", 0))),
		"warn_pos": bool(cint(getattr(supplier, "warn_pos", 0))),
		"prevent_rfqs": bool(cint(getattr(supplier, "prevent_rfqs", 0))),
		"prevent_pos": bool(cint(getattr(supplier, "prevent_pos", 0))),
	}


def _recent_periods(scorecard: str) -> list[dict[str, Any]]:
	if not _permission(SUPPLIER_SCORECARD_PERIOD_DOCTYPE, "read"):
		return []
	return list(
		frappe.get_list(
			SUPPLIER_SCORECARD_PERIOD_DOCTYPE,
			filters={"scorecard": scorecard, "docstatus": 1},
			fields=["name", "start_date", "end_date", "total_score"],
			order_by="end_date desc, name desc",
			limit_page_length=MAX_SCORECARD_PERIODS,
		)
		or []
	)


@frappe.whitelist()
def get_supplier_scorecard_capability() -> dict[str, Any]:
	"""Return native ERPNext Supplier Scorecard permissions without role widening."""
	can_read_scorecard = _permission(SUPPLIER_SCORECARD_DOCTYPE, "read")
	can_create_scorecard = _permission(SUPPLIER_SCORECARD_DOCTYPE, "create")
	can_read_periods = _permission(SUPPLIER_SCORECARD_PERIOD_DOCTYPE, "read")
	return {
		"can_read_scorecard": bool(can_read_scorecard),
		"can_create_scorecard": bool(can_create_scorecard),
		"can_read_periods": bool(can_read_periods),
		"max_periods": MAX_SCORECARD_PERIODS,
		"source_of_truth": "ERPNext Supplier Scorecard",
	}


@frappe.whitelist()
def get_supplier_scorecard_summary(
	supplier: str,
	company: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	"""Return a passive, permission-aware view of one native Supplier Scorecard."""
	supplier = str(supplier or "").strip()
	if not supplier:
		frappe.throw(_("Supplier is required."))

	resolved_company, resolved_branch, _allowed, _global_access = _resolve_scope(
		company=company,
		branch=branch,
	)
	_assert_read(SUPPLIER_DOCTYPE, supplier)
	_assert_scorecard_read()

	supplier_doc = frappe.get_doc(SUPPLIER_DOCTYPE, supplier)
	scorecard_exists = bool(frappe.db.exists(SUPPLIER_SCORECARD_DOCTYPE, supplier))
	scorecard_summary: dict[str, Any] | None = None
	periods: list[dict[str, Any]] = []

	if scorecard_exists:
		_assert_scorecard_read(supplier)
		scorecard = frappe.get_doc(SUPPLIER_SCORECARD_DOCTYPE, supplier)
		scorecard_summary = {
			"name": str(getattr(scorecard, "name", "") or supplier),
			"supplier": str(getattr(scorecard, "supplier", "") or supplier),
			"supplier_score": getattr(scorecard, "supplier_score", None),
			"status": str(getattr(scorecard, "status", "") or ""),
			"period": str(getattr(scorecard, "period", "") or ""),
		}
		periods = _recent_periods(supplier)

	return {
		"supplier": supplier,
		"supplier_name": str(getattr(supplier_doc, "supplier_name", "") or supplier),
		"company": resolved_company,
		"branch": resolved_branch,
		"scorecard_exists": scorecard_exists,
		"scorecard": scorecard_summary,
		"governance": _effective_supplier_governance(supplier_doc),
		"periods": periods,
		"period_count": len(periods),
		"periods_bounded_to": MAX_SCORECARD_PERIODS,
		"source_of_truth": "ERPNext Supplier Scorecard and Supplier governance flags",
	}
