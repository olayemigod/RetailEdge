from __future__ import annotations

import frappe
from frappe.utils.password import update_password

from retailedge.setup_roles import ensure_retailedge_roles
from retailedge.tests.upgrade_validation_fixture import (
	COMPANY,
	_ensure_company,
	_ensure_fiscal_year,
	_ensure_transaction_masters,
)

PASSWORD = "RetailEdgeBrowser1!"

PERSONAS = {
	"browser-manager@example.com": ("Browser Manager", ("RetailEdgeManager",)),
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


def seed_browser_personas() -> dict:
	"""Seed deterministic users for the release browser smoke gate."""
	ensure_retailedge_roles(migrate_alias_assignments=True)
	_ensure_company()
	_ensure_fiscal_year(COMPANY)
	_ensure_transaction_masters()

	for email, (first_name, roles) in PERSONAS.items():
		_ensure_user(email, first_name, roles)

	frappe.db.commit()
	return {
		"company": COMPANY,
		"password": PASSWORD,
		"users": {email: list(roles) for email, (_name, roles) in PERSONAS.items()},
	}
