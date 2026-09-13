from __future__ import annotations

import frappe

from retailedge.tests.browser_persona_fixture import _ensure_user, seed_browser_personas
from retailedge.tests.upgrade_validation_fixture import COMPANY

BRANCHES = (
	"RetailEdge RC3 Lagos",
	"RetailEdge RC3 Ikeja",
	"RetailEdge RC3 Abuja",
)

EXTRA_PERSONAS = {
	"browser-branch-manager@example.com": ("Browser Branch Manager", ("RetailEdgeBranchManager",)),
	"browser-purchasing@example.com": ("Browser Purchasing", ("Purchase User",)),
	"browser-sales@example.com": ("Browser Sales", ("Sales User",)),
	"browser-one-branch@example.com": ("Browser One Branch", ("Stock User",)),
	"browser-multi-branch@example.com": ("Browser Multi Branch", ("Stock User",)),
	"browser-zero-branch@example.com": ("Browser Zero Branch", ("Stock User",)),
	"browser-native@example.com": ("Browser Native Advanced", ("System Manager",)),
}

ACTIVE_ASSIGNMENTS = {
	"browser-branch-manager@example.com": (("RetailEdge RC3 Lagos", "Manager", 1),),
	"browser-cashier@example.com": (("RetailEdge RC3 Lagos", "Cashier", 1),),
	"browser-accounts@example.com": (("RetailEdge RC3 Lagos", "Accounts", 1),),
	"browser-stock@example.com": (("RetailEdge RC3 Lagos", "Stock", 1),),
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


def _ensure_branch_profile(branch_name: str, *, is_default: bool = False) -> None:
	profile_name = f"RC3 {branch_name}"
	if frappe.db.exists("RetailEdge Branch Profile", profile_name):
		return
	frappe.get_doc(
		{
			"doctype": "RetailEdge Branch Profile",
			"profile_name": profile_name,
			"enabled": 1,
			"company": COMPANY,
			"branch": branch_name,
			"is_default_for_company": 1 if is_default else 0,
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


def seed_rc3_personas() -> dict:
	"""Extend the base browser smoke fixture with the full RC3 persona matrix."""
	base = seed_browser_personas()

	for email, (first_name, roles) in EXTRA_PERSONAS.items():
		_ensure_user(email, first_name, roles)

	for index, branch_name in enumerate(BRANCHES):
		_ensure_branch(branch_name)
		_ensure_branch_profile(branch_name, is_default=index == 0)

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

	frappe.db.commit()
	return {
		**base,
		"branches": list(BRANCHES),
		"extra_users": {email: list(roles) for email, (_name, roles) in EXTRA_PERSONAS.items()},
		"active_assignments": {
			email: [branch for branch, _role, _primary in assignments]
			for email, assignments in ACTIVE_ASSIGNMENTS.items()
		},
		"ended_assignment_users": sorted(ENDED_ASSIGNMENTS),
	}
