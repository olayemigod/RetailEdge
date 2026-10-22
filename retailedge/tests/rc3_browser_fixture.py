from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate

from retailedge.professional_quotation import create_professional_quotation_draft
from retailedge.tests.browser_persona_fixture import _ensure_user, seed_browser_personas
from retailedge.tests.upgrade_validation_fixture import (
	COMPANY,
	CUSTOMER,
	ITEM,
	PRICE_LIST,
	_ensure_customer,
	_ensure_item,
	_first_cost_center,
	_first_leaf_account,
)

BRANCHES = (
	"RetailEdge RC3 Lagos",
	"RetailEdge RC3 Ikeja",
	"RetailEdge RC3 Abuja",
)
BRANCH_WITHOUT_DEFAULTS = "RetailEdge RC3 Ikeja"
EXPENSE_CATEGORY = "Browser Working Branch Expense"

EXTRA_PERSONAS = {
	"browser-branch-manager@example.com": ("Browser Branch Manager", ("RetailEdgeBranchManager",)),
	"browser-purchasing@example.com": ("Browser Purchasing", ("Purchase User", "Accounts User")),
	"browser-sales@example.com": ("Browser Sales", ("Sales User", "Accounts User")),
	"browser-stock-manager@example.com": ("Browser Stock Manager", ("Stock Manager",)),
	"browser-one-branch@example.com": (
		"Browser One Branch",
		("RetailEdgeBranchManager", "Stock User", "Sales User"),
	),
	"browser-multi-branch@example.com": (
		"Browser Multi Branch",
		("RetailEdgeBranchManager", "Stock User", "Sales User", "Accounts User"),
	),
	"browser-zero-branch@example.com": ("Browser Zero Branch", ("RetailEdgeBranchManager", "Stock User")),
	"browser-native@example.com": ("Browser Native Advanced", ("System Manager",)),
	"browser-global-branch@example.com": (
		"Browser Global Branch",
		("System Manager", "Sales Manager", "Accounts Manager", "Stock Manager", "Purchase Manager"),
	),
}

ACTIVE_ASSIGNMENTS = {
	"Administrator": (("RetailEdge RC3 Lagos", "Manager", 1),),
	"browser-manager@example.com": (("RetailEdge RC3 Lagos", "Manager", 1),),
	"browser-branch-manager@example.com": (("RetailEdge RC3 Lagos", "Manager", 1),),
	"browser-cashier@example.com": (("RetailEdge RC3 Lagos", "Cashier", 1),),
	"browser-accounts@example.com": (("RetailEdge RC3 Lagos", "Accounts", 1),),
	"browser-stock@example.com": (("RetailEdge RC3 Lagos", "Stock", 1),),
	"browser-stock-manager@example.com": (("RetailEdge RC3 Lagos", "Stock", 1),),
	"browser-purchasing@example.com": (("RetailEdge RC3 Lagos", "Purchasing", 1),),
	"browser-sales@example.com": (("RetailEdge RC3 Lagos", "Sales", 1),),
	"browser-one-branch@example.com": (("RetailEdge RC3 Lagos", "Stock", 1),),
	"browser-multi-branch@example.com": (
		("RetailEdge RC3 Lagos", "Stock", 1),
		("RetailEdge RC3 Ikeja", "Stock", 0),
	),
}

ENDED_ASSIGNMENTS = {
	"browser-zero-branch@example.com": (("RetailEdge RC3 Abuja", "Stock"),),
}


def _ensure_branch(branch_name: str) -> None:
	if frappe.db.exists("Branch", branch_name):
		return
	branch = frappe.new_doc("Branch")
	branch.branch = branch_name
	branch.insert(ignore_permissions=True)


def _ensure_warehouse(branch_name: str) -> str:
	warehouse_name = f"{branch_name} Stock"
	existing = frappe.db.get_value(
		"Warehouse",
		{"warehouse_name": warehouse_name, "company": COMPANY},
		"name",
	)
	if existing:
		return str(existing)

	parent_warehouse = frappe.db.get_value(
		"Warehouse",
		{"company": COMPANY, "is_group": 1},
		"name",
		order_by="lft asc",
	)
	if not parent_warehouse:
		frappe.throw(f"No Warehouse root exists for {COMPANY}.")

	warehouse = frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": warehouse_name,
			"company": COMPANY,
			"parent_warehouse": parent_warehouse,
			"is_group": 0,
			"disabled": 0,
		}
	).insert(ignore_permissions=True)
	return str(warehouse.name)


def _ensure_branch_profile(
	branch_name: str,
	*,
	default_warehouse: str = "",
	is_default: bool = False,
) -> None:
	profile_name = f"RC3 {branch_name}"
	if frappe.db.exists("RetailEdge Branch Profile", profile_name):
		profile = frappe.get_doc("RetailEdge Branch Profile", profile_name)
		changed = False
		if (profile.default_warehouse or "") != default_warehouse:
			profile.default_warehouse = default_warehouse or None
			changed = True
		if int(profile.enabled or 0) != 1:
			profile.enabled = 1
			changed = True
		if int(profile.is_default_for_company or 0) != (1 if is_default else 0):
			profile.is_default_for_company = 1 if is_default else 0
			changed = True
		if changed:
			profile.save(ignore_permissions=True)
		return
	frappe.get_doc(
		{
			"doctype": "RetailEdge Branch Profile",
			"profile_name": profile_name,
			"enabled": 1,
			"company": COMPANY,
			"branch": branch_name,
			"is_default_for_company": 1 if is_default else 0,
			"default_warehouse": default_warehouse or None,
			"notes": "Deterministic RC3 browser/persona fixture.",
		}
	).insert(ignore_permissions=True)


def _ensure_assignment(
	email: str,
	branch_name: str,
	branch_role: str,
	*,
	is_primary: bool,
	active: bool,
) -> None:
	effective_from = "2026-01-01"
	filters = {
		"user": email,
		"company": COMPANY,
		"branch": branch_name,
		"effective_from": effective_from,
	}
	if frappe.db.exists("RetailEdge Branch Assignment", filters):
		return
	frappe.get_doc(
		{
			"doctype": "RetailEdge Branch Assignment",
			"user": email,
			"company": COMPANY,
			"branch": branch_name,
			"branch_role": branch_role,
			"is_primary": 1 if is_primary else 0,
			"effective_from": effective_from,
			"effective_to": None if active else "2026-01-31",
			"transfer_reason": "RC3 deterministic access fixture",
		}
	).insert(ignore_permissions=True)


def _ensure_branch_quotation(branch_name: str) -> str:
	filters = {
		"company": COMPANY,
		"party_name": CUSTOMER,
		"retailedge_branch": branch_name,
	}
	existing = frappe.db.get_value("Quotation", filters, "name", order_by="creation asc")
	if existing:
		return str(existing)
	# Let the existing merchant policy resolve its permitted default Price List.
	# This fixture exercises branch visibility, not a pricing-policy override.
	result = create_professional_quotation_draft(
		{
			"company": COMPANY,
			"branch": branch_name,
			"customer": CUSTOMER,
			"price_list": PRICE_LIST,
			"items": [{"item_code": ITEM, "qty": 1, "rate": 1000}],
		}
	)
	return str(result["name"])


def _ensure_branch_sales_invoice(branch_name: str) -> str:
	"""Seed a deterministic ERPNext draft for list/read-scope acceptance only."""
	marker = f"RetailEdge browser Working Branch fixture: {branch_name}"
	existing = frappe.db.get_value(
		"Sales Invoice",
		{
			"company": COMPANY,
			"retailedge_branch": branch_name,
			"remarks": marker,
		},
		"name",
		order_by="creation asc",
	)
	if existing:
		return str(existing)

	company = frappe.get_doc("Company", COMPANY)
	currency = str(company.default_currency or "NGN")
	receivable = _first_leaf_account(COMPANY, root_type="Asset", account_type="Receivable")
	income = _first_leaf_account(COMPANY, root_type="Income")
	cost_center = _first_cost_center(COMPANY)
	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": COMPANY,
			"customer": CUSTOMER,
			"posting_date": nowdate(),
			"due_date": add_days(nowdate(), 30),
			"currency": currency,
			"conversion_rate": 1,
			"selling_price_list": PRICE_LIST,
			"price_list_currency": currency,
			"plc_conversion_rate": 1,
			"debit_to": receivable,
			"remarks": marker,
			"retailedge_branch": branch_name,
			"items": [
				{
					"item_code": ITEM,
					"qty": 1,
					"rate": 1000,
					"income_account": income,
					"cost_center": cost_center,
				}
			],
		}
	)
	if invoice.meta.has_field("branch"):
		invoice.branch = branch_name
	invoice.insert(ignore_permissions=True)
	return str(invoice.name)


def _ensure_expense_category() -> str:
	if frappe.db.exists("RetailEdge Expense Category", EXPENSE_CATEGORY):
		return EXPENSE_CATEGORY
	frappe.get_doc(
		{
			"doctype": "RetailEdge Expense Category",
			"category_name": EXPENSE_CATEGORY,
			"category_code": "BROWSER-WORKING-BRANCH",
			"company": COMPANY,
			"is_active": 1,
			"description": "Deterministic browser read-scope fixture.",
		}
	).insert(ignore_permissions=True)
	return EXPENSE_CATEGORY


def _ensure_branch_cashier_expense(branch_name: str) -> str:
	"""Seed a read/list-only draft without depending on POS shift creation."""
	category = _ensure_expense_category()
	name = f"RE-CE-BROWSER-{branch_name.replace(' ', '-').upper()}"
	if frappe.db.exists("RetailEdge Cashier Expense", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "RetailEdge Cashier Expense",
			"name": name,
			"naming_series": "RE-CE-.YYYY.-.####",
			"expense_category": category,
			"amount": 1000,
			"description": f"RetailEdge browser Working Branch expense fixture: {branch_name}",
			"company": COMPANY,
			"cashier": "browser-multi-branch@example.com",
			"expense_date": nowdate(),
			"branch": branch_name,
			"expense_status": "Draft",
			"ledger_status": "Not Applicable",
			"entry_source": "API",
			"cash_source": "Other",
			"cash_movement_status": "Not Disbursed",
			"posting_ready": 0,
		}
	)
	# This fixture exercises read visibility only. db_insert deliberately avoids
	# creating a synthetic POS shift or invoking posting/readiness workflows.
	doc.db_insert()
	return str(doc.name)


def seed_rc3_personas() -> dict:
	"""Extend the base browser smoke fixture with the full RC3 persona matrix."""
	base = seed_browser_personas()

	for email, (first_name, roles) in EXTRA_PERSONAS.items():
		_ensure_user(email, first_name, roles)

	warehouses = {}
	for index, branch_name in enumerate(BRANCHES):
		_ensure_branch(branch_name)
		warehouses[branch_name] = _ensure_warehouse(branch_name)
		if branch_name == BRANCH_WITHOUT_DEFAULTS:
			# Branch Setup remains the Company→Branch authority while its optional
			# operational defaults stay empty for this acceptance case.
			_ensure_branch_profile(branch_name, default_warehouse="")
			continue
		_ensure_branch_profile(
			branch_name,
			default_warehouse=warehouses[branch_name],
			is_default=index == 0,
		)

	# Printing acceptance uses Administrator so seed the same deterministic
	# operating Company/Branch contract as the product personas. This stays in
	# the browser fixture only; production operating-context resolution remains
	# permission- and assignment-aware.
	frappe.defaults.set_user_default("Company", COMPANY, user="Administrator")

	for email, assignments in ACTIVE_ASSIGNMENTS.items():
		for branch_name, branch_role, is_primary in assignments:
			_ensure_assignment(
				email,
				branch_name,
				branch_role,
				is_primary=bool(is_primary),
				active=True,
			)

	for email, assignments in ENDED_ASSIGNMENTS.items():
		for branch_name, branch_role in assignments:
			_ensure_assignment(
				email,
				branch_name,
				branch_role,
				is_primary=True,
				active=False,
			)

	# Seed real ERPNext drafts with explicit Company/Branch/accounting truth so
	# browser acceptance isolates read/list governance rather than creation UX.
	_ensure_customer()
	_ensure_item()
	branch_quotations = {
		branch_name: _ensure_branch_quotation(branch_name)
		for branch_name in (BRANCHES[0], BRANCHES[1])
	}
	branch_sales_invoices = {
		branch_name: _ensure_branch_sales_invoice(branch_name)
		for branch_name in (BRANCHES[0], BRANCHES[1])
	}
	branch_cashier_expenses = {
		branch_name: _ensure_branch_cashier_expense(branch_name)
		for branch_name in (BRANCHES[0], BRANCHES[1])
	}

	frappe.db.commit()
	return {
		**base,
		"branches": list(BRANCHES),
		"warehouses": warehouses,
		"branch_without_defaults": BRANCH_WITHOUT_DEFAULTS,
		"branch_quotations": branch_quotations,
		"branch_sales_invoices": branch_sales_invoices,
		"branch_cashier_expenses": branch_cashier_expenses,
		"extra_users": {email: list(roles) for email, (_name, roles) in EXTRA_PERSONAS.items()},
		"active_assignments": {
			email: [branch for branch, _role, _primary in assignments]
			for email, assignments in ACTIVE_ASSIGNMENTS.items()
		},
		"ended_assignment_users": sorted(ENDED_ASSIGNMENTS),
	}
