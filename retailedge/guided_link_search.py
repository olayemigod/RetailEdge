from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

from retailedge import guided_payment, guided_purchase_invoice, guided_sales_invoice

CANDIDATE_LIMIT = 100
MAX_ANCHORS = 4


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


def _sales_candidates(fieldname: str, values: dict[str, Any], query: str) -> list[dict[str, Any]]:
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	branch = values.get("branch") or ""
	customer = values.get("customer") or ""

	if fieldname == "customer":
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Customer",
				txt,
				page_length=page_length,
				reference_doctype=guided_sales_invoice.SALES_INVOICE_DOCTYPE,
				link_fieldname="customer",
			),
			query,
		)
	if fieldname == "item_code":
		filters: dict[str, Any] = {"is_sales_item": 1}
		if customer:
			filters["customer"] = customer
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Item",
				txt,
				query="erpnext.controllers.queries.item_query",
				filters=filters,
				page_length=page_length,
				reference_doctype="Sales Invoice Item",
				link_fieldname="item_code",
			),
			query,
		)
	if fieldname == "warehouse":
		filters = guided_sales_invoice._warehouse_search_filters(
			company=company,
			branch=branch,
			user=frappe.session.user,
		)
		if filters is None:
			return []
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Warehouse",
				txt,
				filters=filters,
				page_length=page_length,
				reference_doctype=guided_sales_invoice.SALES_INVOICE_DOCTYPE,
				link_fieldname="set_warehouse",
			),
			query,
		)
	if fieldname == "branch":
		if not guided_sales_invoice.has_doctype("Branch"):
			return []
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Branch",
				txt,
				filters=guided_sales_invoice._branch_search_filters(
					company=company,
					user=frappe.session.user,
				),
				page_length=page_length,
				reference_doctype=guided_sales_invoice.SALES_INVOICE_DOCTYPE,
				link_fieldname="retailedge_branch",
			),
			query,
		)
	frappe.throw(_("Unsupported Simple Sales Invoice search field: {0}").format(fieldname))
	return []


def _purchase_candidates(fieldname: str, values: dict[str, Any], query: str) -> list[dict[str, Any]]:
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	branch = values.get("branch") or ""
	supplier = values.get("supplier") or ""

	if fieldname == "supplier":
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Supplier",
				txt,
				page_length=page_length,
				reference_doctype=guided_purchase_invoice.PURCHASE_INVOICE_DOCTYPE,
				link_fieldname="supplier",
			),
			query,
		)
	if fieldname == "item_code":
		filters: dict[str, Any] = {"is_purchase_item": 1}
		if supplier:
			filters["supplier"] = supplier
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Item",
				txt,
				query="erpnext.controllers.queries.item_query",
				filters=filters,
				page_length=page_length,
				reference_doctype="Purchase Invoice Item",
				link_fieldname="item_code",
			),
			query,
		)
	if fieldname == "warehouse":
		filters = guided_purchase_invoice._warehouse_search_filters(
			company=company,
			branch=branch,
			user=frappe.session.user,
		)
		if filters is None:
			return []
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Warehouse",
				txt,
				filters=filters,
				page_length=page_length,
				reference_doctype=guided_purchase_invoice.PURCHASE_INVOICE_DOCTYPE,
				link_fieldname="set_warehouse",
			),
			query,
		)
	if fieldname == "branch":
		if not guided_purchase_invoice.has_doctype("Branch"):
			return []
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Branch",
				txt,
				filters=guided_purchase_invoice._branch_search_filters(
					company=company,
					user=frappe.session.user,
				),
				page_length=page_length,
				reference_doctype=guided_purchase_invoice.PURCHASE_INVOICE_DOCTYPE,
				link_fieldname="retailedge_branch",
			),
			query,
		)
	frappe.throw(_("Unsupported Simple Purchase Invoice search field: {0}").format(fieldname))
	return []


def _payment_candidates(
	intent: str,
	fieldname: str,
	values: dict[str, Any],
	query: str,
) -> list[dict[str, Any]]:
	config = guided_payment._get_intent(intent)
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	branch = values.get("branch") or ""
	party = values.get("party") or ""

	if fieldname == "party":
		return _collect_candidates(
			lambda txt, page_length: search_link(
				config["party_type"],
				txt,
				page_length=page_length,
				reference_doctype=guided_payment.PAYMENT_ENTRY_DOCTYPE,
				link_fieldname="party",
			),
			query,
		)
	if fieldname == "mode_of_payment":
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Mode of Payment",
				txt,
				page_length=page_length,
				reference_doctype=guided_payment.PAYMENT_ENTRY_DOCTYPE,
				link_fieldname="mode_of_payment",
			),
			query,
		)
	if fieldname == "branch":
		if not guided_payment.has_doctype("Branch"):
			return []
		return _collect_candidates(
			lambda txt, page_length: search_link(
				"Branch",
				txt,
				filters=guided_payment._branch_search_filters(
					company=company,
					user=frappe.session.user,
				),
				page_length=page_length,
				reference_doctype=guided_payment.PAYMENT_ENTRY_DOCTYPE,
				link_fieldname="retailedge_branch",
			),
			query,
		)
	if fieldname == "reference_name":
		if not party:
			return []
		return _collect_candidates(
			lambda txt, page_length: guided_payment._search_outstanding_references(
				config=config,
				company=company,
				branch=branch,
				party=party,
				txt=txt,
				limit=page_length,
			),
			query,
		)
	frappe.throw(_("Unsupported Simple Payment search field: {0}").format(fieldname))
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
	return _rank_options(_sales_candidates(fieldname, values, txt), txt or "", limit)


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
	return _rank_options(_purchase_candidates(fieldname, values, txt), txt or "", limit)


@frappe.whitelist()
def search_simple_payment_options(
	intent: str,
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = guided_payment.MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	if _shared_ranker() is None:
		return guided_payment.search_simple_payment_options(intent, fieldname, txt, values, limit)
	guided_payment._get_intent(intent)
	guided_payment._assert_can_create_payment_entry()
	values = guided_payment._coerce_values(values)
	limit = _bounded_limit(limit, guided_payment.MAX_LINK_RESULTS)
	return _rank_options(_payment_candidates(intent, fieldname, values, txt), txt or "", limit)
