from __future__ import annotations

import json
from pathlib import Path

import frappe
from frappe.utils import add_days, flt, nowdate

COMPANY = "RetailEdge Upgrade CI"
ABBR = "REU"
CUSTOMER = "RetailEdge Upgrade Customer"
ITEM = "RE-UPGRADE-SERVICE"
SNAPSHOT_PATH = Path("/tmp/retailedge-upgrade-before.json")


def _first_leaf_account(company: str, *, root_type: str, account_type: str = "") -> str:
	filters = {"company": company, "root_type": root_type, "is_group": 0, "disabled": 0}
	if account_type:
		filters["account_type"] = account_type
	name = frappe.db.get_value("Account", filters, "name")
	if not name and account_type:
		filters.pop("account_type", None)
		name = frappe.db.get_value("Account", filters, "name")
	if not name:
		frappe.throw(f"No usable {root_type} account exists for {company}.")
	return str(name)


def _first_cost_center(company: str) -> str:
	name = frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 0, "disabled": 0},
		"name",
	)
	if not name:
		frappe.throw(f"No usable Cost Center exists for {company}.")
	return str(name)


def _ensure_company():
	if frappe.db.exists("Company", COMPANY):
		return frappe.get_doc("Company", COMPANY)
	return frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": COMPANY,
			"abbr": ABBR,
			"default_currency": "NGN",
			"country": "Nigeria",
		}
	).insert()


def _ensure_customer() -> None:
	if frappe.db.exists("Customer", CUSTOMER):
		return
	frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": CUSTOMER,
			"customer_type": "Company",
			"customer_group": "All Customer Groups",
			"territory": "All Territories",
		}
	).insert()


def _ensure_item() -> None:
	if frappe.db.exists("Item", ITEM):
		return
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": ITEM,
			"item_name": "RetailEdge Upgrade Service",
			"item_group": "All Item Groups",
			"stock_uom": "Nos",
			"is_stock_item": 0,
		}
	).insert()


def _ledger_snapshot(invoice: str) -> dict:
	rows = frappe.get_all(
		"GL Entry",
		filters={
			"voucher_type": "Sales Invoice",
			"voucher_no": invoice,
			"is_cancelled": 0,
		},
		fields=["debit", "credit"],
	)
	return {
		"count": len(rows),
		"debit": flt(sum(flt(row.get("debit")) for row in rows), 2),
		"credit": flt(sum(flt(row.get("credit")) for row in rows), 2),
	}


def seed_upgrade_fixture() -> dict:
	"""Create representative setup + submitted accounting truth on the frozen pre-MVP baseline."""
	company = _ensure_company()
	_ensure_customer()
	_ensure_item()

	existing = frappe.get_all(
		"Sales Invoice",
		filters={"company": COMPANY, "customer": CUSTOMER, "docstatus": 1},
		fields=["name"],
		order_by="creation asc",
		limit=1,
	)
	if existing:
		invoice = frappe.get_doc("Sales Invoice", existing[0]["name"])
	else:
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
				"currency": company.default_currency or "NGN",
				"debit_to": receivable,
				"remarks": "RetailEdge upgrade validation invariant",
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": 1250,
						"income_account": income,
						"cost_center": cost_center,
					}
				],
			}
		)
		invoice.insert()
		invoice.submit()

	ledger = _ledger_snapshot(invoice.name)
	if not ledger["count"]:
		frappe.throw("Upgrade fixture Sales Invoice did not create GL truth.")

	snapshot = {
		"company": COMPANY,
		"customer": CUSTOMER,
		"item": ITEM,
		"invoice": invoice.name,
		"docstatus": int(invoice.docstatus),
		"grand_total": flt(invoice.grand_total, 2),
		"outstanding_amount": flt(invoice.outstanding_amount, 2),
		"ledger": ledger,
	}
	SNAPSHOT_PATH.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
	# This is isolated CI fixture setup, not RetailEdge runtime transaction logic.
	frappe.db.commit()
	return snapshot


def verify_upgrade_fixture() -> dict:
	"""Assert that migration preserved setup, submitted document and ERPNext ledger truth."""
	if not SNAPSHOT_PATH.exists():
		frappe.throw("Upgrade validation snapshot is missing.")
	before = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

	for doctype, name in (
		("Company", before["company"]),
		("Customer", before["customer"]),
		("Item", before["item"]),
		("Sales Invoice", before["invoice"]),
	):
		if not frappe.db.exists(doctype, name):
			frappe.throw(f"{doctype} {name} was lost during upgrade.")

	invoice = frappe.get_doc("Sales Invoice", before["invoice"])
	after_ledger = _ledger_snapshot(invoice.name)
	assert int(invoice.docstatus) == before["docstatus"] == 1
	assert flt(invoice.grand_total, 2) == flt(before["grand_total"], 2)
	assert flt(invoice.outstanding_amount, 2) == flt(before["outstanding_amount"], 2)
	assert after_ledger == before["ledger"]
	assert frappe.db.exists("DocType", "RetailEdge Settings")
	assert frappe.db.exists("Role", "RetailEdge Manager")

	return {
		"invoice": invoice.name,
		"grand_total": flt(invoice.grand_total, 2),
		"outstanding_amount": flt(invoice.outstanding_amount, 2),
		"ledger": after_ledger,
		"retailedge_manager_role": True,
	}
