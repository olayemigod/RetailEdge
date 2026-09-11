from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt

from erpnext.stock.doctype.landed_cost_voucher.landed_cost_voucher import get_lcv_dimension_fields
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
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness

LANDED_COST_VOUCHER_DOCTYPE = "Landed Cost Voucher"
PURCHASE_RECEIPT_DOCTYPE = "Purchase Receipt"
PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
SUPPORTED_SOURCE_TYPES = {
	"purchase_receipt": PURCHASE_RECEIPT_DOCTYPE,
	"purchase_invoice": PURCHASE_INVOICE_DOCTYPE,
}
SUPPORTED_DISTRIBUTION_METHODS = {"Amount", "Qty", "Distribute Manually"}
STANDARD_DISTRIBUTION_METHODS = {"Amount", "Qty"}
MAX_STANDARD_LANDED_COST_CHARGES = 20
_ALLOWED_STANDARD_CHARGE_KEYS = {"expense_account", "description", "amount"}
ALLOWED_LANDED_COST_ACCOUNT_TYPES = {
	"Tax",
	"Chargeable",
	"Income Account",
	"Expenses Included In Valuation",
	"Expenses Included In Asset Valuation",
	"Expense Account",
	"Direct Expense",
	"Indirect Expense",
	"Stock Received But Not Billed",
}


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


def _standard_distribution_method(value: str | None) -> str:
	method = _distribution_method(value)
	if method not in STANDARD_DISTRIBUTION_METHODS:
		frappe.throw(
			_(
				"Manual landed-cost distribution is an Advanced ERPNext workflow. Use Amount or Qty in the standard EdgeSuite flow."
			)
		)
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
			_(
				"Only submitted Purchase Invoices with Update Stock enabled can be used for guided landed cost allocation."
			)
		)
	return company, branch


def _get_source(source_type: str, source_name: str, *, lock: bool = False) -> tuple[str, Any, str, str]:
	doctype = _source_doctype(source_type)
	source_name = str(source_name or "").strip()
	if not source_name:
		frappe.throw(_("Landed cost source document is required."))
	_assert_read(doctype, source_name)
	_assert_create(LANDED_COST_VOUCHER_DOCTYPE)
	if lock:
		frappe.db.sql(
			f"SELECT name FROM `tab{doctype}` WHERE name = %s FOR UPDATE",
			(source_name,),
		)
	source = frappe.get_doc(doctype, source_name)
	company, branch = _validate_source(source, doctype)
	return doctype, source, company, branch


def _normalise_standard_charges(charges: list[Any] | str | None) -> list[dict[str, Any]]:
	if isinstance(charges, str):
		charges = frappe.parse_json(charges)
	if not isinstance(charges, list) or not charges:
		frappe.throw(_("Add at least one landed-cost charge before review."))
	if len(charges) > MAX_STANDARD_LANDED_COST_CHARGES:
		frappe.throw(
			_("A maximum of {0} standard landed-cost charges is allowed.").format(
				MAX_STANDARD_LANDED_COST_CHARGES
			)
		)

	result: list[dict[str, Any]] = []
	for row in charges:
		if not isinstance(row, dict):
			frappe.throw(_("Each landed-cost charge must be an object."))
		extra = set(row) - _ALLOWED_STANDARD_CHARGE_KEYS
		if extra:
			frappe.throw(_("Unsupported landed-cost charge fields were provided."))
		expense_account = str(row.get("expense_account") or "").strip()
		description = str(row.get("description") or "").strip()
		amount = flt(row.get("amount"))
		if not expense_account:
			frappe.throw(_("Expense Account is required for every standard landed-cost charge."))
		if not description:
			frappe.throw(_("Description is required for every standard landed-cost charge."))
		if amount <= 0:
			frappe.throw(
				_(
					"Standard landed-cost charge amounts must be greater than zero. Use Advanced ERPNext for corrections or exceptional allocations."
				)
			)
		result.append(
			{
				"expense_account": expense_account,
				"description": description,
				"amount": amount,
			}
		)
	return result


def _validate_standard_charge_account(account: str, company: str) -> None:
	_assert_read("Account", account)
	details = frappe.db.get_value(
		"Account",
		account,
		["company", "account_type", "is_group", "disabled"],
		as_dict=True,
	)
	if not details:
		frappe.throw(_("Expense Account {0} does not exist.").format(account))
	if str(details.get("company") or "") != company:
		frappe.throw(
			_("Expense Account {0} does not belong to Company {1}.").format(
				account,
				company,
			)
		)
	if cint(details.get("is_group")) or cint(details.get("disabled")):
		frappe.throw(_("Expense Account {0} is not an active posting account.").format(account))
	if str(details.get("account_type") or "") not in ALLOWED_LANDED_COST_ACCOUNT_TYPES:
		frappe.throw(
			_(
				"Expense Account {0} is not an ERPNext-compatible landed-cost account type."
			).format(account)
		)


def _validate_native_lcv_payload(
	landed_cost_voucher: Any,
	*,
	source: Any,
	source_doctype: str,
	company: str,
) -> None:
	if landed_cost_voucher.get("doctype") != LANDED_COST_VOUCHER_DOCTYPE:
		frappe.throw(_("ERPNext could not prepare a Landed Cost Voucher."))
	if cint(landed_cost_voucher.get("docstatus")) != 0:
		frappe.throw(
			_("ERPNext returned a non-draft Landed Cost Voucher; preparation was stopped.")
		)
	if str(landed_cost_voucher.get("company") or "") != company:
		frappe.throw(
			_("Mapped Landed Cost Voucher Company does not match the selected source.")
		)

	receipt_rows = list(landed_cost_voucher.get("purchase_receipts") or [])
	if len(receipt_rows) != 1:
		frappe.throw(
			_("Guided landed cost preparation must contain exactly one source document.")
		)
	receipt_row = receipt_rows[0]
	if str(receipt_row.get("receipt_document_type") or "") != source_doctype:
		frappe.throw(
			_("Mapped Landed Cost Voucher source type does not match the selected document.")
		)
	if str(receipt_row.get("receipt_document") or "") != source.name:
		frappe.throw(
			_("Mapped Landed Cost Voucher source does not match the selected document.")
		)
	if str(receipt_row.get("supplier") or "") != str(getattr(source, "supplier", "") or ""):
		frappe.throw(
			_("Mapped Landed Cost Voucher Supplier does not match the selected source.")
		)

	items = list(landed_cost_voucher.get("items") or [])
	if not items:
		frappe.throw(
			_("The selected source has no items available for landed cost allocation.")
		)


def _native_landed_cost_voucher(
	source: Any,
	source_doctype: str,
	company: str,
	distribution_method: str,
) -> Any:
	landed_cost_voucher = frappe._dict(make_lcv(source_doctype, source.name) or {})
	_validate_native_lcv_payload(
		landed_cost_voucher,
		source=source,
		source_doctype=source_doctype,
		company=company,
	)
	landed_cost_voucher["distribute_charges_based_on"] = distribution_method
	return landed_cost_voucher


def _dimension_values(row: Any) -> dict[str, str]:
	return {
		fieldname: str(getattr(row, fieldname, "") or "")
		for fieldname in get_lcv_dimension_fields()
	}


def _assert_standard_landed_cost_shape(
	landed_cost_voucher: Any,
	*,
	source_doctype: str,
	source_name: str,
	company: str,
) -> None:
	if str(getattr(landed_cost_voucher, "company", "") or "") != company:
		frappe.throw(_("Landed Cost Voucher Company no longer matches the source Company."))
	if str(getattr(landed_cost_voucher, "distribute_charges_based_on", "") or "") not in STANDARD_DISTRIBUTION_METHODS:
		frappe.throw(_("This Landed Cost Voucher now requires Advanced ERPNext review."))

	receipt_rows = list(getattr(landed_cost_voucher, "purchase_receipts", None) or [])
	if len(receipt_rows) != 1:
		frappe.throw(_("Standard EdgeSuite Landed Cost supports exactly one source document."))
	receipt = receipt_rows[0]
	if (
		str(getattr(receipt, "receipt_document_type", "") or "") != source_doctype
		or str(getattr(receipt, "receipt_document", "") or "") != source_name
	):
		frappe.throw(_("The saved Landed Cost Voucher is linked to a different source."))

	if list(getattr(landed_cost_voucher, "vendor_invoices", None) or []):
		frappe.throw(_("Vendor-invoice landed cost claims require Advanced ERPNext."))

	items = list(getattr(landed_cost_voucher, "items", None) or [])
	if not items:
		frappe.throw(_("The Landed Cost Voucher has no receipt items."))
	for item in items:
		if cint(getattr(item, "is_fixed_asset", 0)):
			frappe.throw(_("Fixed-asset landed cost requires Advanced ERPNext."))
		item_dimensions = _dimension_values(item)
		if any(
			value
			for fieldname, value in item_dimensions.items()
			if fieldname != "cost_center"
		):
			frappe.throw(
				_("Custom Landed Cost item dimensions require Advanced ERPNext.")
			)
		if (
			str(getattr(item, "receipt_document_type", "") or "") != source_doctype
			or str(getattr(item, "receipt_document", "") or "") != source_name
			or not str(getattr(item, "purchase_receipt_item", "") or "").strip()
		):
			frappe.throw(
				_("The Landed Cost Voucher item mapping no longer matches the selected source.")
			)

	taxes = list(getattr(landed_cost_voucher, "taxes", None) or [])
	if not taxes or len(taxes) > MAX_STANDARD_LANDED_COST_CHARGES:
		frappe.throw(_("The Landed Cost Voucher charge rows are outside the standard EdgeSuite contract."))
	for tax in taxes:
		account = str(getattr(tax, "expense_account", "") or "").strip()
		description = str(getattr(tax, "description", "") or "").strip()
		amount = flt(getattr(tax, "amount", 0))
		if any(_dimension_values(tax).values()):
			frappe.throw(
				_("Landed Cost charge accounting-dimension overrides require Advanced ERPNext.")
			)
		if not account or not description or amount <= 0:
			frappe.throw(_("The Landed Cost Voucher contains a non-standard charge row."))
		_validate_standard_charge_account(account, company)


def _standard_landed_cost_signature(landed_cost_voucher: Any) -> dict[str, Any]:
	return {
		"company": str(getattr(landed_cost_voucher, "company", "") or ""),
		"posting_date": str(getattr(landed_cost_voucher, "posting_date", "") or ""),
		"distribute_charges_based_on": str(
			getattr(landed_cost_voucher, "distribute_charges_based_on", "") or ""
		),
		"purchase_receipts": [
			{
				"receipt_document_type": str(
					getattr(row, "receipt_document_type", "") or ""
				),
				"receipt_document": str(getattr(row, "receipt_document", "") or ""),
				"supplier": str(getattr(row, "supplier", "") or ""),
				"grand_total": flt(getattr(row, "grand_total", 0), 9),
			}
			for row in list(
				getattr(landed_cost_voucher, "purchase_receipts", None) or []
			)
		],
		"items": [
			{
				"item_code": str(getattr(row, "item_code", "") or ""),
				"receipt_document_type": str(
					getattr(row, "receipt_document_type", "") or ""
				),
				"receipt_document": str(getattr(row, "receipt_document", "") or ""),
				"purchase_receipt_item": str(
					getattr(row, "purchase_receipt_item", "") or ""
				),
				"qty": flt(getattr(row, "qty", 0), 9),
				"rate": flt(getattr(row, "rate", 0), 9),
				"amount": flt(getattr(row, "amount", 0), 9),
				"cost_center": str(getattr(row, "cost_center", "") or ""),
				"dimensions": _dimension_values(row),
				"is_fixed_asset": cint(getattr(row, "is_fixed_asset", 0)),
				"applicable_charges": flt(
					getattr(row, "applicable_charges", 0),
					9,
				),
			}
			for row in list(getattr(landed_cost_voucher, "items", None) or [])
		],
		"taxes": [
			{
				"expense_account": str(getattr(row, "expense_account", "") or ""),
				"description": str(getattr(row, "description", "") or ""),
				"amount": flt(getattr(row, "amount", 0), 9),
				"account_currency": str(getattr(row, "account_currency", "") or ""),
				"exchange_rate": flt(getattr(row, "exchange_rate", 0), 9),
				"base_amount": flt(getattr(row, "base_amount", 0), 9),
				"cost_center": str(getattr(row, "cost_center", "") or ""),
				"project": str(getattr(row, "project", "") or ""),
				"dimensions": _dimension_values(row),
			}
			for row in list(getattr(landed_cost_voucher, "taxes", None) or [])
		],
		"total_taxes_and_charges": flt(
			getattr(landed_cost_voucher, "total_taxes_and_charges", 0),
			9,
		),
	}


def _assert_standard_landed_cost_equivalence(
	existing: Any,
	expected: Any,
	*,
	source_doctype: str,
	source_name: str,
	company: str,
) -> None:
	_assert_standard_landed_cost_shape(
		existing,
		source_doctype=source_doctype,
		source_name=source_name,
		company=company,
	)
	if _standard_landed_cost_signature(existing) != _standard_landed_cost_signature(expected):
		frappe.throw(
			_(
				"Landed Cost Voucher {0} no longer matches the standard source, charges or ERPNext allocation. Use Advanced ERPNext review."
			).format(existing.name)
		)


def _charge_inputs_from_doc(landed_cost_voucher: Any) -> list[dict[str, Any]]:
	return [
		{
			"expense_account": str(getattr(row, "expense_account", "") or ""),
			"description": str(getattr(row, "description", "") or ""),
			"amount": flt(getattr(row, "amount", 0)),
		}
		for row in list(getattr(landed_cost_voucher, "taxes", None) or [])
	]


def _prepare_standard_landed_cost_voucher(
	source: Any,
	source_doctype: str,
	company: str,
	distribution_method: str,
	charges: list[Any] | str | None,
	*,
	posting_date: str | None = None,
) -> Any:
	method = _standard_distribution_method(distribution_method)
	normalised_charges = _normalise_standard_charges(charges)
	payload = _native_landed_cost_voucher(
		source,
		source_doctype,
		company,
		method,
	)
	landed_cost_voucher = frappe.get_doc(payload)
	if posting_date:
		landed_cost_voucher.posting_date = posting_date

	for item in list(getattr(landed_cost_voucher, "items", None) or []):
		if cint(getattr(item, "is_fixed_asset", 0)):
			frappe.throw(_("Fixed-asset landed cost requires Advanced ERPNext."))

	for charge in normalised_charges:
		_validate_standard_charge_account(charge["expense_account"], company)
		landed_cost_voucher.append("taxes", charge)

	# ERPNext owns account currency/exchange rate/base amount, mandatory dimensions,
	# total landed cost and item-level applicable-charge distribution.
	landed_cost_voucher.run_method("validate")
	_assert_standard_landed_cost_shape(
		landed_cost_voucher,
		source_doctype=source_doctype,
		source_name=source.name,
		company=company,
	)
	return landed_cost_voucher


def _serialise_standard_review(landed_cost_voucher: Any) -> dict[str, Any]:
	return {
		"posting_date": str(getattr(landed_cost_voucher, "posting_date", "") or ""),
		"distribution_method": str(
			getattr(landed_cost_voucher, "distribute_charges_based_on", "") or ""
		),
		"total_taxes_and_charges": flt(
			getattr(landed_cost_voucher, "total_taxes_and_charges", 0)
		),
		"charges": [
			{
				"expense_account": str(getattr(row, "expense_account", "") or ""),
				"description": str(getattr(row, "description", "") or ""),
				"amount": flt(getattr(row, "amount", 0)),
				"account_currency": str(getattr(row, "account_currency", "") or ""),
				"exchange_rate": flt(getattr(row, "exchange_rate", 0)),
				"base_amount": flt(getattr(row, "base_amount", 0)),
			}
			for row in list(getattr(landed_cost_voucher, "taxes", None) or [])
		],
		"items": [
			{
				"item_code": str(getattr(row, "item_code", "") or ""),
				"description": str(getattr(row, "description", "") or ""),
				"qty": flt(getattr(row, "qty", 0)),
				"amount": flt(getattr(row, "amount", 0)),
				"applicable_charges": flt(
					getattr(row, "applicable_charges", 0)
				),
			}
			for row in list(getattr(landed_cost_voucher, "items", None) or [])
		],
	}


def _find_linked_draft_landed_cost_vouchers(
	source_doctype: str,
	source_name: str,
) -> list[dict[str, Any]]:
	return list(
		frappe.db.sql(
			"""
			SELECT DISTINCT lcv.name, lcv.modified
			FROM `tabLanded Cost Voucher` lcv
			INNER JOIN `tabLanded Cost Purchase Receipt` source
				ON source.parent = lcv.name
				AND source.parenttype = %s
				AND source.parentfield = 'purchase_receipts'
			WHERE lcv.docstatus = 0
				AND source.receipt_document_type = %s
				AND source.receipt_document = %s
			ORDER BY lcv.modified ASC
			LIMIT 3
			""",
			(LANDED_COST_VOUCHER_DOCTYPE, source_doctype, source_name),
			as_dict=True,
		)
		or []
	)


def _landed_cost_payload(landed_cost_voucher: Any) -> dict[str, Any]:
	readiness = get_workflow_readiness(
		doctype=LANDED_COST_VOUCHER_DOCTYPE,
		doc=landed_cost_voucher,
	)
	return {
		"name": landed_cost_voucher.name,
		"modified": str(getattr(landed_cost_voucher, "modified", "") or ""),
		"docstatus": cint(getattr(landed_cost_voucher, "docstatus", 0)),
		"posting_date": str(getattr(landed_cost_voucher, "posting_date", "") or ""),
		"distribution_method": str(
			getattr(landed_cost_voucher, "distribute_charges_based_on", "") or ""
		),
		"total_taxes_and_charges": flt(
			getattr(landed_cost_voucher, "total_taxes_and_charges", 0)
		),
		"workflow_readiness": readiness,
		"workflow_controlled": str(readiness.get("source") or "") == "frappe",
		"can_submit": bool(
			cint(getattr(landed_cost_voucher, "docstatus", 0)) == 0
			and str(readiness.get("source") or "") != "frappe"
			and _permission(
				LANDED_COST_VOUCHER_DOCTYPE,
				"submit",
				landed_cost_voucher.name,
			)
		),
	}


@frappe.whitelist()
def get_landed_cost_capability() -> dict[str, Any]:
	"""Return permission-aware landed-cost capability for the EdgeSuite purchasing workspace."""
	can_create_lcv = _permission(LANDED_COST_VOUCHER_DOCTYPE, "create")
	can_use_purchase_receipt = bool(
		can_create_lcv and _permission(PURCHASE_RECEIPT_DOCTYPE, "read")
	)
	can_use_purchase_invoice = bool(
		can_create_lcv and _permission(PURCHASE_INVOICE_DOCTYPE, "read")
	)
	return {
		"can_prepare_landed_cost": bool(
			can_use_purchase_receipt or can_use_purchase_invoice
		),
		"can_use_purchase_receipt": can_use_purchase_receipt,
		"can_use_purchase_invoice": can_use_purchase_invoice,
		"distribution_methods": ["Amount", "Qty", "Distribute Manually"],
		"standard_distribution_methods": ["Amount", "Qty"],
		"max_standard_charges": MAX_STANDARD_LANDED_COST_CHARGES,
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


@frappe.whitelist()
def search_landed_cost_expense_accounts(
	txt: str = "",
	company: str | None = None,
) -> list[dict[str, Any]]:
	_assert_create(LANDED_COST_VOUCHER_DOCTYPE)
	if not _permission("Account", "read"):
		frappe.throw(
			_("You do not have permission to read Account."),
			frappe.PermissionError,
		)
	resolved_company, _branch, _allowed, _global = _resolve_scope(company=company)
	return list(
		search_link(
			"Account",
			str(txt or "").strip(),
			filters={
				"company": resolved_company,
				"is_group": 0,
				"disabled": 0,
				"account_type": ["in", sorted(ALLOWED_LANDED_COST_ACCOUNT_TYPES)],
			},
			page_length=MAX_LINK_RESULTS,
			reference_doctype=LANDED_COST_VOUCHER_DOCTYPE,
			link_fieldname="expense_account",
		)
	)


@frappe.whitelist(methods=["POST"])
def review_standard_landed_cost_allocation(
	source_type: str,
	source_name: str,
	distribution_method: str | None = None,
	charges: list[Any] | str | None = None,
) -> dict[str, Any]:
	doctype, source, company, branch = _get_source(source_type, source_name)
	landed_cost_voucher = _prepare_standard_landed_cost_voucher(
		source,
		doctype,
		company,
		distribution_method or "Amount",
		charges,
	)
	workflow_readiness = get_workflow_readiness(
		doctype=LANDED_COST_VOUCHER_DOCTYPE,
		doc=None,
	)
	return {
		"source_type": doctype,
		"source_name": source.name,
		"source_modified": str(getattr(source, "modified", "") or ""),
		"company": company,
		"branch": branch,
		"supplier": str(getattr(source, "supplier", "") or ""),
		"review": _serialise_standard_review(landed_cost_voucher),
		"workflow_readiness": workflow_readiness,
		"workflow_controlled": str(workflow_readiness.get("source") or "") == "frappe",
		"persisted": False,
		"posting_status": "Preview only",
		"source_of_truth": "ERPNext Landed Cost Voucher validate",
	}


@frappe.whitelist(methods=["POST"])
def start_standard_landed_cost_voucher(
	source_type: str,
	source_name: str,
	expected_source_modified: str | None = None,
	expected_posting_date: str | None = None,
	distribution_method: str | None = None,
	charges: list[Any] | str | None = None,
) -> dict[str, Any]:
	doctype, source, company, branch = _get_source(
		source_type,
		source_name,
		lock=True,
	)
	current_source_modified = str(getattr(source, "modified", "") or "")
	if (
		not str(expected_source_modified or "").strip()
		or str(expected_source_modified or "").strip() != current_source_modified
	):
		frappe.throw(
			_(
				"{0} {1} changed after landed-cost review. Refresh before saving the draft."
			).format(doctype, source.name)
		)

	drafts = _find_linked_draft_landed_cost_vouchers(doctype, source.name)
	if len(drafts) > 1:
		frappe.throw(
			_(
				"More than one draft Landed Cost Voucher is linked to this source. Use Advanced ERPNext review."
			)
		)

	existing = None
	posting_date = None
	if drafts:
		existing_name = str(drafts[0].get("name") or "")
		_assert_read(LANDED_COST_VOUCHER_DOCTYPE, existing_name)
		existing = frappe.get_doc(LANDED_COST_VOUCHER_DOCTYPE, existing_name)
		posting_date = str(getattr(existing, "posting_date", "") or "")

	expected = _prepare_standard_landed_cost_voucher(
		source,
		doctype,
		company,
		distribution_method or "Amount",
		charges,
		posting_date=posting_date or None,
	)
	expected_posting = str(expected_posting_date or "").strip()
	if not expected_posting or expected_posting != str(
		getattr(expected, "posting_date", "") or ""
	):
		frappe.throw(
			_(
				"The Landed Cost posting date changed after review. Refresh before saving the draft."
			)
		)

	if existing is not None:
		if cint(getattr(existing, "docstatus", 0)) != 0:
			frappe.throw(_("The linked Landed Cost Voucher is no longer a draft."))
		_assert_standard_landed_cost_equivalence(
			existing,
			expected,
			source_doctype=doctype,
			source_name=source.name,
			company=company,
		)
		landed_cost_voucher = existing
		reused = True
	else:
		landed_cost_voucher = expected
		landed_cost_voucher.insert()
		reused = False

	return {
		"source_type": doctype,
		"source_name": source.name,
		"source_modified": current_source_modified,
		"company": company,
		"branch": branch,
		"landed_cost_voucher": _landed_cost_payload(landed_cost_voucher),
		"reused": reused,
		"posting_status": "Saved Draft",
		"source_of_truth": "ERPNext Landed Cost Voucher",
	}


@frappe.whitelist(methods=["POST"])
def submit_standard_landed_cost_voucher(
	source_type: str,
	source_name: str,
	landed_cost_voucher_name: str,
	expected_landed_cost_modified: str | None = None,
) -> dict[str, Any]:
	doctype = _source_doctype(source_type)
	source_name = str(source_name or "").strip()
	landed_cost_voucher_name = str(landed_cost_voucher_name or "").strip()
	if not source_name or not landed_cost_voucher_name:
		frappe.throw(_("Source and Landed Cost Voucher are required."))

	_assert_read(doctype, source_name)
	_assert_read(LANDED_COST_VOUCHER_DOCTYPE, landed_cost_voucher_name)
	frappe.db.sql(
		f"SELECT name FROM `tab{doctype}` WHERE name = %s FOR UPDATE",
		(source_name,),
	)
	frappe.db.sql(
		"SELECT name FROM `tabLanded Cost Voucher` WHERE name = %s FOR UPDATE",
		(landed_cost_voucher_name,),
	)
	source = frappe.get_doc(doctype, source_name)
	company, branch = _validate_source(source, doctype)
	landed_cost_voucher = frappe.get_doc(
		LANDED_COST_VOUCHER_DOCTYPE,
		landed_cost_voucher_name,
	)
	_assert_standard_landed_cost_shape(
		landed_cost_voucher,
		source_doctype=doctype,
		source_name=source.name,
		company=company,
	)

	if cint(getattr(landed_cost_voucher, "docstatus", 0)) == 1:
		return {
			"source_type": doctype,
			"source_name": source.name,
			"source_modified": str(getattr(source, "modified", "") or ""),
			"company": company,
			"branch": branch,
			"landed_cost_voucher": _landed_cost_payload(landed_cost_voucher),
			"already_submitted": True,
			"posting_status": "Submitted",
		}
	if cint(getattr(landed_cost_voucher, "docstatus", 0)) != 0:
		frappe.throw(_("Only a draft standard Landed Cost Voucher can be submitted."))

	expected_modified = str(expected_landed_cost_modified or "").strip()
	if (
		not expected_modified
		or expected_modified
		!= str(getattr(landed_cost_voucher, "modified", "") or "")
	):
		frappe.throw(
			_(
				"Landed Cost Voucher {0} changed after it was loaded. Refresh before submitting."
			).format(landed_cost_voucher.name)
		)

	expected = _prepare_standard_landed_cost_voucher(
		source,
		doctype,
		company,
		str(getattr(landed_cost_voucher, "distribute_charges_based_on", "") or ""),
		_charge_inputs_from_doc(landed_cost_voucher),
		posting_date=str(getattr(landed_cost_voucher, "posting_date", "") or ""),
	)
	_assert_standard_landed_cost_equivalence(
		landed_cost_voucher,
		expected,
		source_doctype=doctype,
		source_name=source.name,
		company=company,
	)
	readiness = get_workflow_readiness(
		doctype=LANDED_COST_VOUCHER_DOCTYPE,
		doc=landed_cost_voucher,
	)
	if str(readiness.get("source") or "") == "frappe":
		frappe.throw(
			_(
				"Landed Cost Voucher is controlled by an active Frappe Workflow. Use the available approval action in EdgeSuite."
			)
		)
	if not _permission(
		LANDED_COST_VOUCHER_DOCTYPE,
		"submit",
		landed_cost_voucher.name,
	):
		frappe.throw(
			_("You do not have permission to submit Landed Cost Voucher."),
			frappe.PermissionError,
		)

	landed_cost_voucher.submit()
	refreshed = frappe.get_doc(
		LANDED_COST_VOUCHER_DOCTYPE,
		landed_cost_voucher.name,
	)
	return {
		"source_type": doctype,
		"source_name": source.name,
		"source_modified": str(
			getattr(frappe.get_doc(doctype, source.name), "modified", "") or ""
		),
		"company": company,
		"branch": branch,
		"landed_cost_voucher": _landed_cost_payload(refreshed),
		"already_submitted": False,
		"posting_status": "Submitted",
	}


@frappe.whitelist(methods=["POST"])
def apply_landed_cost_workflow_action(
	source_type: str,
	source_name: str,
	landed_cost_voucher_name: str,
	action: str,
	expected_source_modified: str | None = None,
	expected_landed_cost_modified: str | None = None,
	expected_workflow_state: str | None = None,
) -> dict[str, Any]:
	doctype = _source_doctype(source_type)
	source_name = str(source_name or "").strip()
	landed_cost_voucher_name = str(landed_cost_voucher_name or "").strip()
	action = str(action or "").strip()
	if not source_name or not landed_cost_voucher_name or not action:
		frappe.throw(_("Source, Landed Cost Voucher and workflow action are required."))

	_assert_read(doctype, source_name)
	_assert_read(LANDED_COST_VOUCHER_DOCTYPE, landed_cost_voucher_name)
	frappe.db.sql(
		f"SELECT name FROM `tab{doctype}` WHERE name = %s FOR UPDATE",
		(source_name,),
	)
	frappe.db.sql(
		"SELECT name FROM `tabLanded Cost Voucher` WHERE name = %s FOR UPDATE",
		(landed_cost_voucher_name,),
	)
	source = frappe.get_doc(doctype, source_name)
	company, branch = _validate_source(source, doctype)
	landed_cost_voucher = frappe.get_doc(
		LANDED_COST_VOUCHER_DOCTYPE,
		landed_cost_voucher_name,
	)
	if cint(getattr(landed_cost_voucher, "docstatus", 0)) != 0:
		frappe.throw(
			_("Only a draft Landed Cost Voucher can take a standard EdgeSuite workflow action.")
		)

	if (
		not str(expected_source_modified or "").strip()
		or str(expected_source_modified or "").strip()
		!= str(getattr(source, "modified", "") or "")
	):
		frappe.throw(
			_(
				"{0} {1} changed after the Landed Cost approval was loaded. Refresh before continuing."
			).format(doctype, source.name)
		)
	expected_modified = str(expected_landed_cost_modified or "").strip()
	if (
		not expected_modified
		or expected_modified
		!= str(getattr(landed_cost_voucher, "modified", "") or "")
	):
		frappe.throw(
			_(
				"Landed Cost Voucher {0} changed after approval was loaded. Refresh before continuing."
			).format(landed_cost_voucher.name)
		)

	expected = _prepare_standard_landed_cost_voucher(
		source,
		doctype,
		company,
		str(getattr(landed_cost_voucher, "distribute_charges_based_on", "") or ""),
		_charge_inputs_from_doc(landed_cost_voucher),
		posting_date=str(getattr(landed_cost_voucher, "posting_date", "") or ""),
	)
	_assert_standard_landed_cost_equivalence(
		landed_cost_voucher,
		expected,
		source_doctype=doctype,
		source_name=source.name,
		company=company,
	)
	readiness = get_workflow_readiness(
		doctype=LANDED_COST_VOUCHER_DOCTYPE,
		doc=landed_cost_voucher,
	)
	if str(readiness.get("source") or "") != "frappe":
		frappe.throw(_("No active Frappe Workflow controls this Landed Cost Voucher."))

	result = apply_document_workflow_action(
		doctype=LANDED_COST_VOUCHER_DOCTYPE,
		name=landed_cost_voucher.name,
		action=action,
		expected_modified=expected_landed_cost_modified,
		expected_state=str(expected_workflow_state or ""),
	)
	refreshed = frappe.get_doc(
		LANDED_COST_VOUCHER_DOCTYPE,
		landed_cost_voucher.name,
	)
	refreshed_source = frappe.get_doc(doctype, source.name)
	return {
		**result,
		"source_type": doctype,
		"source_name": source.name,
		"source_modified": str(getattr(refreshed_source, "modified", "") or ""),
		"company": company,
		"branch": branch,
		"landed_cost_voucher": _landed_cost_payload(refreshed),
		"source_of_truth": "Frappe apply_workflow and ERPNext Landed Cost Voucher",
	}


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

	# Advanced/native handoff intentionally remains unsaved because charge rows are
	# mandatory before first persistence and ERPNext owns the full advanced form.
	landed_cost_voucher = _native_landed_cost_voucher(
		source,
		doctype,
		company,
		method,
	)
	items = list(landed_cost_voucher.get("items") or [])
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
