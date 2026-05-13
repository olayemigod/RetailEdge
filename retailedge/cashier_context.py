from __future__ import annotations

from datetime import datetime, time
from types import SimpleNamespace

import frappe
from frappe.utils import flt, get_datetime, now_datetime

from retailedge.integrations.branch_context import get_active_branch
from retailedge.utils.settings import get_retailedge_settings


WEAK_COST_CENTER_SOURCES = {"company", "single_company_cost_center", "main_cost_center", "not_found"}


def _safe_settings():
	try:
		return get_retailedge_settings()
	except Exception:
		return SimpleNamespace()


def _has_doctype(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype))


def _get_meta(doctype: str):
	if not _has_doctype(doctype):
		return None
	return frappe.get_meta(doctype)


def _get_existing_fields(doctype: str, candidates: list[str]) -> list[str]:
	meta = _get_meta(doctype)
	if not meta:
		return []
	return [fieldname for fieldname in candidates if meta.has_field(fieldname)]


def _find_first_field(doctype: str, candidates: list[str]) -> str | None:
	fields = _get_existing_fields(doctype, candidates)
	return fields[0] if fields else None


def _coerce_doc(doctype: str, value):
	if not value:
		return None
	if getattr(value, "doctype", None) == doctype:
		return value
	try:
		return frappe.get_doc(doctype, value)
	except Exception:
		return None


def _is_cash_mode(mode_of_payment: str | None) -> bool:
	if not mode_of_payment:
		return False
	if str(mode_of_payment).strip().lower() == "cash":
		return True
	if not _has_doctype("Mode of Payment"):
		return False
	mode_type_field = _find_first_field("Mode of Payment", ["type", "mode_of_payment_type"])
	if not mode_type_field:
		return False
	try:
		mode_type = frappe.db.get_value("Mode of Payment", mode_of_payment, mode_type_field)
	except Exception:
		return False
	return str(mode_type or "").strip().lower() == "cash"


def _get_cash_mode_name() -> str | None:
	if not _has_doctype("Mode of Payment"):
		return None
	try:
		if frappe.db.exists("Mode of Payment", "Cash"):
			return "Cash"
	except Exception:
		pass
	mode_type_field = _find_first_field("Mode of Payment", ["type", "mode_of_payment_type"])
	if not mode_type_field:
		return None
	try:
		return frappe.db.get_value("Mode of Payment", {mode_type_field: "Cash"}, "name")
	except Exception:
		return None


def _find_cash_row(rows) -> dict | None:
	for row in rows or []:
		row_dict = row.as_dict() if hasattr(row, "as_dict") else dict(row)
		mode_name = None
		for fieldname in ("mode_of_payment", "payment_method", "payment_mode"):
			if row_dict.get(fieldname):
				mode_name = row_dict.get(fieldname)
				break
		if _is_cash_mode(mode_name):
			return row_dict
	return None


def _find_cash_row_by_mode(rows, preferred_modes: list[str] | None = None) -> dict | None:
	preferred_modes = [str(mode).strip() for mode in (preferred_modes or []) if mode]
	if not preferred_modes:
		return None
	for row in rows or []:
		row_dict = row.as_dict() if hasattr(row, "as_dict") else dict(row)
		row_mode = (
			row_dict.get("mode_of_payment")
			or row_dict.get("payment_method")
			or row_dict.get("payment_mode")
		)
		if row_mode and str(row_mode).strip() in preferred_modes:
			return row_dict
	return None


def _get_pos_profile_cash_mode(pos_profile: str | None) -> str | None:
	profile_doc = _coerce_doc("POS Profile", pos_profile)
	if not profile_doc:
		return None
	return _get_doc_value(
		profile_doc,
		["posa_cash_mode_of_payment", "cash_mode_of_payment", "default_cash_mode_of_payment"],
	)


def _extract_amount_from_row(row_dict: dict) -> float:
	for fieldname in ("opening_amount", "amount", "balance", "opening_balance", "base_amount"):
		if row_dict.get(fieldname) is not None:
			return flt(row_dict.get(fieldname))
	return 0.0


def _get_doc_value(doc, candidates: list[str]):
	for fieldname in candidates:
		if getattr(doc, fieldname, None):
			return getattr(doc, fieldname)
	return None


def _coerce_datetime(value):
	if not value:
		return None
	if isinstance(value, datetime):
		return value
	try:
		return get_datetime(value)
	except Exception:
		return None


def _combine_posting_datetime(date_value, time_value=None):
	date_dt = _coerce_datetime(date_value)
	if not date_dt:
		return None
	if isinstance(time_value, datetime):
		time_value = time_value.time()
	elif hasattr(time_value, "seconds") and not isinstance(time_value, time):
		try:
			time_value = (datetime.min + time_value).time()
		except Exception:
			time_value = None
	try:
		resolved_time = time_value or time.min
		return datetime.combine(date_dt.date(), resolved_time)
	except Exception:
		return date_dt


def _get_invoice_datetime(doc):
	posting_date = getattr(doc, "posting_date", None)
	posting_time = getattr(doc, "posting_time", None)
	return _combine_posting_datetime(posting_date, posting_time) or _coerce_datetime(getattr(doc, "creation", None))


def _within_window(value, start, end) -> bool:
	value_dt = _coerce_datetime(value)
	start_dt = _coerce_datetime(start)
	end_dt = _coerce_datetime(end)
	if not value_dt:
		return False
	if start_dt and value_dt < start_dt:
		return False
	if end_dt and value_dt > end_dt:
		return False
	return True


def _get_coreedge_branch_value(user: str | None = None):
	try:
		result = get_active_branch(user=user)
	except Exception:
		return None
	if isinstance(result, dict):
		return result.get("branch") or result.get("active_branch") or result.get("branch_name") or result.get("name")
	if isinstance(result, str):
		return result
	return None


def _cost_center_matches_company(cost_center: str | None, company: str | None) -> bool:
	if not cost_center or not company or not _has_doctype("Cost Center"):
		return True
	company_field = _find_first_field("Cost Center", ["company"])
	if not company_field:
		return True
	try:
		cost_center_company = frappe.db.get_value("Cost Center", cost_center, company_field)
	except Exception:
		return False
	return not cost_center_company or cost_center_company == company


def _is_valid_cost_center(cost_center: str | None, company: str | None) -> bool:
	if not cost_center or not _has_doctype("Cost Center"):
		return False
	try:
		if not frappe.db.exists("Cost Center", cost_center):
			return False
	except Exception:
		return False
	if not _cost_center_matches_company(cost_center, company):
		return False
	is_group_field = _find_first_field("Cost Center", ["is_group"])
	if is_group_field:
		try:
			if frappe.db.get_value("Cost Center", cost_center, is_group_field):
				return False
		except Exception:
			return False
	return True


def resolve_branch(
	company: str | None = None,
	pos_profile: str | None = None,
	opening_shift=None,
	user: str | None = None,
) -> dict[str, object]:
	opening_shift_doc = _coerce_doc("POS Opening Shift", opening_shift)
	branch_fields = ["branch", "set_branch", "service_branch", "retail_branch"]
	if opening_shift_doc:
		branch_value = _get_doc_value(opening_shift_doc, branch_fields)
		if branch_value:
			return {"branch": branch_value, "source": "opening_shift", "message": None}

	profile_doc = _coerce_doc("POS Profile", pos_profile)
	if profile_doc:
		branch_value = _get_doc_value(profile_doc, branch_fields)
		if branch_value:
			return {"branch": branch_value, "source": "pos_profile", "message": None}

	coreedge_branch = _get_coreedge_branch_value(user=user)
	if coreedge_branch:
		return {"branch": coreedge_branch, "source": "coreedge", "message": None}

	try:
		user_default_branch = frappe.defaults.get_user_default("Branch", user=user) or frappe.defaults.get_user_default("Branch")
	except Exception:
		user_default_branch = None
	if user_default_branch:
		return {"branch": user_default_branch, "source": "user_default", "message": None}

	if _has_doctype("Branch"):
		try:
			meta = frappe.get_meta("Branch")
			fields = ["name"]
			if meta.has_field("company"):
				fields.append("company")
			branches = frappe.get_all("Branch", fields=fields, limit_page_length=0)
		except Exception:
			branches = []
		has_company_field = bool(meta.has_field("company")) if 'meta' in locals() and meta else False
		if company and has_company_field:
			company_branches = [row for row in branches if getattr(row, "company", None) == company]
		else:
			company_branches = branches
		if len(company_branches) == 1:
			return {"branch": company_branches[0].name, "source": "single_company_branch", "message": None}

	return {
		"branch": None,
		"source": "not_found",
		"message": "Branch could not be resolved from opening shift, POS profile, CoreEdge, or defaults.",
	}


def resolve_cost_center(
	company: str | None = None,
	pos_profile: str | None = None,
	opening_shift=None,
	branch: str | None = None,
	expense_category: str | None = None,
) -> dict[str, object]:
	if expense_category and _has_doctype("RetailEdge Expense Category"):
		try:
			category_cost_center = frappe.db.get_value("RetailEdge Expense Category", expense_category, "default_cost_center")
		except Exception:
			category_cost_center = None
		if category_cost_center and _is_valid_cost_center(category_cost_center, company):
			return {"cost_center": category_cost_center, "source": "expense_category", "message": None}

	opening_shift_doc = _coerce_doc("POS Opening Shift", opening_shift)
	cost_center_fields = ["cost_center", "expense_cost_center", "default_cost_center"]
	if opening_shift_doc:
		cost_center = _get_doc_value(opening_shift_doc, cost_center_fields)
		if cost_center and _is_valid_cost_center(cost_center, company):
			return {"cost_center": cost_center, "source": "opening_shift", "message": None}

	profile_doc = _coerce_doc("POS Profile", pos_profile)
	if profile_doc:
		cost_center = _get_doc_value(profile_doc, ["cost_center", "write_off_cost_center", "expense_cost_center", "default_cost_center"])
		if cost_center and _is_valid_cost_center(cost_center, company):
			return {"cost_center": cost_center, "source": "pos_profile", "message": None}

	if branch and _has_doctype("Branch"):
		branch_doc = _coerce_doc("Branch", branch)
		if branch_doc:
			cost_center = _get_doc_value(branch_doc, ["cost_center", "default_cost_center"])
			if cost_center and _is_valid_cost_center(cost_center, company):
				return {"cost_center": cost_center, "source": "branch", "message": None}

	if company and _has_doctype("Company"):
		company_doc = _coerce_doc("Company", company)
		if company_doc:
			cost_center = _get_doc_value(company_doc, ["cost_center", "default_cost_center"])
			if cost_center and _is_valid_cost_center(cost_center, company):
				return {"cost_center": cost_center, "source": "company", "message": None}

	if _has_doctype("Cost Center"):
		try:
			meta = frappe.get_meta("Cost Center")
			fields = ["name"]
			if meta.has_field("company"):
				fields.append("company")
			if meta.has_field("is_group"):
				fields.append("is_group")
			cost_centers = frappe.get_all("Cost Center", fields=fields, limit_page_length=0, order_by="name asc")
		except Exception:
			cost_centers = []
		valid_centers = []
		for row in cost_centers:
			if getattr(row, "company", None) and company and getattr(row, "company", None) != company:
				continue
			if getattr(row, "is_group", 0):
				continue
			valid_centers.append(row)
		if len(valid_centers) == 1:
			return {"cost_center": valid_centers[0].name, "source": "single_company_cost_center", "message": None}
		main_match = next((row for row in valid_centers if "main" in str(row.name).lower()), None)
		if main_match:
			return {"cost_center": main_match.name, "source": "main_cost_center", "message": None}

	return {
		"cost_center": None,
		"source": "not_found",
		"message": "Cost Center could not be resolved from expense category, POS profile, branch, company, or defaults.",
	}


def find_open_pos_opening_shift(user: str | None = None, company: str | None = None):
	user = user or frappe.session.user
	if not _has_doctype("POS Opening Shift"):
		return None

	user_fields = _get_existing_fields("POS Opening Shift", ["user", "cashier", "owner"])
	status_field = _find_first_field("POS Opening Shift", ["status"])
	company_field = _find_first_field("POS Opening Shift", ["company"])
	sort_field = _find_first_field("POS Opening Shift", ["period_start_date", "opening_date", "creation", "modified"]) or "creation"
	fields = ["name"]
	for fieldname in {"company", "pos_profile", "branch", "cost_center", "status", "docstatus", *user_fields}:
		if fieldname == "docstatus" or fieldname in _get_existing_fields("POS Opening Shift", [fieldname]):
			fields.append(fieldname)
	fields = list(dict.fromkeys(fields))

	filter_sets = []
	base_filters = []
	for user_field in user_fields or ["owner"]:
		filters = {user_field: user, "docstatus": ["in", [0, 1]]}
		if status_field:
			filters[status_field] = ["in", ["Open", "Opened"]]
		if company and company_field:
			filters[company_field] = company
		base_filters.append(filters)
		if company and company_field:
			fallback = dict(filters)
			fallback.pop(company_field, None)
			filter_sets.append(fallback)
	filter_sets = base_filters + filter_sets

	for filters in filter_sets:
		try:
			rows = frappe.get_all(
				"POS Opening Shift",
				filters=filters,
				fields=fields,
				order_by=f"{sort_field} desc, creation desc",
				limit=1,
			)
		except Exception:
			continue
		if rows:
			return _coerce_doc("POS Opening Shift", rows[0].name)

	return None


def resolve_cash_payment_account(company: str | None = None, pos_profile: str | None = None, opening_shift=None) -> dict[str, object]:
	preferred_cash_mode = _get_pos_profile_cash_mode(pos_profile)
	candidate_cash_modes = [preferred_cash_mode, _get_cash_mode_name()]
	opening_shift_doc = _coerce_doc("POS Opening Shift", opening_shift)
	if opening_shift_doc:
		for table_field in ("balance_details", "payments", "opening_balance_details", "payment_reconciliation"):
			if not hasattr(opening_shift_doc, table_field):
				continue
			rows = getattr(opening_shift_doc, table_field)
			row_dict = _find_cash_row_by_mode(rows, candidate_cash_modes) or _find_cash_row(rows)
			if not row_dict:
				continue
			for account_field in ("account", "default_account", "payment_account", "account_head"):
				if row_dict.get(account_field):
					return {
						"payment_account": row_dict.get(account_field),
						"mode_of_payment": row_dict.get("mode_of_payment") or row_dict.get("payment_method") or row_dict.get("payment_mode"),
						"source": f"opening_shift.{table_field}",
						"message": None,
					}

	if pos_profile:
		profile_doc = _coerce_doc("POS Profile", pos_profile)
		if profile_doc:
			if preferred_cash_mode and company and _has_doctype("Mode of Payment Account"):
				try:
					account = frappe.db.get_value(
						"Mode of Payment Account",
						{"parent": preferred_cash_mode, "company": company},
						"default_account",
					)
				except Exception:
					account = None
				if account:
					return {
						"payment_account": account,
						"mode_of_payment": preferred_cash_mode,
						"source": "pos_profile.posa_cash_mode_of_payment",
						"message": None,
					}
			for table_field in ("payments", "payment_methods"):
				if not hasattr(profile_doc, table_field):
					continue
				rows = getattr(profile_doc, table_field)
				row_dict = _find_cash_row_by_mode(rows, candidate_cash_modes) or _find_cash_row(rows)
				if not row_dict:
					continue
				for account_field in ("default_account", "account", "payment_account", "account_head"):
					if row_dict.get(account_field):
						return {
							"payment_account": row_dict.get(account_field),
							"mode_of_payment": row_dict.get("mode_of_payment") or row_dict.get("payment_method") or row_dict.get("payment_mode"),
							"source": f"pos_profile.{table_field}",
							"message": None,
						}

	if _has_doctype("Mode of Payment Account") and company:
		for cash_mode in candidate_cash_modes:
			if not cash_mode:
				continue
			try:
				account = frappe.db.get_value(
					"Mode of Payment Account",
					{"parent": cash_mode, "company": company},
					"default_account",
				)
			except Exception:
				account = None
			if account:
				return {
					"payment_account": account,
					"mode_of_payment": cash_mode,
					"source": "mode_of_payment_account",
					"message": None,
				}

	return {
		"payment_account": None,
		"mode_of_payment": None,
		"source": "unresolved",
		"message": "RetailEdge could not resolve a cash payment account from the current shift or POS profile.",
	}


def _find_matching_pos_closing_shift(opening_shift_doc):
	if not opening_shift_doc or not _has_doctype("POS Closing Shift"):
		return None
	link_field = _find_first_field("POS Closing Shift", ["pos_opening_shift", "opening_shift", "linked_pos_opening_shift"])
	if not link_field:
		return None
	try:
		rows = frappe.get_all(
			"POS Closing Shift",
			filters={link_field: opening_shift_doc.name, "docstatus": ["in", [0, 1]]},
			fields=["name"],
			order_by="creation desc",
			limit=1,
		)
	except Exception:
		return None
	if not rows:
		return None
	return _coerce_doc("POS Closing Shift", rows[0].name)


def _get_shift_window(opening_shift=None, company: str | None = None, pos_profile: str | None = None, user: str | None = None):
	opening_shift_doc = _coerce_doc("POS Opening Shift", opening_shift)
	if not opening_shift_doc:
		return {
			"opening_shift": None,
			"closing_shift": None,
			"company": company,
			"pos_profile": pos_profile,
			"user": user,
			"shift_start": None,
			"shift_end": None,
		}

	resolved_company = company or getattr(opening_shift_doc, "company", None)
	resolved_profile = pos_profile or getattr(opening_shift_doc, "pos_profile", None)
	resolved_user = user or getattr(opening_shift_doc, "user", None) or getattr(opening_shift_doc, "owner", None)

	shift_start = None
	for fieldname in ("period_start_date", "opening_date", "posting_date", "creation"):
		if not hasattr(opening_shift_doc, fieldname):
			continue
		value = getattr(opening_shift_doc, fieldname)
		if fieldname == "posting_date":
			value = _combine_posting_datetime(value)
		shift_start = _coerce_datetime(value)
		if shift_start:
			break

	closing_shift_doc = _find_matching_pos_closing_shift(opening_shift_doc)
	shift_end = None
	if closing_shift_doc:
		for fieldname in ("period_end_date", "closing_date", "posting_date", "modified", "creation"):
			if not hasattr(closing_shift_doc, fieldname):
				continue
			value = getattr(closing_shift_doc, fieldname)
			if fieldname == "posting_date":
				value = _combine_posting_datetime(value)
			shift_end = _coerce_datetime(value)
			if shift_end:
				break
	if not shift_end:
		shift_end = now_datetime()

	return {
		"opening_shift": opening_shift_doc,
		"closing_shift": closing_shift_doc,
		"company": resolved_company,
		"pos_profile": resolved_profile,
		"user": resolved_user,
		"shift_start": shift_start,
		"shift_end": shift_end,
	}


def get_shift_cash_sales(
	opening_shift=None,
	company: str | None = None,
	pos_profile: str | None = None,
	user: str | None = None,
) -> dict[str, object]:
	window = _get_shift_window(opening_shift=opening_shift, company=company, pos_profile=pos_profile, user=user)
	opening_shift_doc = window["opening_shift"]
	result = {
		"cash_sales": 0.0,
		"source": "unresolved",
		"mode_of_payment": None,
		"payment_account": None,
		"matched_invoice_count": 0,
		"matched_payment_count": 0,
		"message": None,
	}
	if not opening_shift_doc or not _has_doctype("Sales Invoice"):
		result["message"] = "Cash sales could not be safely resolved for this POS schema."
		return result

	account_context = resolve_cash_payment_account(
		company=window["company"],
		pos_profile=window["pos_profile"],
		opening_shift=opening_shift_doc,
	)
	cash_mode = account_context.get("mode_of_payment") or _get_cash_mode_name()
	cash_account = account_context.get("payment_account")
	result["mode_of_payment"] = cash_mode
	result["payment_account"] = cash_account

	try:
		sales_invoice_meta = frappe.get_meta("Sales Invoice")
	except Exception:
		sales_invoice_meta = None
	try:
		payment_meta = frappe.get_meta("Sales Invoice Payment") if _has_doctype("Sales Invoice Payment") else None
	except Exception:
		payment_meta = None

	if sales_invoice_meta and sales_invoice_meta.has_field("payments") and payment_meta:
		filters = {"docstatus": 1}
		if sales_invoice_meta.has_field("is_pos"):
			filters["is_pos"] = 1
		if window["company"] and sales_invoice_meta.has_field("company"):
			filters["company"] = window["company"]

		opening_shift_field = _find_first_field("Sales Invoice", ["posa_pos_opening_shift", "pos_opening_shift", "opening_shift"])
		pos_profile_field = _find_first_field("Sales Invoice", ["pos_profile"])
		if opening_shift_field:
			filters[opening_shift_field] = opening_shift_doc.name
		elif window["pos_profile"] and pos_profile_field:
			filters[pos_profile_field] = window["pos_profile"]

		try:
			invoice_rows = frappe.get_all("Sales Invoice", filters=filters, fields=["name"], limit_page_length=0, order_by="creation asc")
		except Exception:
			invoice_rows = []

		cash_sales = 0.0
		matched_invoices = 0
		matched_payments = 0
		for row in invoice_rows:
			invoice = _coerce_doc("Sales Invoice", row.name)
			if not invoice:
				continue
			if not opening_shift_field and not _within_window(_get_invoice_datetime(invoice), window["shift_start"], window["shift_end"]):
				continue
			payment_rows = getattr(invoice, "payments", []) or []
			invoice_cash = 0.0
			invoice_payment_matches = 0
			for payment_row in payment_rows:
				row_dict = payment_row.as_dict() if hasattr(payment_row, "as_dict") else dict(payment_row)
				mode_name = row_dict.get("mode_of_payment")
				account_name = row_dict.get("account") or row_dict.get("default_account")
				if not (_is_cash_mode(mode_name) or (cash_account and account_name == cash_account)):
					continue
				amount = flt(row_dict.get("base_amount") if row_dict.get("base_amount") is not None else row_dict.get("amount"))
				if amount <= 0:
					continue
				invoice_cash += amount
				invoice_payment_matches += 1
			if invoice_payment_matches:
				cash_sales += invoice_cash
				matched_invoices += 1
				matched_payments += invoice_payment_matches

		if matched_payments:
			result.update(
				{
					"cash_sales": cash_sales,
					"source": "sales_invoice.payments",
					"matched_invoice_count": matched_invoices,
					"matched_payment_count": matched_payments,
				}
			)
			return result

	closing_shift_doc = window["closing_shift"]
	if closing_shift_doc:
		for table_field in ("payment_reconciliation", "payment_reconciliation_details", "pos_payments"):
			if not hasattr(closing_shift_doc, table_field):
				continue
			rows = getattr(closing_shift_doc, table_field) or []
			row_dict = _find_cash_row(rows)
			if not row_dict:
				continue
			amount = None
			for fieldname in ("expected_amount", "closing_amount", "amount", "base_amount"):
				if row_dict.get(fieldname) is not None:
					amount = flt(row_dict.get(fieldname))
					break
			opening_amount = flt(row_dict.get("opening_amount"))
			if amount is None:
				continue
			cash_sales = max(flt(amount) - opening_amount, 0.0) if row_dict.get("opening_amount") is not None else flt(amount)
			result.update(
				{
					"cash_sales": cash_sales,
					"source": f"pos_closing_shift.{table_field}",
					"matched_invoice_count": len(getattr(closing_shift_doc, "pos_transactions", []) or []),
					"matched_payment_count": 1,
					"message": "Cash sales were resolved from POS Closing Shift reconciliation because invoice payment rows were not safely matched.",
				}
			)
			return result

	result["message"] = "Cash sales could not be safely resolved for this POS schema."
	return result


def debug_shift_cash_sales(opening_shift):
	window = _get_shift_window(opening_shift=opening_shift)
	opening_shift_doc = window["opening_shift"]
	cash_sales = get_shift_cash_sales(
		opening_shift=opening_shift_doc,
		company=window["company"],
		pos_profile=window["pos_profile"],
		user=window["user"],
	)
	debug = {
		"opening_shift": getattr(opening_shift_doc, "name", None),
		"company": window["company"],
		"pos_profile": window["pos_profile"],
		"cash_mode": cash_sales.get("mode_of_payment"),
		"cash_account": cash_sales.get("payment_account"),
		"shift_start": window["shift_start"],
		"shift_end": window["shift_end"],
		"matched_invoices": [],
		"matched_invoice_count": 0,
		"cash_sales": cash_sales.get("cash_sales", 0.0),
		"source": cash_sales.get("source"),
		"messages": [part for part in [cash_sales.get("message")] if part],
	}
	if not opening_shift_doc or not _has_doctype("Sales Invoice"):
		return debug

	filters = {"docstatus": 1}
	try:
		sales_invoice_meta = frappe.get_meta("Sales Invoice")
	except Exception:
		sales_invoice_meta = None
	if sales_invoice_meta and sales_invoice_meta.has_field("is_pos"):
		filters["is_pos"] = 1
	opening_shift_field = _find_first_field("Sales Invoice", ["posa_pos_opening_shift", "pos_opening_shift", "opening_shift"])
	if opening_shift_field:
		filters[opening_shift_field] = opening_shift_doc.name
	elif window["pos_profile"] and sales_invoice_meta and sales_invoice_meta.has_field("pos_profile"):
		filters["pos_profile"] = window["pos_profile"]
	if window["company"] and sales_invoice_meta and sales_invoice_meta.has_field("company"):
		filters["company"] = window["company"]

	try:
		invoice_rows = frappe.get_all("Sales Invoice", filters=filters, fields=["name"], limit_page_length=0, order_by="creation asc")
	except Exception as exc:
		debug["messages"].append(str(exc))
		return debug

	for row in invoice_rows:
		invoice = _coerce_doc("Sales Invoice", row.name)
		if not invoice:
			continue
		invoice_dt = _get_invoice_datetime(invoice)
		if not opening_shift_field and not _within_window(invoice_dt, window["shift_start"], window["shift_end"]):
			continue
		payment_rows = []
		for payment_row in getattr(invoice, "payments", []) or []:
			row_dict = payment_row.as_dict() if hasattr(payment_row, "as_dict") else dict(payment_row)
			payment_rows.append(row_dict)
		debug["matched_invoices"].append(
			{
				"name": invoice.name,
				"posting_datetime": invoice_dt,
				"payments": payment_rows,
			}
		)
	debug["matched_invoice_count"] = len(debug["matched_invoices"])
	return debug


def get_current_cashier_context(user: str | None = None, company: str | None = None) -> dict[str, object]:
	user = user or frappe.session.user
	context = {
		"user": user,
		"company": company or None,
		"branch": None,
		"branch_source": "not_found",
		"pos_profile": None,
		"payment_account": None,
		"cost_center": None,
		"cost_center_source": "not_found",
		"linked_pos_opening_shift": None,
		"opening_shift_status": None,
		"source": "manual_fallback",
		"message": None,
	}

	opening_shift = find_open_pos_opening_shift(user=user, company=company)
	if not opening_shift:
		context["message"] = "No open POS Opening Shift found for this user. Please open a POS shift before recording cashier expenses."
		return context

	context["linked_pos_opening_shift"] = opening_shift.name
	context["source"] = "pos_opening_shift"
	for fieldname in ("status",):
		if hasattr(opening_shift, fieldname):
			context["opening_shift_status"] = getattr(opening_shift, fieldname)
			break

	shift_company = getattr(opening_shift, "company", None)
	shift_profile = getattr(opening_shift, "pos_profile", None)
	if shift_company and not context["company"]:
		context["company"] = shift_company
	if shift_profile:
		context["pos_profile"] = shift_profile

	profile_doc = _coerce_doc("POS Profile", context["pos_profile"])
	if profile_doc:
		context["source"] = "pos_profile"
		if not context["company"] and getattr(profile_doc, "company", None):
			context["company"] = profile_doc.company

	account_context = resolve_cash_payment_account(
		company=context["company"],
		pos_profile=context["pos_profile"],
		opening_shift=opening_shift,
	)
	context["payment_account"] = account_context.get("payment_account")
	branch_context = resolve_branch(
		company=context["company"],
		pos_profile=context["pos_profile"],
		opening_shift=opening_shift,
		user=user,
	)
	context["branch"] = branch_context.get("branch")
	context["branch_source"] = branch_context.get("source", "not_found")
	if branch_context.get("source") == "coreedge":
		context["source"] = "coreedge"

	cost_center_context = resolve_cost_center(
		company=context["company"],
		pos_profile=context["pos_profile"],
		opening_shift=opening_shift,
		branch=context["branch"],
	)
	context["cost_center"] = cost_center_context.get("cost_center")
	context["cost_center_source"] = cost_center_context.get("source", "not_found")

	message_parts = [
		part
		for part in [
			account_context.get("message"),
			branch_context.get("message"),
			cost_center_context.get("message"),
		]
		if part
	]
	if message_parts:
		context["message"] = "\n".join(message_parts)

	return context


def get_shift_cash_snapshot(
	opening_shift=None,
	company: str | None = None,
	pos_profile: str | None = None,
	user: str | None = None,
	expense_name: str | None = None,
) -> dict[str, object]:
	settings = _safe_settings()
	opening_shift_doc = _coerce_doc("POS Opening Shift", opening_shift)
	result = {
		"opening_cash": 0.0,
		"cash_sales": 0.0,
		"prior_expenses": 0.0,
		"available_before": 0.0,
		"source": "unresolved",
		"message": None,
	}

	opening_row = None
	if opening_shift_doc:
		for table_field in ("balance_details", "payments", "opening_balance_details", "payment_reconciliation"):
			if not hasattr(opening_shift_doc, table_field):
				continue
			opening_row = _find_cash_row(getattr(opening_shift_doc, table_field))
			if opening_row:
				result["opening_cash"] = _extract_amount_from_row(opening_row)
				result["source"] = f"opening_shift.{table_field}"
				break

	if not opening_row:
		result["message"] = "RetailEdge could not safely resolve opening cash from the POS Opening Shift, so opening cash is treated as zero."

	sales_result = get_shift_cash_sales(
		opening_shift=opening_shift_doc,
		company=company or getattr(opening_shift_doc, "company", None),
		pos_profile=pos_profile or getattr(opening_shift_doc, "pos_profile", None),
		user=user,
	)
	result["cash_sales"] = flt(sales_result.get("cash_sales", 0.0))

	statuses = ["Submitted", "Pending Ledger", "Posted", "Approved"]
	if getattr(settings, "include_draft_cashier_expenses_in_cash_check", 1):
		statuses.append("Draft")
	if getattr(settings, "include_rejected_cashier_expenses_in_cash_check", 1):
		statuses.append("Rejected")

	if opening_shift_doc:
		filters = {
			"linked_pos_opening_shift": opening_shift_doc.name,
			"expense_status": ["in", sorted(set(statuses))],
			"docstatus": ["!=", 2],
		}
		if expense_name:
			filters["name"] = ["!=", expense_name]
		try:
			expenses = frappe.get_all(
				"RetailEdge Cashier Expense",
				filters=filters,
				fields=["amount"],
				limit_page_length=0,
			)
		except Exception:
			expenses = []
		result["prior_expenses"] = sum(flt(row.amount) for row in expenses)

	result["available_before"] = flt(result["opening_cash"]) + flt(result["cash_sales"]) - flt(result["prior_expenses"])
	source_parts = [result["source"]]
	if sales_result.get("source") and sales_result.get("source") != "unresolved":
		source_parts.append(sales_result["source"])
	source_parts.append("retailedge_expenses")
	result["source"] = " + ".join([part for part in source_parts if part])
	message_parts = [part for part in [result.get("message"), sales_result.get("message")] if part]
	result["message"] = "\n".join(message_parts) if message_parts else None
	return result


def get_cashier_expense_entry_context(user: str | None = None, company: str | None = None) -> dict[str, object]:
	settings = _safe_settings()
	context = get_current_cashier_context(user=user, company=company)
	snapshot = get_shift_cash_snapshot(
		opening_shift=context.get("linked_pos_opening_shift"),
		company=context.get("company"),
		pos_profile=context.get("pos_profile"),
		user=context.get("user"),
	)

	message_parts = [part for part in [context.get("message"), snapshot.get("message")] if part]
	return {
		**context,
		"shift_opening_cash_amount": snapshot.get("opening_cash", 0.0),
		"shift_cash_sales_amount": snapshot.get("cash_sales", 0.0),
		"prior_shift_expense_amount": snapshot.get("prior_expenses", 0.0),
		"available_shift_cash_before_expense": snapshot.get("available_before", 0.0),
		"available_shift_cash_after_expense": snapshot.get("available_before", 0.0),
		"cash_balance_source": snapshot.get("source"),
		"cash_control_message": "\n".join(message_parts) if message_parts else None,
		"settings": {
			"require_open_shift_for_cashier_expense": int(bool(getattr(settings, "require_open_shift_for_cashier_expense", 1))),
			"allow_cashier_expense_date_edit": int(bool(getattr(settings, "allow_cashier_expense_date_edit", 0))),
			"include_draft_cashier_expenses_in_cash_check": int(bool(getattr(settings, "include_draft_cashier_expenses_in_cash_check", 1))),
			"include_rejected_cashier_expenses_in_cash_check": int(bool(getattr(settings, "include_rejected_cashier_expenses_in_cash_check", 1))),
			"allow_cashier_expense_without_cash_account": int(bool(getattr(settings, "allow_cashier_expense_without_cash_account", 0))),
		},
	}
