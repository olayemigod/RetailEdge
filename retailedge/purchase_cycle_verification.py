from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

MAX_VERIFICATION_INVOICES = 100
MAX_VERIFICATION_ITEM_ROWS = 2000
RATE_TOLERANCE = 0.01
QTY_TOLERANCE = 0.000001


@frappe.whitelist()
def get_purchase_cycle_verification(invoice_names: list[str] | str | None = None) -> dict[str, Any]:
	"""Return bounded advisory PO / receipt coverage for submitted Purchase Invoices.

	ERPNext remains authoritative for purchase-cycle validation and accounting. This
	endpoint never writes documents or creates a persistent match state.
	"""
	if not frappe.has_permission("Purchase Invoice", "read"):
		frappe.throw(_("You do not have permission to view Purchase Invoices."), frappe.PermissionError)

	names = _normalise_invoice_names(invoice_names)
	policy = _buying_policy()
	if not names:
		return {"rows": [], "policy": policy, "source_of_truth": "ERPNext purchase-cycle documents"}

	headers = frappe.get_list(
		"Purchase Invoice",
		filters={"name": ["in", names], "docstatus": 1},
		fields=["name", "is_return"],
		order_by="name asc",
		limit=MAX_VERIFICATION_INVOICES + 1,
	)
	if len(headers) > MAX_VERIFICATION_INVOICES:
		frappe.throw(
			_("Purchase-cycle verification is limited to {0} invoices per request.").format(
				MAX_VERIFICATION_INVOICES
			)
		)

	permitted_names = {str(row.name) for row in headers}
	if not permitted_names:
		return {"rows": [], "policy": policy, "source_of_truth": "ERPNext purchase-cycle documents"}

	items = frappe.get_all(
		"Purchase Invoice Item",
		filters={"parenttype": "Purchase Invoice", "parent": ["in", sorted(permitted_names)]},
		fields=[
			"parent",
			"idx",
			"item_code",
			"stock_qty",
			"base_net_rate",
			"purchase_order",
			"po_detail",
			"purchase_receipt",
			"pr_detail",
		],
		order_by="parent asc, idx asc",
		limit=MAX_VERIFICATION_ITEM_ROWS + 1,
	)
	if len(items) > MAX_VERIFICATION_ITEM_ROWS:
		frappe.throw(
			_(
				"More than {0} Purchase Invoice item rows are in this verification scope. Narrow the page size first."
			).format(MAX_VERIFICATION_ITEM_ROWS)
		)

	po_names = {str(row.purchase_order) for row in items if row.get("purchase_order")}
	pr_names = {str(row.purchase_receipt) for row in items if row.get("purchase_receipt")}
	permitted_pos = _permitted_parent_names("Purchase Order", po_names)
	permitted_prs = _permitted_parent_names("Purchase Receipt", pr_names)

	po_details = _source_item_map(
		"Purchase Order Item",
		{str(row.po_detail) for row in items if row.get("po_detail")},
		permitted_pos,
	)
	pr_details = _source_item_map(
		"Purchase Receipt Item",
		{str(row.pr_detail) for row in items if row.get("pr_detail")},
		permitted_prs,
	)

	items_by_invoice: dict[str, list[frappe._dict]] = defaultdict(list)
	for row in items:
		items_by_invoice[str(row.parent)].append(row)

	result_rows = []
	for header in headers:
		result_rows.append(
			_classify_invoice(
				invoice=str(header.name),
				is_return=bool(cint(header.is_return)),
				items=items_by_invoice.get(str(header.name), []),
				po_details=po_details,
				pr_details=pr_details,
				permitted_pos=permitted_pos,
				permitted_prs=permitted_prs,
			)
		)

	return {
		"rows": result_rows,
		"policy": policy,
		"source_of_truth": "ERPNext Purchase Invoice Item links, Purchase Order Item, Purchase Receipt Item and Buying Settings",
		"limits": {"invoices": MAX_VERIFICATION_INVOICES, "item_rows": MAX_VERIFICATION_ITEM_ROWS},
	}


def _normalise_invoice_names(invoice_names: list[str] | str | None) -> list[str]:
	if isinstance(invoice_names, str):
		invoice_names = frappe.parse_json(invoice_names)
	if invoice_names in (None, ""):
		return []
	if not isinstance(invoice_names, (list, tuple)):
		frappe.throw(_("Purchase Invoice names must be supplied as a list."))

	names: list[str] = []
	seen: set[str] = set()
	for value in invoice_names:
		name = str(value or "").strip()
		if not name or name in seen:
			continue
		seen.add(name)
		names.append(name)
	if len(names) > MAX_VERIFICATION_INVOICES:
		frappe.throw(
			_("Purchase-cycle verification is limited to {0} invoices per request.").format(
				MAX_VERIFICATION_INVOICES
			)
		)
	return names


def _permitted_parent_names(doctype: str, names: set[str]) -> set[str]:
	if not names or not frappe.has_permission(doctype, "read"):
		return set()
	rows = frappe.get_list(
		doctype,
		filters={"name": ["in", sorted(names)]},
		pluck="name",
		order_by="name asc",
		limit=len(names) + 1,
	)
	return {str(name) for name in rows}


def _source_item_map(
	doctype: str,
	detail_names: set[str],
	permitted_parents: set[str],
) -> dict[str, frappe._dict]:
	if not detail_names or not permitted_parents:
		return {}
	# Child tables do not carry independent user permissions. Parent documents were
	# permission-filtered immediately above, so only rows from readable parents are used.
	rows = frappe.get_all(
		doctype,
		filters={"name": ["in", sorted(detail_names)], "parent": ["in", sorted(permitted_parents)]},
		fields=["name", "parent", "item_code", "stock_qty", "base_net_rate"],
		limit=min(MAX_VERIFICATION_ITEM_ROWS, len(detail_names)) + 1,
	)
	return {str(row.name): row for row in rows}


def _classify_invoice(
	*,
	invoice: str,
	is_return: bool,
	items: list[frappe._dict],
	po_details: dict[str, frappe._dict],
	pr_details: dict[str, frappe._dict],
	permitted_pos: set[str],
	permitted_prs: set[str],
) -> dict[str, Any]:
	line_count = len(items)
	po_links = sum(bool(row.get("purchase_order") and row.get("po_detail")) for row in items)
	receipt_links = sum(bool(row.get("purchase_receipt") and row.get("pr_detail")) for row in items)
	if is_return:
		return {
			"invoice": invoice,
			"verification_status": "Return",
			"po_links": _coverage(po_links, line_count),
			"receipt_links": _coverage(receipt_links, line_count),
			"review_flags": 0,
			"review_reason": "Return / credit note is outside ordinary C6A matching semantics.",
		}

	flag_count = 0
	reasons: list[str] = []
	for row in items:
		po_name = str(row.get("purchase_order") or "")
		po_detail = str(row.get("po_detail") or "")
		pr_name = str(row.get("purchase_receipt") or "")
		pr_detail = str(row.get("pr_detail") or "")

		if bool(po_name) != bool(po_detail):
			flag_count += 1
			_add_reason(reasons, _("Incomplete Purchase Order item reference"))
		elif po_name and po_detail:
			if po_name not in permitted_pos:
				flag_count += 1
				_add_reason(reasons, _("Linked Purchase Order is unavailable in your current access"))
			else:
				po_row = po_details.get(po_detail)
				if not po_row:
					flag_count += 1
					_add_reason(reasons, _("Linked Purchase Order item is unavailable"))
				elif str(po_row.get("parent") or "") != po_name:
					flag_count += 1
					_add_reason(reasons, _("Purchase Order item reference does not belong to the linked Purchase Order"))
				elif _rate_differs(row.get("base_net_rate"), po_row.get("base_net_rate")):
					flag_count += 1
					_add_reason(reasons, _("Invoice rate differs from linked Purchase Order"))

		if bool(pr_name) != bool(pr_detail):
			flag_count += 1
			_add_reason(reasons, _("Incomplete Purchase Receipt item reference"))
		elif pr_name and pr_detail:
			if pr_name not in permitted_prs:
				flag_count += 1
				_add_reason(reasons, _("Linked Purchase Receipt is unavailable in your current access"))
			else:
				pr_row = pr_details.get(pr_detail)
				if not pr_row:
					flag_count += 1
					_add_reason(reasons, _("Linked Purchase Receipt item is unavailable"))
				elif str(pr_row.get("parent") or "") != pr_name:
					flag_count += 1
					_add_reason(reasons, _("Purchase Receipt item reference does not belong to the linked Purchase Receipt"))
				else:
					if _rate_differs(row.get("base_net_rate"), pr_row.get("base_net_rate")):
						flag_count += 1
						_add_reason(reasons, _("Invoice rate differs from linked Purchase Receipt"))
					if flt(row.get("stock_qty")) > flt(pr_row.get("stock_qty")) + QTY_TOLERANCE:
						flag_count += 1
						_add_reason(
							reasons,
							_("Invoice quantity exceeds the directly linked accepted receipt quantity"),
						)

	status = _coverage_status(
		line_count=line_count,
		po_links=po_links,
		receipt_links=receipt_links,
		review_flags=flag_count,
	)
	return {
		"invoice": invoice,
		"verification_status": status,
		"po_links": _coverage(po_links, line_count),
		"receipt_links": _coverage(receipt_links, line_count),
		"review_flags": flag_count,
		"review_reason": "; ".join(reasons),
	}


def _coverage_status(*, line_count: int, po_links: int, receipt_links: int, review_flags: int) -> str:
	if review_flags:
		return "Review"
	if line_count <= 0:
		return "Unlinked"
	if po_links == line_count and receipt_links == line_count:
		return "Linked"
	if po_links == line_count and receipt_links == 0:
		return "PO Linked"
	if po_links == 0 and receipt_links == 0:
		return "Unlinked"
	return "Mixed Links"


def _coverage(linked: int, total: int) -> str:
	return f"{int(linked)}/{int(total)}"


def _rate_differs(invoice_rate: Any, source_rate: Any) -> bool:
	return abs(flt(invoice_rate) - flt(source_rate)) > RATE_TOLERANCE


def _add_reason(reasons: list[str], reason: str) -> None:
	if reason not in reasons:
		reasons.append(reason)


def _buying_policy() -> dict[str, Any]:
	if not frappe.has_permission("Buying Settings", "read"):
		return {"visible": 0}
	settings = frappe.get_single("Buying Settings")
	maintain_same_rate = bool(cint(settings.get("maintain_same_rate")))
	return {
		"visible": 1,
		"po_required": str(settings.get("po_required") or "No"),
		"pr_required": str(settings.get("pr_required") or "No"),
		"maintain_same_rate": int(maintain_same_rate),
		"maintain_same_rate_action": str(settings.get("maintain_same_rate_action") or "") if maintain_same_rate else "",
	}
