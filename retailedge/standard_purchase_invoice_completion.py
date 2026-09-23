from __future__ import annotations

from typing import Any

import frappe
from erpnext.controllers.sales_and_purchase_return import get_returned_qty_map_for_row
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	resolve_branch_from_warehouse,
)
from retailedge.guided_pricing import resolve_purchase_item_pricing
from retailedge.operating_context import get_operating_context, get_operational_branch_scope
from retailedge.professional_selling import _assert_read, _validate_stored_operational_branch
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness


PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
HANDOFF_DOCTYPE = "Supplier Document Purchase Invoice Handoff"
_LOCK_TABLE = "tabPurchase Invoice"
MAX_ITEM_SUMMARY = 10
MAX_DRAFT_QUEUE = 50
MAX_DRAFT_ITEMS = 100
SOURCE_MODE_DIRECT = "direct"
SOURCE_MODE_PROFESSIONAL_PURCHASING = "professional_purchasing"


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _get_purchase_invoice(name: str):
	name = _clean(name)
	if not name or not frappe.db.exists(PURCHASE_INVOICE_DOCTYPE, name):
		frappe.throw(_("Purchase Invoice {0} does not exist.").format(name or "(blank)"))
	doc = frappe.get_doc(PURCHASE_INVOICE_DOCTYPE, name)
	if not frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "read", doc=doc):
		frappe.throw(
			_("You do not have permission to read Purchase Invoice {0}.").format(name),
			frappe.PermissionError,
		)
	return doc


def _lock_purchase_invoice(name: str) -> None:
	rows = frappe.db.sql(
		f"SELECT name FROM `{_LOCK_TABLE}` WHERE name = %s FOR UPDATE",
		(_clean(name),),
	)
	if not rows:
		frappe.throw(_("Purchase Invoice {0} no longer exists.").format(name))


def _stored_branch(doc) -> str:
	return _clean(doc.get("branch") or doc.get("retailedge_branch"))


def _validate_invoice_context(doc) -> tuple[str, str]:
	company = _clean(doc.get("company"))
	if not company:
		frappe.throw(_("Purchase Invoice {0} has no Company.").format(doc.name))
	_assert_read("Company", company)

	invoice_branch = _validate_stored_operational_branch(
		company=company,
		branch=_stored_branch(doc),
		label=_("Purchase Invoice {0}").format(doc.name),
	)

	supplier = _clean(doc.get("supplier"))
	if not supplier:
		frappe.throw(_("Purchase Invoice Supplier is required."))
	_assert_read("Supplier", supplier)

	operating = get_operating_context() or {}
	operating_company = _clean(operating.get("company"))
	operating_branch = _clean(operating.get("branch"))
	if operating_company and operating_company != company:
		frappe.throw(
			_("Purchase Invoice {0} belongs to another Company. Change Operating Context before completing it.").format(
				doc.name
			),
			frappe.PermissionError,
		)
	if operating_branch and invoice_branch and operating_branch != invoice_branch:
		frappe.throw(
			_("Purchase Invoice {0} does not belong to the current Operating Branch.").format(doc.name),
			frappe.PermissionError,
		)
	return company, invoice_branch


def _has_supplier_document_handoff(doc) -> bool:
	if not frappe.db.exists("DocType", HANDOFF_DOCTYPE):
		return False
	return bool(frappe.db.exists(HANDOFF_DOCTYPE, {"purchase_invoice": doc.name}))


def _reference_names(doc, fieldname: str) -> set[str]:
	return {
		_clean(row.get(fieldname))
		for row in list(doc.get("items") or [])
		if _clean(row.get(fieldname))
	}


def _standard_invoice_blockers(doc) -> list[str]:
	blockers: list[str] = []
	if cint(doc.docstatus) != 0:
		blockers.append(_("Only draft Purchase Invoices can use standard EdgeSuite completion."))
	if doc.get("amended_from"):
		blockers.append(_("Amended Purchase Invoices require Advanced ERPNext review."))
	if cint(doc.get("is_return")) or _clean(doc.get("return_against")):
		blockers.append(_("Return / Supplier Debit Note completion requires Advanced ERPNext review."))
	if (
		cint(doc.get("is_internal_supplier"))
		or _clean(doc.get("represents_company"))
		or _clean(doc.get("inter_company_invoice_reference"))
	):
		blockers.append(_("Internal or inter-company Purchase Invoice requires Advanced ERPNext review."))
	if cint(doc.get("is_paid")):
		blockers.append(_("Paid-at-source Purchase Invoice requires Advanced ERPNext review."))
	if _clean(doc.get("is_opening")).lower() in {"yes", "1", "true"}:
		blockers.append(_("Opening Purchase Invoice requires Advanced ERPNext review."))
	if list(doc.get("advances") or []):
		blockers.append(_("Pre-allocated advances require Advanced ERPNext review."))
	if cint(doc.get("allocate_advances_automatically")):
		blockers.append(_("Automatic advance allocation requires Advanced ERPNext review."))
	if cint(doc.get("is_subcontracted")) or list(doc.get("supplied_items") or []):
		blockers.append(_("Subcontracting Purchase Invoice requires Advanced ERPNext review."))
	if not _clean(doc.get("supplier")):
		blockers.append(_("Purchase Invoice Supplier is required."))
	if not list(doc.get("items") or []):
		blockers.append(_("Purchase Invoice must contain at least one item."))
	return list(dict.fromkeys(blockers))


def _validate_source_less_context(doc) -> dict[str, Any]:
	blockers: list[str] = []
	purchase_orders = _reference_names(doc, "purchase_order")
	purchase_receipts = _reference_names(doc, "purchase_receipt")
	if purchase_orders or purchase_receipts:
		blockers.append(
			_(
				"Source-linked Purchase Invoices are owned by Professional Purchasing and require that workflow instead of generic completion."
			)
		)
	if _has_supplier_document_handoff(doc):
		blockers.append(
			_(
				"Supplier Document Purchase Invoice is owned by the immutable Supplier Document handoff workflow."
			)
		)
	return {
		"purchase_orders": sorted(purchase_orders),
		"purchase_receipts": sorted(purchase_receipts),
		"has_supplier_document_handoff": _has_supplier_document_handoff(doc),
		"blockers": list(dict.fromkeys(blockers)),
	}


def _validate_professional_purchasing_source_context(doc) -> dict[str, Any]:
	"""Validate one ERPNext-mapped PO/Receipt Purchase Invoice for EdgeSuite completion."""
	blockers: list[str] = []
	purchase_orders = _reference_names(doc, "purchase_order")
	purchase_receipts = _reference_names(doc, "purchase_receipt")

	if _has_supplier_document_handoff(doc):
		blockers.append(_("Supplier Document Purchase Invoice remains owned by its immutable handoff workflow."))

	source_type = ""
	source_name = ""
	if purchase_receipts:
		source_type = "Purchase Receipt"
		if len(purchase_receipts) == 1:
			source_name = next(iter(purchase_receipts))
		else:
			blockers.append(_("Standard Professional Purchasing completion supports one source Purchase Receipt at a time."))
		if cint(doc.get("update_stock")):
			blockers.append(_("A Purchase Receipt-linked Purchase Invoice cannot also Update Stock in the standard path."))
	elif purchase_orders:
		source_type = "Purchase Order"
		if len(purchase_orders) == 1:
			source_name = next(iter(purchase_orders))
		else:
			blockers.append(_("Standard Professional Purchasing completion supports one source Purchase Order at a time."))
	else:
		blockers.append(_("Professional Purchasing completion requires an ERPNext Purchase Order or Purchase Receipt source link."))

	source_branch = ""
	if source_name:
		if not frappe.db.exists(source_type, source_name):
			blockers.append(_("{0} {1} no longer exists.").format(source_type, source_name))
		else:
			source = frappe.get_doc(source_type, source_name)
			if not frappe.has_permission(source_type, "read", doc=source):
				frappe.throw(_("You do not have permission to read {0} {1}.").format(source_type, source_name), frappe.PermissionError)
			if cint(source.docstatus) != 1:
				blockers.append(_("{0} {1} is not submitted.").format(source_type, source_name))
			if _clean(source.get("company")) != _clean(doc.get("company")):
				blockers.append(_("Source document Company does not match the Purchase Invoice."))
			if _clean(source.get("supplier")) != _clean(doc.get("supplier")):
				blockers.append(_("Source document Supplier does not match the Purchase Invoice."))
			source_branch = _validate_stored_operational_branch(
				company=_clean(source.get("company")) or _clean(doc.get("company")),
				branch=_stored_branch(source),
				label=_("{0} {1}").format(source_type, source_name),
			)
			invoice_branch = _stored_branch(doc)
			if source_branch and invoice_branch and source_branch != invoice_branch:
				blockers.append(_("Source document Branch does not match the Purchase Invoice Branch."))

	return {
		"source_type": source_type,
		"source_name": source_name,
		"source_branch": source_branch,
		"purchase_orders": sorted(purchase_orders),
		"purchase_receipts": sorted(purchase_receipts),
		"has_supplier_document_handoff": _has_supplier_document_handoff(doc),
		"blockers": list(dict.fromkeys(blockers)),
	}


def _completion_source_context(doc, source_mode: str) -> dict[str, Any]:
	source_mode = _clean(source_mode) or SOURCE_MODE_DIRECT
	if source_mode == SOURCE_MODE_PROFESSIONAL_PURCHASING:
		return _validate_professional_purchasing_source_context(doc)
	if source_mode != SOURCE_MODE_DIRECT:
		frappe.throw(_("Unsupported Purchase Invoice completion source mode."), frappe.ValidationError)
	result = _validate_source_less_context(doc)
	return {
		**result,
		"source_type": "",
		"source_name": "",
		"source_branch": "",
	}


def _validate_purchase_item_access(doc) -> list[str]:
	blockers: list[str] = []
	for index, row in enumerate(list(doc.get("items") or []), start=1):
		item_code = _clean(row.get("item_code"))
		if not item_code:
			blockers.append(_("Item is missing on Purchase Invoice row {0}.").format(index))
			continue
		_assert_read("Item", item_code)
	return blockers


def _validate_stock_context(
	doc,
	*,
	company: str,
	invoice_branch: str,
) -> dict[str, Any]:
	if not cint(doc.get("update_stock")):
		return {
			"mode": "accounting_only",
			"default_warehouse": _clean(doc.get("set_warehouse")),
			"warehouse_branch": "",
			"effective_branch": invoice_branch,
			"blockers": [],
		}

	blockers: list[str] = []
	resolved_branches: set[str] = set()
	warehouses: set[str] = set()
	for row in list(doc.get("items") or []):
		warehouse = _clean(row.get("warehouse"))
		if warehouse:
			warehouses.add(warehouse)
		if not warehouse:
			blockers.append(_("Every stock-updating Purchase Invoice item must have a Warehouse."))
			continue

		if (
			_clean(row.get("serial_no"))
			or _clean(row.get("batch_no"))
			or _clean(row.get("serial_and_batch_bundle"))
		):
			blockers.append(
				_("Serial/Batch controlled stock-updating Purchase Invoice requires Advanced ERPNext review.")
			)

		_assert_read("Warehouse", warehouse)
		warehouse_company = _clean(frappe.db.get_value("Warehouse", warehouse, "company"))
		if warehouse_company and warehouse_company != company:
			blockers.append(
				_("Warehouse {0} does not belong to Company {1}.").format(warehouse, company)
			)
			continue

		resolved = resolve_branch_from_warehouse(warehouse, company=company)
		warehouse_branch = _clean(resolved.get("branch"))
		if not warehouse_branch:
			blockers.append(
				_("Warehouse {0} is not mapped to an operational Branch; use Advanced ERPNext review.").format(
					warehouse
				)
			)
			continue
		warehouse_branch = _validate_stored_operational_branch(
			company=company,
			branch=warehouse_branch,
			label=_("Purchase Invoice Warehouse {0}").format(warehouse),
		)
		resolved_branches.add(warehouse_branch)

	if len(resolved_branches) > 1:
		blockers.append(_("The Purchase Invoice spans Warehouses from multiple operational Branches."))

	warehouse_branch = next(iter(resolved_branches), "") if len(resolved_branches) == 1 else ""
	effective_branch = invoice_branch or warehouse_branch
	if warehouse_branch and effective_branch and warehouse_branch != effective_branch:
		blockers.append(_("Warehouse Branch does not match the Purchase Invoice Branch."))

	operating = get_operating_context() or {}
	operating_branch = _clean(operating.get("branch"))
	if operating_branch and effective_branch and operating_branch != effective_branch:
		frappe.throw(
			_("The Purchase Invoice stock context does not match the current Operating Branch."),
			frappe.PermissionError,
		)

	default_warehouse = _clean(doc.get("set_warehouse")) or (next(iter(warehouses), "") if len(warehouses) == 1 else "")
	return {
		"mode": "update_stock",
		"default_warehouse": default_warehouse,
		"warehouse_branch": warehouse_branch,
		"effective_branch": effective_branch,
		"blockers": list(dict.fromkeys(blockers)),
	}


def _purchase_invoice_has_returnable_items(doc) -> bool:
	if cint(doc.docstatus) != 1 or cint(doc.get("is_return")):
		return False
	supplier = _clean(doc.get("supplier"))
	if not supplier:
		return False
	for row in list(doc.get("items") or []):
		row_name = _clean(row.get("name"))
		qty = flt(row.get("qty"))
		if not row_name or qty <= 0:
			continue
		returned = get_returned_qty_map_for_row(doc.name, supplier, row_name, PURCHASE_INVOICE_DOCTYPE) or {}
		if qty - flt(returned.get("qty")) > 0.000001:
			return True
	return False


def _can_open_page(page_name: str) -> bool:
	try:
		if not frappe.db.exists("Page", page_name):
			return False
		return bool(frappe.get_doc("Page", page_name).is_permitted())
	except Exception:
		return False


def _submitted_next_actions(doc) -> list[dict[str, str]]:
	"""Return safe next business actions for one submitted payable Purchase Invoice."""
	if cint(doc.docstatus) != 1 or cint(doc.get("is_return")):
		return []

	actions: list[dict[str, str]] = []
	if frappe.has_permission("Payment Entry", "create") and flt(doc.get("outstanding_amount")) > 0.005:
		actions.append({"value": "pay-supplier", "label": _("Pay Supplier")})
	if (
		frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "create")
		and _can_open_page("professional-purchasing")
		and _purchase_invoice_has_returnable_items(doc)
	):
		actions.append({"value": "create-supplier-debit-note", "label": _("Supplier Debit Note")})
	return actions


def _source_locked_purchase_item(row) -> bool:
	return any(
		_clean(row.get(fieldname))
		for fieldname in ("purchase_order", "po_detail", "purchase_receipt", "pr_detail")
	)


def _editable_purchase_items(doc) -> list[dict[str, Any]]:
	return [
		{
			"name": _clean(row.get("name")),
			"item_code": _clean(row.get("item_code")),
			"item_name": _clean(row.get("item_name")),
			"qty": flt(row.get("qty")),
			"rate": flt(row.get("rate")),
			"amount": flt(row.get("amount")),
			"warehouse": _clean(row.get("warehouse")),
			"source_locked": _source_locked_purchase_item(row),
		}
		for row in list(doc.get("items") or [])
	]


def _resolve_purchase_rate(*, item_code: str, company: str, supplier: str, branch: str, warehouse: str, posting_date: str, qty: float, selected_price_list: str = "") -> float:
	resolved = resolve_purchase_item_pricing(
		item_code=item_code,
		company=company,
		supplier=supplier,
		branch=branch,
		warehouse=warehouse,
		posting_date=posting_date,
		qty=qty,
		selected_price_list=selected_price_list,
		user=frappe.session.user,
	)
	rate = resolved.get("rate")
	if rate is None:
		frappe.throw(
			_("No buying price could be resolved for Item {0}. Enter the agreed buying rate before saving.").format(item_code)
		)
	return flt(rate)


def _update_purchase_draft_items(doc, requested_items: Any, *, source_mode: str, company: str, branch: str) -> None:
	if isinstance(requested_items, str):
		requested_items = frappe.parse_json(requested_items)
	if not isinstance(requested_items, list) or not requested_items:
		frappe.throw(_("Add at least one purchase item."))
	if len(requested_items) > MAX_DRAFT_ITEMS:
		frappe.throw(_("A Purchase Invoice draft can contain at most {0} items here.").format(MAX_DRAFT_ITEMS))

	current_rows = {
		_clean(row.get("name")): row
		for row in list(doc.get("items") or [])
		if _clean(row.get("name"))
	}
	requested_existing: set[str] = set()
	professional_source = (_clean(source_mode) == SOURCE_MODE_PROFESSIONAL_PURCHASING)
	default_warehouse = _clean(doc.get("set_warehouse"))
	supplier = _clean(doc.get("supplier"))
	posting_date = _clean(doc.get("posting_date"))
	buying_price_list = _clean(doc.get("buying_price_list"))

	for index, item in enumerate(requested_items, start=1):
		if not isinstance(item, dict):
			frappe.throw(_("Purchase item row {0} is invalid.").format(index))
		row_name = _clean(item.get("name"))
		if row_name:
			row = current_rows.get(row_name)
			if not row:
				frappe.throw(_("Purchase item row {0} is no longer part of this draft. Refresh and try again.").format(index))
			if row_name in requested_existing:
				frappe.throw(_("Purchase item row {0} is repeated.").format(index))
			requested_existing.add(row_name)
			requested_code = _clean(item.get("item_code"))
			if requested_code and requested_code != _clean(row.get("item_code")):
				frappe.throw(_("Existing purchase item identity cannot be replaced here."))
			qty = flt(item.get("qty"))
			if qty <= 0:
				frappe.throw(_("Quantity on purchase row {0} must be greater than zero.").format(index))
			rate_value = item.get("rate")
			rate = _resolve_purchase_rate(
				item_code=_clean(row.get("item_code")),
				company=company,
				supplier=supplier,
				branch=branch,
				warehouse=_clean(row.get("warehouse")) or default_warehouse,
				posting_date=posting_date,
				qty=qty,
				selected_price_list=buying_price_list,
			) if rate_value in (None, "") else flt(rate_value)
			if rate < 0:
				frappe.throw(_("Buying Rate on purchase row {0} cannot be negative.").format(index))
			row.qty = qty
			row.rate = rate
			continue

		if professional_source:
			frappe.throw(_("Source-linked Purchase Invoice items cannot be added from standard completion. Continue from the owning Purchase Order or Purchase Receipt."))
		item_code = _clean(item.get("item_code"))
		if not item_code:
			frappe.throw(_("Item is required on new purchase row {0}.").format(index))
		if cint(doc.get("update_stock")) and not default_warehouse:
			frappe.throw(_("A Receiving Stock Location is required before adding items to this stock-updating Purchase Invoice."))
		_assert_read("Item", item_code)
		qty = flt(item.get("qty"))
		if qty <= 0:
			frappe.throw(_("Quantity on purchase row {0} must be greater than zero.").format(index))
		rate_value = item.get("rate")
		rate = _resolve_purchase_rate(
			item_code=item_code,
			company=company,
			supplier=supplier,
			branch=branch,
			warehouse=default_warehouse,
			posting_date=posting_date,
			qty=qty,
			selected_price_list=buying_price_list,
		) if rate_value in (None, "") else flt(rate_value)
		if rate < 0:
			frappe.throw(_("Buying Rate on purchase row {0} cannot be negative.").format(index))
		row = {"item_code": item_code, "qty": qty, "rate": rate}
		if default_warehouse:
			row["warehouse"] = default_warehouse
		doc.append("items", row)

	for row_name, row in list(current_rows.items()):
		if row_name in requested_existing:
			continue
		if professional_source or _source_locked_purchase_item(row):
			frappe.throw(_("Source-linked purchase items cannot be removed from standard completion."))
		doc.remove(row)

	if hasattr(doc, "set_missing_values"):
		doc.set_missing_values()


def _item_summary(doc) -> list[dict[str, Any]]:
	result: list[dict[str, Any]] = []
	for row in list(doc.get("items") or [])[:MAX_ITEM_SUMMARY]:
		result.append(
			{
				"item_code": _clean(row.get("item_code")),
				"item_name": _clean(row.get("item_name")),
				"qty": flt(row.get("qty")),
				"rate": flt(row.get("rate")),
				"amount": flt(row.get("amount")),
				"warehouse": _clean(row.get("warehouse")),
			}
		)
	return result


def _build_preview(doc, *, source_mode: str = SOURCE_MODE_DIRECT) -> dict[str, Any]:
	company, invoice_branch = _validate_invoice_context(doc)
	blockers = _standard_invoice_blockers(doc)
	blockers.extend(_validate_purchase_item_access(doc))
	source_context = _completion_source_context(doc, source_mode)
	blockers.extend(source_context["blockers"])
	stock_context = _validate_stock_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
	)
	blockers.extend(stock_context["blockers"])
	blockers = list(dict.fromkeys(blockers))
	edit_blockers = list(blockers)

	workflow_readiness = get_workflow_readiness(
		doctype=PURCHASE_INVOICE_DOCTYPE,
		doc=doc,
	)
	workflow_controlled = _clean(workflow_readiness.get("source")) == "frappe"

	if (
		not workflow_controlled
		and not blockers
		and not frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "submit", doc=doc)
	):
		blockers.append(_("You do not have permission to submit this Purchase Invoice."))

	return {
		"doctype": PURCHASE_INVOICE_DOCTYPE,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or ("Draft" if cint(doc.docstatus) == 0 else ""),
		"company": company,
		"branch": stock_context["effective_branch"] or invoice_branch,
		"supplier": _clean(doc.get("supplier")),
		"supplier_name": _clean(doc.get("supplier_name")) or _clean(doc.get("supplier")),
		"buying_price_list": _clean(doc.get("buying_price_list")),
		"currency": _clean(doc.get("currency")),
		"grand_total": flt(doc.get("grand_total")),
		"outstanding_amount": flt(doc.get("outstanding_amount")),
		"next_actions": _submitted_next_actions(doc),
		"posting_date": _clean(doc.get("posting_date")),
		"due_date": _clean(doc.get("due_date")),
		"bill_no": _clean(doc.get("bill_no")),
		"bill_date": _clean(doc.get("bill_date")),
		"remarks": _clean(doc.get("remarks")),
		"can_edit": bool(cint(doc.docstatus) == 0 and not edit_blockers and frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "write", doc=doc)),
		"editable_items": _editable_purchase_items(doc),
		"allow_new_items": bool(
			(_clean(source_mode) or SOURCE_MODE_DIRECT) == SOURCE_MODE_DIRECT
			and (not cint(doc.get("update_stock")) or _clean(doc.get("set_warehouse")))
		),
		"update_stock": bool(cint(doc.get("update_stock"))),
		"completion_mode": stock_context["mode"],
		"default_warehouse": stock_context.get("default_warehouse") or "",
		"source_mode": _clean(source_mode) or SOURCE_MODE_DIRECT,
		"source_type": source_context.get("source_type") or "",
		"source_name": source_context.get("source_name") or "",
		"item_count": len(list(doc.get("items") or [])),
		"items": _item_summary(doc),
		"blockers": blockers,
		"can_submit": bool(not blockers and not workflow_controlled and cint(doc.docstatus) == 0),
		"workflow_readiness": workflow_readiness,
		"workflow_eligible": bool(
			workflow_controlled
			and not blockers
			and cint(doc.docstatus) == 0
		),
		"persistence": "none",
		"source_of_truth": "ERPNext Purchase Invoice",
		"route": f"/app/purchase-invoice/{doc.name}",
	}


def _assert_expected_modified(doc, expected_modified: str | None) -> str:
	expected_modified = _clean(expected_modified)
	if not expected_modified:
		frappe.throw(
			_("The reviewed Purchase Invoice version is required. Refresh completion review."),
			frappe.TimestampMismatchError,
		)
	try:
		expected = get_datetime(expected_modified)
		current = get_datetime(doc.modified)
	except Exception:
		frappe.throw(_("Invalid reviewed Purchase Invoice version."), frappe.ValidationError)
	if expected != current:
		frappe.throw(
			_("Purchase Invoice {0} changed after completion review. Refresh before continuing.").format(
				doc.name
			),
			frappe.TimestampMismatchError,
		)
	return expected_modified


def _sync_purchase_due_date_with_payment_schedule(doc, due_value) -> None:
	if not due_value or not doc.meta.has_field("payment_schedule"):
		return
	schedule = list(doc.get("payment_schedule") or [])
	if not schedule:
		return
	if len(schedule) == 1 and not _clean(doc.get("payment_terms_template")):
		schedule[0].due_date = due_value
		return
	current_due_dates = [getdate(row.due_date) for row in schedule if row.get("due_date")]
	current_due_date = max(current_due_dates) if current_due_dates else None
	if current_due_date == due_value:
		return
	frappe.throw(
		_("Due Date is controlled by this invoice's Payment Terms schedule. Use Advanced ERPNext to change the payment schedule safely."),
		frappe.ValidationError,
	)


@frappe.whitelist(methods=["POST"])
def update_standard_purchase_invoice_draft(
	name: str,
	values: dict | str | None = None,
	expected_modified: str | None = None,
	source_mode: str = SOURCE_MODE_DIRECT,
) -> dict[str, Any]:
	"""Update a bounded set of fields on one draft Purchase Invoice.

	Company, Supplier, Branch, Update Stock, warehouses and all PO/Receipt source
	links stay immutable here. ERPNext remains authoritative for totals, taxes,
	payment terms, source-quantity controls and buying validation on save.
	"""
	name = _clean(name)
	_lock_purchase_invoice(name)
	doc = _get_purchase_invoice(name)
	_assert_expected_modified(doc, expected_modified)
	company, branch = _validate_invoice_context(doc)
	if cint(doc.docstatus) != 0:
		frappe.throw(_("Only draft Purchase Invoices can be edited here."), frappe.ValidationError)
	if not frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "write", doc=doc):
		frappe.throw(_("You do not have permission to edit this Purchase Invoice."), frappe.PermissionError)

	source_context = _completion_source_context(doc, source_mode)
	blockers = _standard_invoice_blockers(doc)
	blockers.extend(_validate_purchase_item_access(doc))
	blockers.extend(source_context.get("blockers") or [])
	stock_context = _validate_stock_context(doc, company=company, invoice_branch=branch)
	blockers.extend(stock_context.get("blockers") or [])
	blockers = list(dict.fromkeys(blockers))
	if blockers:
		frappe.throw(
			_("Purchase Invoice draft editing is blocked:\n- {0}").format("\n- ".join(blockers)),
			frappe.ValidationError,
		)

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if values is None:
		values = {}
	if not isinstance(values, dict):
		frappe.throw(_("Invalid Purchase Invoice draft changes."), frappe.ValidationError)

	posting_text = _clean(values.get("posting_date") or doc.get("posting_date"))
	due_text = _clean(values.get("due_date") or doc.get("due_date"))
	if not posting_text:
		frappe.throw(_("Posting Date is required."), frappe.ValidationError)
	try:
		posting_value = getdate(posting_text)
		due_value = getdate(due_text) if due_text else None
	except Exception:
		frappe.throw(_("Enter valid Posting Date and Due Date values."), frappe.ValidationError)
	if due_value and due_value < posting_value:
		frappe.throw(_("Due Date cannot be before Posting Date."), frappe.ValidationError)

	doc.set("posting_date", posting_value)
	if doc.meta.has_field("due_date") and due_value:
		doc.set("due_date", due_value)
		_sync_purchase_due_date_with_payment_schedule(doc, due_value)
	if doc.meta.has_field("bill_no"):
		doc.set("bill_no", _clean(values.get("bill_no")))
	if doc.meta.has_field("bill_date"):
		bill_text = _clean(values.get("bill_date"))
		doc.set("bill_date", getdate(bill_text) if bill_text else None)
	if doc.meta.has_field("remarks"):
		doc.set("remarks", _clean(values.get("remarks")))

	if values.get("items") is not None:
		_update_purchase_draft_items(
			doc,
			values.get("items"),
			source_mode=source_mode,
			company=company,
			branch=branch,
		)

	# ERPNext owns buying defaults, taxes, totals, source quantity constraints and
	# accounting validation. Saving this draft posts no GL or stock ledger.
	doc.save()
	doc.reload()
	result = _build_preview(doc, source_mode=source_mode)
	result["persistence"] = "draft_update"
	return result


def _queue_filters(*, company: str, branch: str, supplier: str) -> dict[str, Any]:
	filters: dict[str, Any] = {
		"docstatus": 0,
		"company": company,
		"is_return": 0,
	}
	if supplier:
		filters["supplier"] = supplier

	branch_field = get_first_existing_field(PURCHASE_INVOICE_DOCTYPE, BRANCH_FIELD_CANDIDATES)
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if branch:
		validated_branch = _validate_stored_operational_branch(
			company=company,
			branch=branch,
			label=_("Purchase Invoice draft queue"),
		)
		if branch_field:
			filters[branch_field] = validated_branch
		elif scope["restricted"]:
			filters["name"] = "__never__"
	elif scope["restricted"]:
		if not scope["allowed_branches"] or not branch_field:
			filters["name"] = "__never__"
		else:
			filters[branch_field] = ["in", scope["allowed_branches"]]
	return filters


def _eligible_queue_row(doc) -> bool:
	try:
		company, invoice_branch = _validate_invoice_context(doc)
		blockers = _standard_invoice_blockers(doc)
		blockers.extend(_validate_purchase_item_access(doc))
		blockers.extend(_validate_source_less_context(doc)["blockers"])
		blockers.extend(
			_validate_stock_context(
				doc,
				company=company,
				invoice_branch=invoice_branch,
			)["blockers"]
		)
		return not blockers
	except Exception:
		return False


@frappe.whitelist()
def get_standard_purchase_invoice_completion_queue(
	company: str | None = None,
	branch: str | None = None,
	supplier: str | None = None,
	limit: int | str = 20,
) -> dict[str, Any]:
	if not frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "read"):
		frappe.throw(
			_("You do not have permission to read Purchase Invoices."),
			frappe.PermissionError,
		)

	operating = get_operating_context() or {}
	company = _clean(company) or _clean(operating.get("company")) or _clean(
		frappe.defaults.get_user_default("Company")
	)
	if not company:
		frappe.throw(_("Choose an Operating Company before reviewing Purchase Invoice drafts."))
	_assert_read("Company", company)

	branch = _clean(branch) or _clean(operating.get("branch"))
	supplier = _clean(supplier)
	if supplier:
		_assert_read("Supplier", supplier)

	row_limit = max(1, min(cint(limit) or 20, MAX_DRAFT_QUEUE))
	branch_field = get_first_existing_field(PURCHASE_INVOICE_DOCTYPE, BRANCH_FIELD_CANDIDATES)
	fields = [
		"name",
		"supplier",
		"supplier_name",
		"posting_date",
		"grand_total",
		"currency",
		"update_stock",
		"modified",
	]
	if branch_field:
		fields.append(branch_field)

	rows = frappe.get_list(
		PURCHASE_INVOICE_DOCTYPE,
		filters=_queue_filters(company=company, branch=branch, supplier=supplier),
		fields=fields,
		order_by="modified desc, name desc",
		limit_page_length=row_limit,
	)

	result: list[dict[str, Any]] = []
	for row in rows:
		try:
			doc = frappe.get_doc(PURCHASE_INVOICE_DOCTYPE, row.get("name"))
			if not frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "read", doc=doc):
				continue
			if not _eligible_queue_row(doc):
				continue
			result.append(
				{
					"name": doc.name,
					"supplier": _clean(doc.get("supplier")),
					"supplier_name": _clean(doc.get("supplier_name")) or _clean(doc.get("supplier")),
					"company": _clean(doc.get("company")),
					"branch": _stored_branch(doc),
					"posting_date": doc.get("posting_date"),
					"grand_total": flt(doc.get("grand_total")),
					"currency": _clean(doc.get("currency")),
					"update_stock": bool(cint(doc.get("update_stock"))),
					"modified": _clean(doc.get("modified")),
				}
			)
		except Exception:
			continue

	return {
		"company": company,
		"branch": branch,
		"supplier": supplier,
		"rows": result,
		"limit": row_limit,
		"source_of_truth": "ERPNext draft Purchase Invoice",
	}


@frappe.whitelist()
def get_standard_purchase_invoice_completion_preview(
	name: str,
	source_mode: str = SOURCE_MODE_DIRECT,
) -> dict[str, Any]:
	"""Return a persistence-free review for one governed standard Purchase Invoice."""
	doc = _get_purchase_invoice(name)
	return _build_preview(doc, source_mode=source_mode)


@frappe.whitelist(methods=["POST"])
def submit_standard_purchase_invoice(
	name: str,
	expected_modified: str | None = None,
	source_mode: str = SOURCE_MODE_DIRECT,
) -> dict[str, Any]:
	"""Submit one reviewed generic Purchase Invoice through native ERPNext."""
	name = _clean(name)
	_lock_purchase_invoice(name)
	doc = _get_purchase_invoice(name)
	_assert_expected_modified(doc, expected_modified)
	company, invoice_branch = _validate_invoice_context(doc)

	blockers = _standard_invoice_blockers(doc)
	blockers.extend(_validate_purchase_item_access(doc))
	source_context = _completion_source_context(doc, source_mode)
	blockers.extend(source_context["blockers"])
	stock_context = _validate_stock_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
	)
	blockers.extend(stock_context["blockers"])
	if blockers:
		frappe.throw("<br>".join(list(dict.fromkeys(blockers))))

	workflow_readiness = get_workflow_readiness(
		doctype=PURCHASE_INVOICE_DOCTYPE,
		doc=doc,
	)
	if _clean(workflow_readiness.get("source")) == "frappe":
		frappe.throw(
			_(
				"Purchase Invoice is controlled by active Workflow {0}. Use the available workflow action in EdgeSuite."
			).format(workflow_readiness.get("workflow") or _("Frappe Workflow")),
			frappe.ValidationError,
		)

	if not frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "submit", doc=doc):
		frappe.throw(
			_("You do not have permission to submit this Purchase Invoice."),
			frappe.PermissionError,
		)

	# ERPNext remains authoritative for payable, tax, GL, Payment Ledger,
	# outstanding and Stock Ledger / valuation when update_stock is enabled.
	doc.submit()
	if cint(doc.docstatus) != 1:
		frappe.throw(_("ERPNext did not submit Purchase Invoice {0}.").format(name))
	doc.reload()
	return {
		"doctype": PURCHASE_INVOICE_DOCTYPE,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or "Submitted",
		"company": _clean(doc.get("company")),
		"branch": _stored_branch(doc) or stock_context["effective_branch"],
		"source_mode": _clean(source_mode) or SOURCE_MODE_DIRECT,
		"source_type": source_context.get("source_type") or "",
		"source_name": source_context.get("source_name") or "",
		"supplier": _clean(doc.get("supplier")),
		"supplier_name": _clean(doc.get("supplier_name")) or _clean(doc.get("supplier")),
		"outstanding_amount": flt(doc.get("outstanding_amount")),
		"next_actions": _submitted_next_actions(doc),
		"update_stock": bool(cint(doc.get("update_stock"))),
		"source_of_truth": "ERPNext native submit",
		"route": f"/app/purchase-invoice/{doc.name}",
	}


@frappe.whitelist(methods=["POST"])
def apply_standard_purchase_invoice_workflow_action(
	name: str,
	action: str,
	expected_modified: str | None = None,
	expected_workflow_state: str | None = None,
	source_mode: str = SOURCE_MODE_DIRECT,
) -> dict[str, Any]:
	"""Apply one Frappe Workflow action to a reviewed generic Purchase Invoice."""
	name = _clean(name)
	action = _clean(action)
	if not action:
		frappe.throw(_("Workflow action is required."))

	_lock_purchase_invoice(name)
	doc = _get_purchase_invoice(name)
	expected_modified = _assert_expected_modified(doc, expected_modified)
	company, invoice_branch = _validate_invoice_context(doc)

	blockers = _standard_invoice_blockers(doc)
	blockers.extend(_validate_purchase_item_access(doc))
	source_context = _completion_source_context(doc, source_mode)
	blockers.extend(source_context["blockers"])
	stock_context = _validate_stock_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
	)
	blockers.extend(stock_context["blockers"])
	if blockers:
		frappe.throw("<br>".join(list(dict.fromkeys(blockers))))

	workflow_readiness = get_workflow_readiness(
		doctype=PURCHASE_INVOICE_DOCTYPE,
		doc=doc,
	)
	if _clean(workflow_readiness.get("source")) != "frappe":
		frappe.throw(
			_("No active Frappe Workflow owns this Purchase Invoice."),
			frappe.ValidationError,
		)

	result = apply_document_workflow_action(
		doctype=PURCHASE_INVOICE_DOCTYPE,
		name=name,
		action=action,
		expected_modified=expected_modified,
		expected_state=str(expected_workflow_state or ""),
	)
	if cint(result.get("docstatus")) == 1:
		current = _get_purchase_invoice(name)
		result.update(
			{
				"company": _clean(current.get("company")),
				"branch": _stored_branch(current) or stock_context["effective_branch"],
				"source_mode": _clean(source_mode) or SOURCE_MODE_DIRECT,
				"source_type": source_context.get("source_type") or "",
				"source_name": source_context.get("source_name") or "",
				"supplier": _clean(current.get("supplier")),
				"supplier_name": _clean(current.get("supplier_name")) or _clean(current.get("supplier")),
				"outstanding_amount": flt(current.get("outstanding_amount")),
				"next_actions": _submitted_next_actions(current),
				"source_of_truth": "Frappe Workflow / ERPNext Purchase Invoice",
			}
		)
	return result
