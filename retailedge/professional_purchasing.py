from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt
from frappe.utils.user import get_user_fullname

from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	get_user_allowed_branches,
	has_field,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.operating_context import get_operating_context

PURCHASE_ORDER_DOCTYPE = "Purchase Order"
PURCHASE_RECEIPT_DOCTYPE = "Purchase Receipt"
SUPPLIER_DOCTYPE = "Supplier"
MAX_PURCHASE_ORDERS = 200
MAX_LINK_RESULTS = 20


def _permission(doctype: str, ptype: str, name: str | None = None) -> bool:
	try:
		return bool(frappe.has_permission(doctype, ptype, doc=name))
	except Exception:
		return False


def _assert_read(doctype: str, name: str | None = None) -> None:
	if not _permission(doctype, "read", name):
		frappe.throw(_("You do not have permission to read {0}.").format(_(doctype)), frappe.PermissionError)


def _assert_create(doctype: str) -> None:
	if not _permission(doctype, "create"):
		frappe.throw(_("You do not have permission to create {0}.").format(_(doctype)), frappe.PermissionError)


def _transaction_branch_field(doctype: str) -> str | None:
	if has_field(doctype, "retailedge_branch"):
		return "retailedge_branch"
	return get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)


def _document_branch(doc: Any) -> str:
	field = _transaction_branch_field(doc.doctype)
	return str(getattr(doc, field, None) or "") if field else ""


def _resolve_scope(company: str | None = None, branch: str | None = None) -> tuple[str, str, list[str], bool]:
	operating = get_operating_context() or {}
	resolved_company = str(
		company
		or operating.get("company")
		or frappe.defaults.get_user_default("Company")
		or ""
	).strip()
	if not resolved_company:
		frappe.throw(_("Choose an Operating Company before using Professional Purchasing."))
	_assert_read("Company", resolved_company)

	resolved_branch = str(branch or "").strip()
	if not resolved_branch and (not company or resolved_company == str(operating.get("company") or "")):
		resolved_branch = str(operating.get("branch") or "").strip()
	if resolved_branch:
		validate_user_branch_access(
			resolved_branch,
			user=frappe.session.user,
			company=resolved_company,
			throw=True,
		)

	global_access = user_has_global_branch_access(user=frappe.session.user)
	allowed = list(
		get_user_allowed_branches(user=frappe.session.user, company=resolved_company).get("branches") or []
	)
	if resolved_branch and allowed and not global_access and resolved_branch not in allowed:
		frappe.throw(_("You do not have access to Branch {0}.").format(resolved_branch), frappe.PermissionError)
	return resolved_company, resolved_branch, allowed, global_access


def _purchase_order_filters(
	*,
	company: str,
	branch: str,
	supplier: str,
	allowed_branches: list[str],
	global_branch_access: bool,
) -> tuple[dict[str, Any], str | None]:
	filters: dict[str, Any] = {"company": company, "docstatus": ["<", 2]}
	if supplier:
		filters["supplier"] = supplier

	branch_field = _transaction_branch_field(PURCHASE_ORDER_DOCTYPE)
	if branch:
		if not branch_field:
			frappe.throw(
			_("Purchase Order branch attribution is unavailable. Run site migration before using a Branch-scoped purchasing workspace.")
		)
		filters[branch_field] = branch
	elif not global_branch_access:
		if not branch_field:
			frappe.throw(
			_("Purchase Order branch attribution is unavailable. Run site migration before using restricted Branch purchasing access.")
		)
		filters[branch_field] = ["in", allowed_branches or ["__no_permitted_branch__"]]
	return filters, branch_field


@frappe.whitelist()
def get_professional_purchasing_context(
	company: str | None = None,
	branch: str | None = None,
	supplier: str | None = None,
	limit: int | str = 100,
) -> dict[str, Any]:
	"""Return a permission-aware operational Purchase Order view.

	The dataset is read from ERPNext Purchase Orders. RetailEdge does not maintain
	purchase-order progress, receipt quantities or billing state separately.
	"""
	_assert_read(PURCHASE_ORDER_DOCTYPE)
	company, branch, allowed_branches, global_branch_access = _resolve_scope(company, branch)
	supplier = str(supplier or "").strip()
	if supplier:
		_assert_read(SUPPLIER_DOCTYPE, supplier)

	filters, branch_field = _purchase_order_filters(
		company=company,
		branch=branch,
		supplier=supplier,
		allowed_branches=allowed_branches,
		global_branch_access=global_branch_access,
	)
	row_limit = max(1, min(cint(limit) or 100, MAX_PURCHASE_ORDERS))
	fields = [
		"name",
		"docstatus",
		"transaction_date",
		"schedule_date",
		"company",
		"supplier",
		"supplier_name",
		"status",
		"currency",
		"grand_total",
		"per_received",
		"per_billed",
		"is_subcontracted",
		"modified",
	]
	if branch_field:
		fields.append(branch_field)

	rows = frappe.get_list(
		PURCHASE_ORDER_DOCTYPE,
		filters=filters,
		fields=fields,
		order_by="transaction_date desc, name desc",
		limit_page_length=row_limit,
	)
	can_create_receipt = _permission(PURCHASE_RECEIPT_DOCTYPE, "create")
	result_rows = []
	for row in rows:
		row_branch = str(row.get(branch_field) or "") if branch_field else ""
		per_received = flt(row.get("per_received"))
		status = str(row.get("status") or "")
		can_prepare_receipt = bool(
			can_create_receipt
			and cint(row.get("docstatus")) == 1
			and per_received < 100
			and not cint(row.get("is_subcontracted"))
			and status not in {"Closed", "Completed", "Cancelled"}
		)
		result_rows.append(
			{
				"name": row.get("name"),
				"docstatus": cint(row.get("docstatus")),
				"transaction_date": row.get("transaction_date"),
				"schedule_date": row.get("schedule_date"),
				"company": row.get("company"),
				"supplier": row.get("supplier"),
				"supplier_name": row.get("supplier_name") or row.get("supplier"),
				"status": status,
				"currency": row.get("currency"),
				"grand_total": flt(row.get("grand_total")),
				"per_received": per_received,
				"per_billed": flt(row.get("per_billed")),
				"branch": row_branch,
				"is_subcontracted": bool(cint(row.get("is_subcontracted"))),
				"can_prepare_receipt": can_prepare_receipt,
				"route": f"/app/purchase-order/{row.get('name')}",
			}
		)

	to_receive = [row for row in result_rows if row["can_prepare_receipt"]]
	return {
		"company": company,
		"branch": branch,
		"supplier": supplier,
		"rows": result_rows,
		"summary": {
			"purchase_orders": len(result_rows),
			"to_receive": len(to_receive),
			"drafts": sum(1 for row in result_rows if row["docstatus"] == 0),
			"open_value": sum(row["grand_total"] for row in result_rows if row["docstatus"] == 1),
		},
		"capabilities": {
			"can_read_purchase_order": True,
			"can_create_purchase_order": _permission(PURCHASE_ORDER_DOCTYPE, "create"),
			"can_read_purchase_receipt": _permission(PURCHASE_RECEIPT_DOCTYPE, "read"),
			"can_create_purchase_receipt": can_create_receipt,
		},
		"limits": {"purchase_orders": MAX_PURCHASE_ORDERS, "link_results": MAX_LINK_RESULTS},
		"source_of_truth": PURCHASE_ORDER_DOCTYPE,
		"receipt_source_of_truth": "ERPNext Purchase Order make_purchase_receipt mapper",
		"user_name": get_user_fullname(frappe.session.user),
	}


@frappe.whitelist()
def search_professional_purchasing_options(
	kind: str,
	txt: str = "",
	company: str | None = None,
) -> list[dict[str, Any]]:
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	if kind == "company":
		return search_link("Company", txt, page_length=MAX_LINK_RESULTS)
	if kind == "supplier":
		return search_link(
			SUPPLIER_DOCTYPE,
			txt,
			page_length=MAX_LINK_RESULTS,
			reference_doctype=PURCHASE_ORDER_DOCTYPE,
			link_fieldname="supplier",
		)
	if kind == "branch":
		resolved_company, _branch, allowed, global_access = _resolve_scope(company=company, branch=None)
		filters: dict[str, Any] = {}
		if has_field("Branch", "company"):
			filters["company"] = resolved_company
		if not global_access:
			filters["name"] = ["in", allowed or ["__no_permitted_branch__"]]
		rows = frappe.get_list(
			"Branch",
			filters=filters,
			or_filters={"name": ["like", f"%{txt}%"]} if txt else None,
			fields=["name"],
			order_by="name asc",
			limit_page_length=MAX_LINK_RESULTS,
		)
		return [{"value": row.name, "label": row.name} for row in rows]
	frappe.throw(_("Unsupported Professional Purchasing search type."))
	return []


@frappe.whitelist(methods=["POST"])
def prepare_purchase_receipt_draft(purchase_order: str) -> dict[str, Any]:
	"""Prepare one standard ERPNext Purchase Receipt draft from a submitted PO."""
	purchase_order = str(purchase_order or "").strip()
	if not purchase_order:
		frappe.throw(_("Purchase Order is required."))
	_assert_read(PURCHASE_ORDER_DOCTYPE, purchase_order)
	_assert_create(PURCHASE_RECEIPT_DOCTYPE)

	po = frappe.get_doc(PURCHASE_ORDER_DOCTYPE, purchase_order)
	if cint(po.docstatus) != 1:
		frappe.throw(_("Only submitted Purchase Orders can prepare a Purchase Receipt."))
	if str(getattr(po, "status", "") or "") in {"Closed", "Completed", "Cancelled"}:
		frappe.throw(_("Purchase Order {0} is not open for receiving.").format(purchase_order))
	if flt(getattr(po, "per_received", 0)) >= 100:
		frappe.throw(_("Purchase Order {0} is already fully received.").format(purchase_order))
	if cint(getattr(po, "is_subcontracted", 0)):
		frappe.throw(_("Use the full ERPNext Purchase Order workflow for subcontracted orders."))

	branch = _document_branch(po)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=po.company,
			throw=True,
		)

	receipt = make_purchase_receipt(po.name)
	if not receipt or getattr(receipt, "doctype", None) != PURCHASE_RECEIPT_DOCTYPE:
		frappe.throw(_("ERPNext could not prepare a Purchase Receipt from {0}.").format(purchase_order))
	items = [row for row in (getattr(receipt, "items", None) or []) if flt(getattr(row, "qty", 0)) > 0]
	if not items:
		frappe.throw(_("Purchase Order {0} has no remaining receivable items.").format(purchase_order))
	if str(getattr(receipt, "company", "") or "") != str(po.company or ""):
		frappe.throw(_("Mapped Purchase Receipt Company does not match the Purchase Order."))
	if str(getattr(receipt, "supplier", "") or "") != str(po.supplier or ""):
		frappe.throw(_("Mapped Purchase Receipt Supplier does not match the Purchase Order."))

	receipt_branch_field = _transaction_branch_field(PURCHASE_RECEIPT_DOCTYPE)
	if branch and receipt_branch_field:
		setattr(receipt, receipt_branch_field, branch)
	elif branch and not receipt_branch_field:
		frappe.throw(
			_("Purchase Receipt branch attribution is unavailable. Run site migration before using this Branch-scoped action.")
		)

	# Insert as the current user. ERPNext Purchase Receipt validation owns stock,
	# quantities, taxes, warehouses and accounting safety. This action stays draft-first.
	receipt.insert()
	return {
		"doctype": receipt.doctype,
		"name": receipt.name,
		"docstatus": cint(receipt.docstatus),
		"purchase_order": po.name,
		"company": receipt.company,
		"supplier": receipt.supplier,
		"branch": getattr(receipt, receipt_branch_field, "") if receipt_branch_field else "",
		"item_count": len(items),
		"posting_status": "Draft",
		"source_of_truth": "ERPNext Purchase Order make_purchase_receipt mapper",
		"route": f"/app/purchase-receipt/{receipt.name}",
	}
