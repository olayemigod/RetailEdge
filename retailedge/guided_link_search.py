from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

from retailedge import guided_purchase_invoice, guided_sales_invoice

CANDIDATE_LIMIT = 100


def _shared_ranker() -> Callable[..., list] | None:
	try:
		from edgesuite_ui.search_ranking import rank_search_records
	except (ImportError, ModuleNotFoundError):
		return None
	return rank_search_records


def _rank_options(rows: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
	ranker = _shared_ranker()
	if ranker is None:
		return rows[:limit]
	return list(
		ranker(
			rows,
			query,
			exact_fields=("value",),
			search_fields=("label", "description"),
			limit=limit,
		)
	)


def _bounded_limit(limit: int, maximum: int) -> int:
	return max(1, min(cint(limit) or maximum, maximum))


def _sales_candidates(fieldname: str, values: dict[str, Any]) -> list[dict[str, Any]]:
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	branch = values.get("branch") or ""
	customer = values.get("customer") or ""

	if fieldname == "customer":
		return search_link(
			"Customer",
			"",
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_sales_invoice.SALES_INVOICE_DOCTYPE,
			link_fieldname="customer",
		)
	if fieldname == "item_code":
		filters: dict[str, Any] = {"is_sales_item": 1}
		if customer:
			filters["customer"] = customer
		return search_link(
			"Item",
			"",
			query="erpnext.controllers.queries.item_query",
			filters=filters,
			page_length=CANDIDATE_LIMIT,
			reference_doctype="Sales Invoice Item",
			link_fieldname="item_code",
		)
	if fieldname == "warehouse":
		filters = guided_sales_invoice._warehouse_search_filters(
			company=company,
			branch=branch,
			user=frappe.session.user,
		)
		if filters is None:
			return []
		return search_link(
			"Warehouse",
			"",
			filters=filters,
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_sales_invoice.SALES_INVOICE_DOCTYPE,
			link_fieldname="set_warehouse",
		)
	if fieldname == "branch":
		if not guided_sales_invoice.has_doctype("Branch"):
			return []
		return search_link(
			"Branch",
			"",
			filters=guided_sales_invoice._branch_search_filters(
				company=company,
				user=frappe.session.user,
			),
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_sales_invoice.SALES_INVOICE_DOCTYPE,
			link_fieldname="retailedge_branch",
		)
	frappe.throw(_("Unsupported Simple Sales Invoice search field: {0}").format(fieldname))
	return []


def _purchase_candidates(fieldname: str, values: dict[str, Any]) -> list[dict[str, Any]]:
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	branch = values.get("branch") or ""
	supplier = values.get("supplier") or ""

	if fieldname == "supplier":
		return search_link(
			"Supplier",
			"",
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_purchase_invoice.PURCHASE_INVOICE_DOCTYPE,
			link_fieldname="supplier",
		)
	if fieldname == "item_code":
		filters: dict[str, Any] = {"is_purchase_item": 1}
		if supplier:
			filters["supplier"] = supplier
		return search_link(
			"Item",
			"",
			query="erpnext.controllers.queries.item_query",
			filters=filters,
			page_length=CANDIDATE_LIMIT,
			reference_doctype="Purchase Invoice Item",
			link_fieldname="item_code",
		)
	if fieldname == "warehouse":
		filters = guided_purchase_invoice._warehouse_search_filters(
			company=company,
			branch=branch,
			user=frappe.session.user,
		)
		if filters is None:
			return []
		return search_link(
			"Warehouse",
			"",
			filters=filters,
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_purchase_invoice.PURCHASE_INVOICE_DOCTYPE,
			link_fieldname="set_warehouse",
		)
	if fieldname == "branch":
		if not guided_purchase_invoice.has_doctype("Branch"):
			return []
		return search_link(
			"Branch",
			"",
			filters=guided_purchase_invoice._branch_search_filters(
				company=company,
				user=frappe.session.user,
			),
			page_length=CANDIDATE_LIMIT,
			reference_doctype=guided_purchase_invoice.PURCHASE_INVOICE_DOCTYPE,
			link_fieldname="retailedge_branch",
		)
	frappe.throw(_("Unsupported Simple Purchase Invoice search field: {0}").format(fieldname))
	return []


@frappe.whitelist()
def search_simple_sales_invoice_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = guided_sales_invoice.MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	if _shared_ranker() is None:
		return guided_sales_invoice.search_simple_sales_invoice_options(fieldname, txt, values, limit)
	guided_sales_invoice._assert_can_create_sales_invoice()
	values = guided_sales_invoice._coerce_values(values)
	limit = _bounded_limit(limit, guided_sales_invoice.MAX_LINK_RESULTS)
	return _rank_options(_sales_candidates(fieldname, values), txt or "", limit)


@frappe.whitelist()
def search_simple_purchase_invoice_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = guided_purchase_invoice.MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	if _shared_ranker() is None:
		return guided_purchase_invoice.search_simple_purchase_invoice_options(fieldname, txt, values, limit)
	guided_purchase_invoice._assert_can_create_purchase_invoice()
	values = guided_purchase_invoice._coerce_values(values)
	limit = _bounded_limit(limit, guided_purchase_invoice.MAX_LINK_RESULTS)
	return _rank_options(_purchase_candidates(fieldname, values), txt or "", limit)
