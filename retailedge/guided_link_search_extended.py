from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

from retailedge import cash_custody, guided_cash_transfer, guided_stock_adjustment, guided_stock_transfer

CANDIDATE_LIMIT = 100
MAX_ANCHORS = 4


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


def _query_anchors(query: str) -> tuple[str, ...]:
	term = " ".join(str(query or "").strip().casefold().split())
	if not term:
		return ("",)
	anchors = [term]
	for token in term.split():
		if len(token) >= 3:
			anchors.append(token[:3])
		if len(token) >= 2:
			anchors.append(token[-2:])
	unique: list[str] = []
	for anchor in anchors:
		if anchor not in unique:
			unique.append(anchor)
		if len(unique) >= MAX_ANCHORS:
			break
	return tuple(unique)


def _collect_candidates(searcher: Callable[[str, int], list], query: str) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	seen: set[str] = set()
	for anchor in _query_anchors(query):
		remaining = CANDIDATE_LIMIT - len(rows)
		if remaining <= 0:
			break
		for source in searcher(anchor, remaining):
			row = dict(source)
			key = str(row.get("value") or row.get("name") or row.get("label") or "")
			if not key or key in seen:
				continue
			seen.add(key)
			rows.append(row)
			if len(rows) >= CANDIDATE_LIMIT:
				break
	return rows


def _stock_transfer_candidates(fieldname: str, values: dict[str, Any], query: str) -> list[dict[str, Any]]:
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	source_branch = values.get("source_branch") or ""
	target_branch = values.get("target_branch") or ""
	if fieldname == "item_code":
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Item",
				txt,
				query="erpnext.controllers.queries.item_query",
				filters={"is_stock_item": 1, "disabled": 0},
				page_length=page_length,
				reference_doctype="Stock Entry Detail",
				link_fieldname="item_code",
			),
			query,
		)
	if fieldname in {"source_warehouse", "target_warehouse"}:
		branch = source_branch if fieldname == "source_warehouse" else target_branch
		filters = guided_stock_transfer._warehouse_search_filters(
			company=company, branch=branch, user=frappe.session.user
		)
		if filters is None:
			return []
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Warehouse",
				txt,
				filters=filters,
				page_length=page_length,
				reference_doctype=guided_stock_transfer.STOCK_ENTRY_DOCTYPE,
				link_fieldname="from_warehouse" if fieldname == "source_warehouse" else "to_warehouse",
			),
			query,
		)
	if fieldname in {"source_branch", "target_branch"}:
		if not guided_stock_transfer.has_doctype("Branch"):
			return []
		filters = guided_stock_transfer._branch_search_filters(company=company, user=frappe.session.user)
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Branch",
				txt,
				filters=filters,
				page_length=page_length,
				reference_doctype=guided_stock_transfer.STOCK_ENTRY_DOCTYPE,
				link_fieldname="retailedge_branch",
			),
			query,
		)
	frappe.throw(_("Unsupported Simple Stock Transfer search field: {0}").format(fieldname))
	return []


def _stock_adjustment_candidates(fieldname: str, values: dict[str, Any], query: str) -> list[dict[str, Any]]:
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	branch = values.get("branch") or ""
	if fieldname == "item_code":
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Item",
				txt,
				query="erpnext.controllers.queries.item_query",
				filters={"is_stock_item": 1, "disabled": 0},
				page_length=page_length,
				reference_doctype="Stock Reconciliation Item",
				link_fieldname="item_code",
			),
			query,
		)
	if fieldname == "warehouse":
		filters = guided_stock_adjustment._warehouse_search_filters(
			company=company, branch=branch, user=frappe.session.user
		)
		if filters is None:
			return []
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Warehouse",
				txt,
				filters=filters,
				page_length=page_length,
				reference_doctype=guided_stock_adjustment.STOCK_RECONCILIATION_DOCTYPE,
				link_fieldname="set_warehouse",
			),
			query,
		)
	if fieldname == "branch":
		if not guided_stock_adjustment.has_doctype("Branch"):
			return []
		filters = guided_stock_adjustment._branch_search_filters(company=company, user=frappe.session.user)
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Branch",
				txt,
				filters=filters,
				page_length=page_length,
				reference_doctype=guided_stock_adjustment.STOCK_RECONCILIATION_DOCTYPE,
				link_fieldname="retailedge_branch",
			),
			query,
		)
	frappe.throw(_("Unsupported Stock Adjustment search field: {0}").format(fieldname))
	return []


def _cash_transfer_candidates(fieldname: str, values: dict[str, Any], query: str) -> list[dict[str, Any]]:
	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if fieldname in {"from_account", "to_account"}:
		return _collect_candidates(
			lambda txt, page_length: guided_cash_transfer._search_bank_cash_accounts(
				company=company, txt=txt, limit=page_length
			),
			query,
		)
	if fieldname == "branch":
		return _collect_candidates(
			lambda txt, page_length: guided_cash_transfer._search_branches(
				company=company, txt=txt, limit=page_length
			),
			query,
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
	return _rank(_stock_transfer_candidates(fieldname, values, txt), txt, limit)


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
	return _rank(_stock_adjustment_candidates(fieldname, values, txt), txt, limit)


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
	return _rank(_cash_transfer_candidates(fieldname, values, txt), txt, limit)


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
	rows = _collect_candidates(
		lambda query, page_length: cash_custody.search_retailedge_bank_accounts(
			company=company,
			branch=branch,
			txt=query,
			limit=page_length,
		),
		txt,
	)
	return _rank(rows, txt, limit)
