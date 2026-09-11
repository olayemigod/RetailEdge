from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	resolve_branch_from_warehouse,
)
from retailedge.operating_context import get_operating_context, get_operational_branch_scope
from retailedge.professional_selling import _assert_read, _validate_stored_operational_branch
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness


PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
HANDOFF_DOCTYPE = "Supplier Document Purchase Invoice Handoff"
_LOCK_TABLE = "tabPurchase Invoice"
MAX_ITEM_SUMMARY = 10
MAX_DRAFT_QUEUE = 50


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


def _validate_stock_context(
	doc,
	*,
	company: str,
	invoice_branch: str,
) -> dict[str, Any]:
	if not cint(doc.get("update_stock")):
		return {
			"mode": "accounting_only",
			"warehouse_branch": "",
			"effective_branch": invoice_branch,
			"blockers": [],
		}

	blockers: list[str] = []
	resolved_branches: set[str] = set()
	for row in list(doc.get("items") or []):
		warehouse = _clean(row.get("warehouse"))
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

	return {
		"mode": "update_stock",
		"warehouse_branch": warehouse_branch,
		"effective_branch": effective_branch,
		"blockers": list(dict.fromkeys(blockers)),
	}


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


def _build_preview(doc) -> dict[str, Any]:
	company, invoice_branch = _validate_invoice_context(doc)
	blockers = _standard_invoice_blockers(doc)
	source_context = _validate_source_less_context(doc)
	blockers.extend(source_context["blockers"])
	stock_context = _validate_stock_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
	)
	blockers.extend(stock_context["blockers"])
	blockers = list(dict.fromkeys(blockers))

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
		"currency": _clean(doc.get("currency")),
		"grand_total": flt(doc.get("grand_total")),
		"update_stock": bool(cint(doc.get("update_stock"))),
		"completion_mode": stock_context["mode"],
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
def get_standard_purchase_invoice_completion_preview(name: str) -> dict[str, Any]:
	"""Return a persistence-free review for one source-less standard Purchase Invoice."""
	doc = _get_purchase_invoice(name)
	return _build_preview(doc)


@frappe.whitelist(methods=["POST"])
def submit_standard_purchase_invoice(
	name: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	"""Submit one reviewed generic Purchase Invoice through native ERPNext."""
	name = _clean(name)
	_lock_purchase_invoice(name)
	doc = _get_purchase_invoice(name)
	_assert_expected_modified(doc, expected_modified)
	company, invoice_branch = _validate_invoice_context(doc)

	blockers = _standard_invoice_blockers(doc)
	blockers.extend(_validate_source_less_context(doc)["blockers"])
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
		"supplier": _clean(doc.get("supplier")),
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
	blockers.extend(_validate_source_less_context(doc)["blockers"])
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

	return apply_document_workflow_action(
		doctype=PURCHASE_INVOICE_DOCTYPE,
		name=name,
		action=action,
		expected_modified=expected_modified,
		expected_state=str(expected_workflow_state or ""),
	)
