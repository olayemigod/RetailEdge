from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, getdate, today

from retailedge.advanced_payments import _payment_branch_field
from retailedge.reporting_capabilities import require_report_action
from retailedge.reporting_scope import constrain_report_filters, validate_report_scope

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_PAYMENT_ROWS = 5000
MAX_DATE_RANGE_DAYS = 366
MAX_LINK_RESULTS = 20

DEFAULT_GROUP_BY = "Mode of Payment"
PERIOD_GROUPS = frozenset({"Day", "Week", "Month", "Quarter", "Year"})
SUPPORTED_GROUP_BY = (
	"Day",
	"Week",
	"Month",
	"Quarter",
	"Year",
	"Mode of Payment",
	"Branch",
	"Payment Type",
	"Party Type",
	"Party",
	"Settlement Account",
)
PAYMENT_TYPES = ("Receive", "Pay", "Internal Transfer")
PARTY_TYPES = ("Customer", "Supplier")


@frappe.whitelist()
def get_payment_settlement_context() -> dict[str, Any]:
	user = frappe.session.user
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	scope: dict[str, Any] = {"restricted": False, "allowed_branches": []}
	branch = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	if company:
		scope = validate_report_scope(
			company=company,
			branch="",
			user=user,
			require_branch_when_restricted=False,
		)
		if branch:
			try:
				validate_report_scope(
					company=company,
					branch=branch,
					user=user,
					require_branch_when_restricted=False,
				)
			except (frappe.PermissionError, frappe.ValidationError):
				branch = ""
		if scope.get("restricted") and branch not in (scope.get("allowed_branches") or []):
			branch = ""
		if not branch and len(scope.get("allowed_branches") or []) == 1:
			branch = scope["allowed_branches"][0]

	if company and not (scope.get("restricted") and not branch):
		require_report_action(
			"payment-settlement-analysis",
			action="view",
			company=company,
			branch=branch,
		)

	return {
		"default_filters": {
			"company": company,
			"branch": branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
			"group_by": DEFAULT_GROUP_BY,
			"payment_type": "All",
			"party_type": "All",
			"party": "",
			"mode_of_payment": "",
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", user, "full_name") or user,
		"group_by_options": list(SUPPORTED_GROUP_BY),
		"payment_types": ["All", *PAYMENT_TYPES],
		"party_types": ["All", *PARTY_TYPES],
		"branch_dimension_available": int(bool(_payment_branch_field())),
		"scope": {
			"restricted": int(bool(scope.get("restricted"))),
			"allowed_branch_count": len(scope.get("allowed_branches") or []),
		},
		"limits": {
			"payment_rows": MAX_PAYMENT_ROWS,
			"date_range_days": MAX_DATE_RANGE_DAYS,
			"page_size": MAX_PAGE_SIZE,
			"link_results": MAX_LINK_RESULTS,
		},
		"data_policy": {
			"source": _("Submitted ERPNext Payment Entries."),
			"money": _(
				"Money In uses posted Receive Payment Entry base received amount; Money Out uses posted Pay Payment Entry base paid amount."
			),
			"advances": _(
				"Available Customer Advances use submitted customer Receive Payment Entry unallocated amount only when the party account is in Company currency."
			),
			"cashier": _("Cashier is not inferred from Payment Entry owner and is not exposed as a dimension."),
			"payment_mode": _(
				"Payment Mode is analysed from Payment Entry, not inferred from Sales Invoices."
			),
		},
	}


@frappe.whitelist()
def search_payment_settlement_options(
	kind: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
	party_type: str = "",
) -> list[dict[str, Any]]:
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(branch or "").strip()
	party_type = str(party_type or "").strip()

	if kind == "company":
		return _search_named("Company", txt)
	if company:
		validate_report_scope(
			company=company,
			branch=branch,
			require_branch_when_restricted=False,
		)
	if kind == "branch":
		return _search_branches(txt=txt, company=company)
	if kind == "mode_of_payment":
		return _search_named("Mode of Payment", txt)
	if kind == "party":
		if party_type not in PARTY_TYPES:
			return []
		return _search_named(party_type, txt)
	frappe.throw(_("Unsupported Payment & Settlement Analysis search type."))


@frappe.whitelist()
def get_payment_settlement_analysis(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
	sort: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	from retailedge.report_sorting import apply_materialized_report_sort

	resolved = _resolve_filters(filters)
	dataset = _build_dataset(resolved)
	apply_materialized_report_sort(dataset, sort, "payment-settlement-analysis")
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_payment_settlement_analysis_export(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	return _export_response(_build_dataset(_resolve_filters(filters)))


def _resolve_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	if filters and not isinstance(filters, dict):
		frappe.throw(_("Invalid Payment & Settlement Analysis filters."))
	resolved = frappe._dict(filters or {})
	if not resolved.get("company"):
		resolved.company = str(frappe.defaults.get_user_default("Company") or "").strip()
	resolved = frappe._dict(
		constrain_report_filters(
			resolved,
			require_branch_when_restricted=True,
		)
	)
	_validate_filters(resolved)
	require_report_action(
		"payment-settlement-analysis",
		action="view",
		company=str(resolved.company),
		branch=str(resolved.get("branch") or ""),
	)
	return resolved


def _validate_filters(filters: frappe._dict) -> None:
	if not filters.get("company"):
		frappe.throw(_("Company is required."))
	if not frappe.has_permission("Payment Entry", "read"):
		frappe.throw(
			_("You do not have permission to read Payment Entries."),
			frappe.PermissionError,
		)
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))
	start = getdate(filters.from_date)
	end = getdate(filters.to_date)
	if start > end:
		frappe.throw(_("From Date cannot be after To Date."))
	if (end - start).days + 1 > MAX_DATE_RANGE_DAYS:
		frappe.throw(
			_("Payment & Settlement Analysis supports up to {0} days per request.").format(
				MAX_DATE_RANGE_DAYS
			)
		)

	group_by = _normalise_group_by(filters.get("group_by"))
	if group_by == "Branch" and not _payment_branch_field():
		frappe.throw(
			_("Payment Entry Branch attribution is unavailable. Run site migration before grouping payments by Branch.")
		)

	payment_type = str(filters.get("payment_type") or "All").strip()
	if payment_type not in {"All", *PAYMENT_TYPES}:
		frappe.throw(_("Unsupported Payment Type."))
	party_type = str(filters.get("party_type") or "All").strip()
	if party_type not in {"All", *PARTY_TYPES}:
		frappe.throw(_("Unsupported Party Type."))
	if filters.get("party") and party_type not in PARTY_TYPES:
		frappe.throw(_("Choose Customer or Supplier before filtering by Party."))


def _normalise_group_by(value: Any) -> str:
	raw = str(value or DEFAULT_GROUP_BY).strip()
	lookup = {item.casefold(): item for item in SUPPORTED_GROUP_BY}
	resolved = lookup.get(raw.casefold())
	if not resolved:
		frappe.throw(
			_("Group By must be one of: {0}.").format(", ".join(SUPPORTED_GROUP_BY))
		)
	return resolved


def _build_dataset(filters: frappe._dict) -> dict[str, Any]:
	group_by = _normalise_group_by(filters.get("group_by"))
	company = str(filters.company)
	currency = str(frappe.get_cached_value("Company", company, "default_currency") or "")
	branch_field = _payment_branch_field()

	query_filters: dict[str, Any] = {
		"docstatus": 1,
		"company": company,
		"posting_date": ["between", [filters.from_date, filters.to_date]],
	}
	if filters.get("branch"):
		if not branch_field:
			frappe.throw(_("Payment Entry Branch attribution is unavailable."))
		query_filters[branch_field] = filters.branch
	if filters.get("payment_type") not in (None, "", "All"):
		query_filters["payment_type"] = filters.payment_type
	if filters.get("party_type") not in (None, "", "All"):
		query_filters["party_type"] = filters.party_type
	if filters.get("party"):
		query_filters["party"] = filters.party
	if filters.get("mode_of_payment"):
		query_filters["mode_of_payment"] = filters.mode_of_payment

	fields = [
		"name",
		"posting_date",
		"payment_type",
		"party_type",
		"party",
		"mode_of_payment",
		"paid_amount",
		"received_amount",
		"base_paid_amount",
		"base_received_amount",
		"unallocated_amount",
		"paid_from",
		"paid_to",
		"paid_from_account_currency",
		"paid_to_account_currency",
	]
	if branch_field:
		fields.append(branch_field)

	payments = frappe.get_list(
		"Payment Entry",
		filters=query_filters,
		fields=fields,
		order_by="posting_date asc, name asc",
		limit_page_length=MAX_PAYMENT_ROWS + 1,
	)
	if len(payments) > MAX_PAYMENT_ROWS:
		frappe.throw(
			_(
				"More than {0} submitted payments match this analysis. Narrow the date, Branch, Party, Payment Type, or Mode of Payment filters."
			).format(MAX_PAYMENT_ROWS)
		)

	buckets: dict[str, dict[str, Any]] = {}
	for payment in payments:
		key, label = _group_value(group_by, payment, branch_field=branch_field)
		bucket = buckets.setdefault(key, _new_bucket(key, label))
		_add_payment(bucket, payment, company_currency=currency)

	rows = [_finalise_bucket(bucket) for bucket in buckets.values()]
	if group_by in PERIOD_GROUPS:
		rows.sort(key=lambda row: str(row.get("group_key") or ""))
	else:
		rows.sort(
			key=lambda row: (
				-(flt(row.get("money_in")) + flt(row.get("money_out"))),
				str(row.get("group_label") or ""),
			)
		)

	return {
		"title": _("Payment & Settlement Analysis"),
		"columns": _columns(currency),
		"rows": rows,
		"summary": _summary(rows, currency=currency),
		"company_currency": currency,
		"group_by": group_by,
		"scan": {
			"payment_rows": len(payments),
			"payment_limit": MAX_PAYMENT_ROWS,
		},
		"metadata": {
			"source": "Submitted ERPNext Payment Entry",
			"money_truth": "Posted Payment Entry company-currency base amounts",
			"advance_truth": "Submitted customer Receive Payment Entry unallocated_amount where party account is Company currency",
			"invoice_payment_mode_policy": "Payment Mode is not inferred from Sales Invoice",
			"cashier_dimension": "Not exposed; Payment Entry owner is not treated as cashier",
			"mixed_settlement_policy": "Multi-reference Payment Entries are not labelled as Mixed Settlement because the concepts are not equivalent",
		},
	}


def _group_value(
	group_by: str,
	payment: frappe._dict,
	*,
	branch_field: str | None,
) -> tuple[str, str]:
	if group_by in PERIOD_GROUPS:
		return _period_group(payment.posting_date, group_by)
	if group_by == "Mode of Payment":
		value = str(payment.get("mode_of_payment") or "").strip() or _("Unspecified / Account-led")
		return value, value
	if group_by == "Branch":
		value = str(payment.get(branch_field) or "").strip() if branch_field else ""
		value = value or _("Unattributed Branch")
		return value, value
	if group_by == "Payment Type":
		value = str(payment.get("payment_type") or "").strip() or _("Unspecified Payment Type")
		return value, value
	if group_by == "Party Type":
		value = str(payment.get("party_type") or "").strip() or _("No Party")
		return value, value
	if group_by == "Party":
		party_type = str(payment.get("party_type") or "").strip() or _("No Party")
		party = str(payment.get("party") or "").strip() or _("No Party")
		return f"{party_type}:{party}", party
	if group_by == "Settlement Account":
		payment_type = str(payment.get("payment_type") or "")
		if payment_type == "Receive":
			value = str(payment.get("paid_to") or "").strip()
		elif payment_type == "Pay":
			value = str(payment.get("paid_from") or "").strip()
		elif payment_type == "Internal Transfer":
			source = str(payment.get("paid_from") or "").strip()
			target = str(payment.get("paid_to") or "").strip()
			value = " → ".join(part for part in (source, target) if part)
		else:
			value = ""
		value = value or _("Unspecified Settlement Account")
		return value, value
	frappe.throw(_("Unsupported Payment & Settlement Analysis dimension."))


def _period_group(value: Any, group_by: str) -> tuple[str, str]:
	resolved = getdate(value)
	if group_by == "Day":
		key = resolved.isoformat()
		return key, key
	if group_by == "Week":
		iso_year, iso_week, _weekday = resolved.isocalendar()
		key = f"{iso_year}-W{iso_week:02d}"
		return key, _("Week {0}, {1}").format(iso_week, iso_year)
	if group_by == "Month":
		key = f"{resolved.year}-{resolved.month:02d}"
		return key, resolved.strftime("%b %Y")
	if group_by == "Quarter":
		quarter = ((resolved.month - 1) // 3) + 1
		key = f"{resolved.year}-Q{quarter}"
		return key, _("Q{0} {1}").format(quarter, resolved.year)
	if group_by == "Year":
		key = str(resolved.year)
		return key, key
	frappe.throw(_("Unsupported payment period grouping."))


def _new_bucket(group_key: str, group_label: str) -> dict[str, Any]:
	return {
		"group_key": group_key,
		"group_label": group_label,
		"payment_count": 0,
		"receive_count": 0,
		"pay_count": 0,
		"transfer_count": 0,
		"money_in": 0.0,
		"money_out": 0.0,
		"transfer_amount": 0.0,
		"customer_receipts_allocated": 0.0,
		"customer_advance_available": 0.0,
		"multi_currency_exception_count": 0,
	}


def _add_payment(
	bucket: dict[str, Any],
	payment: frappe._dict,
	*,
	company_currency: str,
) -> None:
	payment_type = str(payment.get("payment_type") or "")
	base_paid = flt(payment.get("base_paid_amount"))
	base_received = flt(payment.get("base_received_amount"))
	bucket["payment_count"] += 1

	if payment_type == "Receive":
		bucket["receive_count"] += 1
		bucket["money_in"] += base_received
	elif payment_type == "Pay":
		bucket["pay_count"] += 1
		bucket["money_out"] += base_paid
	elif payment_type == "Internal Transfer":
		bucket["transfer_count"] += 1
		bucket["transfer_amount"] += max(abs(base_paid), abs(base_received))

	if payment_type != "Receive" or str(payment.get("party_type") or "") != "Customer":
		return

	party_currency = str(payment.get("paid_from_account_currency") or "").strip()
	if not party_currency or party_currency != company_currency:
		bucket["multi_currency_exception_count"] += 1
		return

	party_amount = base_paid
	unallocated = max(flt(payment.get("unallocated_amount")), 0.0)
	bucket["customer_advance_available"] += min(unallocated, max(party_amount, 0.0))
	bucket["customer_receipts_allocated"] += max(party_amount - unallocated, 0.0)


def _finalise_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
	row = dict(bucket)
	row["net_external_settlement"] = flt(row["money_in"]) - flt(row["money_out"])
	external_count = cint(row["receive_count"]) + cint(row["pay_count"])
	row["average_external_payment"] = (
		(flt(row["money_in"]) + flt(row["money_out"])) / external_count
		if external_count
		else 0.0
	)
	return row


def _columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "group_label", "label": _("Group"), "fieldtype": "Data"},
		{"fieldname": "payment_count", "label": _("Payments"), "fieldtype": "Int"},
		{"fieldname": "receive_count", "label": _("Receipts"), "fieldtype": "Int"},
		{"fieldname": "pay_count", "label": _("Payments Out"), "fieldtype": "Int"},
		{"fieldname": "transfer_count", "label": _("Transfers"), "fieldtype": "Int"},
		{"fieldname": "money_in", "label": _("Money In"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "money_out", "label": _("Money Out"), "fieldtype": "Currency", "options": currency},
		{
			"fieldname": "net_external_settlement",
			"label": _("Net External Settlement"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "transfer_amount",
			"label": _("Internal Transfers"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "customer_receipts_allocated",
			"label": _("Allocated Customer Receipts"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "customer_advance_available",
			"label": _("Available Customer Advances"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "average_external_payment",
			"label": _("Avg External Payment"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "multi_currency_exception_count",
			"label": _("Multi-currency Exceptions"),
			"fieldtype": "Int",
		},
	]


def _summary(rows: list[dict[str, Any]], *, currency: str) -> list[dict[str, Any]]:
	money_in = sum(flt(row.get("money_in")) for row in rows)
	money_out = sum(flt(row.get("money_out")) for row in rows)
	payment_count = sum(cint(row.get("payment_count")) for row in rows)
	receive_count = sum(cint(row.get("receive_count")) for row in rows)
	pay_count = sum(cint(row.get("pay_count")) for row in rows)
	external_count = receive_count + pay_count
	return [
		{"label": _("Money In"), "value": money_in, "datatype": "Currency", "currency": currency},
		{"label": _("Money Out"), "value": money_out, "datatype": "Currency", "currency": currency},
		{
			"label": _("Net External Settlement"),
			"value": money_in - money_out,
			"datatype": "Currency",
			"currency": currency,
		},
		{"label": _("Payment Entries"), "value": payment_count, "datatype": "Int"},
		{
			"label": _("Available Customer Advances"),
			"value": sum(flt(row.get("customer_advance_available")) for row in rows),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"label": _("Average External Payment"),
			"value": (money_in + money_out) / external_count if external_count else 0.0,
			"datatype": "Currency",
			"currency": currency,
		},
	]


def _page_response(
	dataset: dict[str, Any],
	*,
	page: int | str,
	page_size: int | str,
) -> dict[str, Any]:
	rows = list(dataset.get("rows") or [])
	resolved_page_size = max(
		25,
		min(cint(page_size) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE),
	)
	resolved_page = max(cint(page), 1)
	total_rows = len(rows)
	total_pages = max(1, ceil(total_rows / resolved_page_size))
	resolved_page = min(resolved_page, total_pages)
	start = (resolved_page - 1) * resolved_page_size
	end = start + resolved_page_size
	return {
		**dataset,
		"rows": rows[start:end],
		"pagination": {
			"page": resolved_page,
			"page_size": resolved_page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": resolved_page > 1,
			"has_next": resolved_page < total_pages,
		},
	}


def _export_response(dataset: dict[str, Any]) -> dict[str, Any]:
	return {
		"columns": dataset.get("columns") or [],
		"rows": dataset.get("rows") or [],
		"summary": dataset.get("summary") or [],
		"company_currency": dataset.get("company_currency") or "",
		"group_by": dataset.get("group_by") or DEFAULT_GROUP_BY,
		"scan": dataset.get("scan") or {},
		"metadata": dataset.get("metadata") or {},
	}


def _search_named(doctype: str, txt: str) -> list[dict[str, Any]]:
	if not frappe.has_permission(doctype, "read"):
		return []
	fields = ["name"]
	if doctype == "Company":
		fields.extend(["company_name", "default_currency"])
	elif doctype == "Customer":
		fields.append("customer_name")
	elif doctype == "Supplier":
		fields.append("supplier_name")
	rows = frappe.get_list(
		doctype,
		filters={"name": ["like", f"%{txt}%"]},
		fields=fields,
		order_by="name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	result = []
	for row in rows:
		label = (
			row.get("company_name")
			or row.get("customer_name")
			or row.get("supplier_name")
			or row.name
		)
		description = row.get("default_currency") or row.name
		result.append({"value": row.name, "label": label, "description": description})
	return result


def _search_branches(*, txt: str, company: str) -> list[dict[str, Any]]:
	if not company or not frappe.db.exists("DocType", "Branch"):
		return []
	scope = validate_report_scope(
		company=company,
		branch="",
		require_branch_when_restricted=False,
	)
	filters: dict[str, Any] = {}
	meta = frappe.get_meta("Branch")
	if meta.has_field("company"):
		filters["company"] = company
	if scope.get("restricted"):
		allowed = list(scope.get("allowed_branches") or [])
		if not allowed:
			return []
		filters["name"] = ["in", allowed]
	rows = frappe.get_list(
		"Branch",
		filters=filters,
		or_filters={"name": ["like", f"%{txt}%"]},
		fields=["name"],
		order_by="name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [{"value": row.name, "label": row.name} for row in rows]
