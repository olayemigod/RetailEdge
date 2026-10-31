from __future__ import annotations

import frappe
from frappe.utils.password import update_password

from retailedge.setup_roles import ensure_retailedge_roles
from retailedge.tests.upgrade_validation_fixture import (
	COMPANY,
	ITEM_GROUP,
	_ensure_company,
	_ensure_fiscal_year,
	_ensure_transaction_masters,
)

PASSWORD = "RetailEdgeBrowser1!"
SECOND_ITEM = "RE-UPGRADE-SERVICE-SECOND"

PERSONAS = {
	# The RC3 owner/manager persona represents a broad permitted Company context,
	# not a RetailEdge-only role with deliberately unavailable ERPNext data sources.
	# Keep native authorities explicit so browser acceptance exercises real report
	# permission checks instead of bypassing them.
	"browser-manager@example.com": (
		"Browser Manager",
		("RetailEdgeManager", "Sales User", "Stock User", "Accounts User", "Purchase User"),
	),
	"browser-cashier@example.com": ("Browser Cashier", ("RetailEdgeCashier",)),
	"browser-accounts@example.com": ("Browser Accounts", ("Accounts User",)),
	"browser-stock@example.com": ("Browser Stock", ("Stock User",)),
}


def _ensure_user(email: str, first_name: str, roles: tuple[str, ...]) -> None:
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"enabled": 1,
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)

	existing_roles = {row.role for row in (user.roles or [])}
	for role in roles:
		if role not in existing_roles:
			user.append("roles", {"role": role})
	user.enabled = 1
	user.user_type = "System User"
	user.save(ignore_permissions=True)
	update_password(email, PASSWORD, logout_all_sessions=True)
	frappe.defaults.set_user_default("Company", COMPANY, user=email)


def _ensure_secondary_item() -> None:
	"""Keep multi-row browser acceptance valid under ERPNext's duplicate-item guard."""
	if frappe.db.exists("Item", SECOND_ITEM):
		return
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": SECOND_ITEM,
			"item_name": "RetailEdge Upgrade Service Second",
			"item_group": ITEM_GROUP,
			"stock_uom": "Nos",
			"is_stock_item": 0,
		}
	).insert(ignore_permissions=True)


def seed_browser_personas() -> dict:
	"""Seed deterministic users for the release browser smoke gate."""
	ensure_retailedge_roles(migrate_alias_assignments=True)
	_ensure_company()
	_ensure_fiscal_year(COMPANY)
	_ensure_transaction_masters()
	_ensure_secondary_item()

	for email, (first_name, roles) in PERSONAS.items():
		_ensure_user(email, first_name, roles)

	frappe.db.commit()
	return {
		"company": COMPANY,
		"password": PASSWORD,
		"second_item": SECOND_ITEM,
		"users": {email: list(roles) for email, (_name, roles) in PERSONAS.items()},
	}
