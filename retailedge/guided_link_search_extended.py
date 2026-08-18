from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

from retailedge import cash_custody, guided_cash_transfer, guided_stock_adjustment, guided_stock_transfer

CANDIDATE_LIMIT = 100


def _shared_ranker() -> Callable[..., list] | None:
	try:
		from edgesuite_ui.search_ranking import rank_search_records
	except (ImportError, ModuleNotFoundError):
		return None
	return rank_search_records


def _rank(rows: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
	ranker = _shared_ranker()
	if ranker is None:
		return rows[:limit]
	return list(
		ranker(
			rows,
			query or "",
			exact_fields=("value",),
			search_fields=("label", "description"),
			limit=limit,
		)
	)


def _bounded_limit(limit: int, maximum: int) -> int:
	return max(1, min(cint(limit) or maximum, maximum))


def _stock_transfer_candidates(fieldname: str, values: dict[str, Any]) -> list[dict[str, Any]]:
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	source_branch = values.get("source_branch") or ""
	target_branch = values.get("target_branch") or ""
	if fieldname == "item_code":
		return search_link(
			"Item",
			"",
			query="erpnext.controllers.queries.item_query",
			filters={"is_stock_item": 1, "disabled": 0},
			page_length=CANDIDATE_LIMIT,
			reference_doctype="Stock Entry Detail",
			link_fieldname="item_code",
		)
	if fieldname in {"source_warehouse", "target_warehouse"}:
		branch = source_branch if fieldname == "source_warehouse" else target_branch
		filters = guided_stock_transfer._warehouse_search_filters(
			company=company, branch=branch, user=frappe.session.user
		)
		if filters is None:
			return []
		return search_link(
			"Warehouse",
			"",
			filters=filters,
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_stock_transfer.STOCK_ENTRY_DOCTYPE,
			link_fieldname="from_warehouse" if fieldname == "source_warehouse" else "to_warehouse",
		)
	if fieldname in {"source_branch", "target_branch"}:
		if not guided_stock_transfer.has_doctype("Branch"):
			return []
		return search_link(
			"Branch",
			"",
			filters=guided_stock_transfer._branch_search_filters(
				company=company, user=frappe.session.user
			),
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_stock_transfer.STOCK_ENTRY_DOCTYPE,
			link_fieldname="retailedge_branch",
		)
	frappe.throw(_("Unsupported Simple Stock Transfer search field: {0}").format(fieldname))
	return []


def _stock_adjustment_candidates(fieldname: str, values: dict[str, Any]) -> list[dict[str, Any]]:
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	branch = values.get("branch") or ""
	if fieldname == "item_code":
		return search_link(
			"Item",
			"",
			query="erpnext.controllers.queries.item_query",
			filters={"is_stock_item": 1, "disabled": 0},
			page_length=CANDIDATE_LIMIT,
			reference_doctype="Stock Reconciliation Item",
			link_fieldname="item_code",
		)
	if fieldname == "warehouse":
		filters = guided_stock_adjustment._warehouse_search_filters(
			company=company, branch=branch, user=frappe.session.user
		)
		if filters is None:
			return []
		return search_link(
			"Warehouse",
			"",
			filters=filters,
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_stock_adjustment.STOCK_RECONCILIATION_DOCTYPE,
			link_fieldname="set_warehouse",
		)
	if fieldname == "branch":
		if not guided_stock_adjustment.has_doctype("Branch"):
			return []
		return search_link(
			"Branch",
			"",
			filters=guided_stock_adjustment._branch_search_filters(
				company=company, user=frappe.session.user
			),
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_stock_adjustment.STOCK_RECONCILIATION_DOCTYPE,
			link_fieldname="retailedge_branch",
		)
	frappe.throw(_("Unsupported Stock Adjustment search field: {0}").format(fieldname))
	return []


def _cash_transfer_candidates(fieldname: str, values: dict[str, Any]) -> list[dict[str, Any]]:
	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if fieldname in {"from_account", "to_account"}:
		return guided_cash_transfer._search_bank_cash_accounts(
			company=company, txt="", limit=CANDIDATE_LIMIT
		)
	if fieldname == "branch":
		return guided_cash_transfer._search_branches(
			company=company, txt="", limit=CANDIDATE_LIMIT
		)
	frappe.throw(_("Unsupported Cash / Bank Transfer search field: {0}").format(fieldname))
	return []


@frappe.whitelist()
def search_simple_stock_transfer_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = guided_stock_transfer.MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	if _shared_ranker() is None:
		return guided_stock_transfer.search_simple_stock_transfer_options(fieldname, txt, values, limit)
	guided_stock_transfer._assert_can_create_stock_entry()
	values = guided_stock_transfer._coerce_values(values)
	limit = _bounded_limit(limit, guided_stock_transfer.MAX_LINK_RESULTS)
	return _rank(_stock_transfer_candidates(fieldname, values), txt, limit)


@frappe.whitelist()
def search_simple_stock_adjustment_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = guided_stock_adjustment.MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	if _shared_ranker() is None:
		return guided_stock_adjustment.search_simple_stock_adjustment_options(fieldname, txt, values, limit)
	guided_stock_adjustment._assert_can_create_stock_reconciliation()
	values = guided_stock_adjustment._coerce_values(values)
	limit = _bounded_limit(limit, guided_stock_adjustment.MAX_LINK_RESULTS)
	return _rank(_stock_adjustment_candidates(fieldname, values), txt, limit)


@frappe.whitelist()
def search_simple_cash_transfer_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = guided_cash_transfer.MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	if _shared_ranker() is None:
		return guided_cash_transfer.search_simple_cash_transfer_options(fieldname, txt, values, limit)
	guided_cash_transfer._assert_can_create_payment_entry()
	values = guided_cash_transfer._coerce_values(values)
	limit = _bounded_limit(limit, guided_cash_transfer.MAX_LINK_RESULTS)
	return _rank(_cash_transfer_candidates(fieldname, values), txt, limit)


@frappe.whitelist()
def search_cash_deposit_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = cash_custody.MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	if _shared_ranker() is None:
		return cash_custody.search_cash_deposit_options(fieldname, txt, values, limit)
	cash_custody._assert_can_create_payment_entry()
	values = cash_custody._coerce_values(values)
	limit = _bounded_limit(limit, cash_custody.MAX_LINK_RESULTS)
	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(values.get("branch") or "").strip()
	if fieldname not in {"to_bank_account", "to_account"}:
		frappe.throw(_("Unsupported Deposit Cash search field: {0}").format(fieldname))
	if not company:
		return []
	rows = cash_custody.search_retailedge_bank_accounts(
		company=company,
		branch=branch,
		txt="",
		limit=CANDIDATE_LIMIT,
	)
	return _rank(rows, txt, limit)
