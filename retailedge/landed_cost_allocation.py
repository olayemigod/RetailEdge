from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_lcv

from retailedge.professional_purchasing import (
	MAX_LINK_RESULTS,
	SUPPLIER_DOCTYPE,
	_assert_create,
	_assert_read,
	_branch_scoped_filters,
	_permission,
	_resolve_scope,
	_validate_native_purchase_return_source,
)

LANDED_COST_VOUCHER_DOCTYPE = "Landed Cost Voucher"
PURCHASE_RECEIPT_DOCTYPE = "Purchase Receipt"
PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
SUPPORTED_SOURCE_TYPES = {
	"purchase_receipt": PURCHASE_RECEIPT_DOCTYPE,
	"purchase_invoice": PURCHASE_INVOICE_DOCTYPE,
}
SUPPORTED_DISTRIBUTION_METHODS = {"Amount", "Qty", "Distribute Manually"}


def _source_doctype(source_type: str) -> str:
	key = str(source_type or "").strip().lower()
	doctype = SUPPORTED_SOURCE_TYPES.get(key)
	if not doctype:
		frappe.throw(_("Unsupported landed cost source type."))
	return doctype


def _distribution_method(value: str | None) -> str:
	method = str(value or "Amount").strip() or "Amount"
	if method not in SUPPORTED_DISTRIBUTION_METHODS:
		frappe.throw(_("Unsupported landed cost distribution method."))
	return method


def _assert_landed_cost_permissions(source_doctype: str) -> None:
	if not _permission(source_doctype, "read"):
		frappe.throw(
			_("You do not have permission to read {0}.").format(_(source_doctype)),
			frappe.PermissionError,
		)
	_assert_create(LANDED_COST_VOUCHER_DOCTYPE)


def _validate_source(source: Any, source_doctype: str) -> tuple[str, str]:
	company, branch = _validate_native_purchase_return_source(
		source,
		source_label=source_doctype,
	)
	if source_doctype == PURCHASE_INVOICE_DOCTYPE and not cint(getattr(source, "update_stock", 0)):
		frappe.throw(
			_("Only submitted Purchase Invoices with Update Stock enabled can be used for guided landed cost allocation.")
		)
	return company, branch


@frappe.whitelist()
def get_landed_cost_capability() -> dict[str, Any]:
	"""Return permission-aware C18 capability for the EdgeSuite purchasing workspace."""
	can_create_lcv = _permission(LANDED_COST_VOUCHER_DOCTYPE, "create")
	can_use_purchase_receipt = bool(can_create_lcv and _permission(PURCHASE_RECEIPT_DOCTYPE, "read"))
	can_use_purchase_invoice = bool(can_create_lcv and _permission(PURCHASE_INVOICE_DOCTYPE, "read"))
	return {
		"can_prepare_landed_cost": bool(can_use_purchase_receipt or can_use_purchase_invoice),
		"can_use_purchase_receipt": can_use_purchase_receipt,
		"can_use_purchase_invoice": can_use_purchase_invoice,
		"distribution_methods": ["Amount", "Qty", "Distribute Manually"],
		"source_of_truth": "ERPNext Purchase Receipt make_lcv and Landed Cost Voucher",
	}


@frappe.whitelist()
def search_landed_cost_sources(
	source_type: str,
	txt: str = "",
	company: str | None = None,
	branch: str | None = None,
	supplier: str | None = None,
) -> list[dict[str, Any]]:
	"""Search submitted purchase-side stock receipts inside authorised operating scope."""
	doctype = _source_doctype(source_type)
	_assert_landed_cost_permissions(doctype)

	resolved_company, resolved_branch, allowed, global_access = _resolve_scope(
		company=company,
		branch=branch,
	)
	filters, _branch_field = _branch_scoped_filters(
		doctype,
		company=resolved_company,
		branch=resolved_branch,
		allowed_branches=allowed,
		global_branch_access=global_access,
	)
	filters.update({"docstatus": 1, "is_return": 0})
	if doctype == PURCHASE_INVOICE_DOCTYPE:
		filters["update_stock"] = 1

	supplier = str(supplier or "").strip()
	if supplier:
		_assert_read(SUPPLIER_DOCTYPE, supplier)
		filters["supplier"] = supplier

	return list(
		search_link(
			doctype,
			str(txt or "").strip(),
			filters=filters,
			page_length=MAX_LINK_RESULTS,
			reference_doctype=LANDED_COST_VOUCHER_DOCTYPE,
			link_fieldname="receipt_document",
		)
	)


@frappe.whitelist(methods=["POST"])
def prepare_landed_cost_voucher_draft(
	source_type: str,
	source_name: str,
	distribution_method: str | None = None,
) -> dict[str, Any]:
	"""Prepare one native ERPNext Landed Cost Voucher locally, without persistence."""
	doctype = _source_doctype(source_type)
	method = _distribution_method(distribution_method)
	source_name = str(source_name or "").strip()
	if not source_name:
		frappe.throw(_("Landed cost source document is required."))

	_assert_read(doctype, source_name)
	_assert_create(LANDED_COST_VOUCHER_DOCTYPE)
	source = frappe.get_doc(doctype, source_name)
	company, branch = _validate_source(source, doctype)

	# ERPNext's own Purchase Receipt/Purchase Invoice Create > Landed Cost Voucher
	# handoff builds an unsaved LCV and maps authoritative receipt items. Keeping
	# this document unsaved is essential because landed-cost charge rows are
	# mandatory and must be entered/reviewed on the native ERPNext form first.
	landed_cost_voucher = frappe._dict(make_lcv(doctype, source.name) or {})
	if landed_cost_voucher.get("doctype") != LANDED_COST_VOUCHER_DOCTYPE:
		frappe.throw(_("ERPNext could not prepare a Landed Cost Voucher."))
	if cint(landed_cost_voucher.get("docstatus")) != 0:
		frappe.throw(_("ERPNext returned a non-draft Landed Cost Voucher; preparation was stopped."))
	if str(landed_cost_voucher.get("company") or "") != company:
		frappe.throw(_("Mapped Landed Cost Voucher Company does not match the selected source."))

	receipt_rows = list(landed_cost_voucher.get("purchase_receipts") or [])
	if len(receipt_rows) != 1:
		frappe.throw(_("Guided landed cost preparation must contain exactly one source document."))
	receipt_row = receipt_rows[0]
	if str(receipt_row.get("receipt_document_type") or "") != doctype:
		frappe.throw(_("Mapped Landed Cost Voucher source type does not match the selected document."))
	if str(receipt_row.get("receipt_document") or "") != source.name:
		frappe.throw(_("Mapped Landed Cost Voucher source does not match the selected document."))
	if str(receipt_row.get("supplier") or "") != str(getattr(source, "supplier", "") or ""):
		frappe.throw(_("Mapped Landed Cost Voucher Supplier does not match the selected source."))

	items = list(landed_cost_voucher.get("items") or [])
	if not items:
		frappe.throw(_("The selected source has no items available for landed cost allocation."))

	landed_cost_voucher["distribute_charges_based_on"] = method
	return {
		"doctype": LANDED_COST_VOUCHER_DOCTYPE,
		"docstatus": 0,
		"company": company,
		"branch": branch,
		"supplier": str(getattr(source, "supplier", "") or ""),
		"source_type": doctype,
		"source_name": source.name,
		"distribution_method": method,
		"item_count": len(items),
		"persisted": False,
		"posting_status": "Unsaved Draft",
		"document": landed_cost_voucher,
		"source_of_truth": "ERPNext Purchase Receipt make_lcv and native Landed Cost Voucher form",
	}
