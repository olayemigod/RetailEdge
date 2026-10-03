from __future__ import annotations

import frappe


PRODUCT_DESCRIPTOR = {
	"key": "retailedge",
	"product_key": "retailedge",
	"label": "PEdge Retail",
	"product": "PEdge Retail",
	"icon": "shopping-cart",
	"home_route": "/app/retailedge-business-hub",
	"route_patterns": [
		"/app/retailedge*",
		"/app/make-sale*",
		"/app/professional-selling*",
		"/app/document-output-sharing*",
		"/app/transaction-workspace*",
		"/app/query-report/RetailEdge*",
	],
	"order": 20,
}


def get_product_availability() -> dict | None:
	"""Expose RetailEdge only when the current Desk user may open the product home page."""

	user = frappe.session.user
	if not user or user == "Guest":
		return None
	if user != "Administrator" and frappe.db.get_value("User", user, "user_type") != "System User":
		return None
	if not frappe.db.exists("Page", "retailedge-business-hub"):
		return None
	try:
		if not frappe.get_doc("Page", "retailedge-business-hub").is_permitted():
			return None
	except Exception:
		return None
	return dict(PRODUCT_DESCRIPTOR)



def validate_print_context(
	product_key=None,
	company=None,
	branch=None,
	purpose="Receipt",
	user=None,
) -> dict:
	"""Validate RetailEdge Company/Branch context before EdgeSuite resolves a scoped profile."""

	key = str(product_key or "").strip().lower()
	if key != "retailedge":
		return {"handled": False}

	user = user or frappe.session.user
	company = str(company or "").strip()
	branch = str(branch or "").strip()

	if purpose != "Receipt":
		return {
			"handled": True,
			"allowed": False,
			"reason": "RetailEdge shared printing currently supports Receipt profiles only.",
		}

	if company:
		if not frappe.db.exists("Company", company):
			return {
				"handled": True,
				"allowed": False,
				"reason": f"Company {company} does not exist.",
			}
		if user != "Administrator":
			company_doc = frappe.get_doc("Company", company)
			if not company_doc.has_permission("read", user=user):
				return {
					"handled": True,
					"allowed": False,
					"reason": f"You do not have access to Company {company}.",
				}

	if branch:
		if frappe.db.exists("DocType", "Branch") and not frappe.db.exists("Branch", branch):
			return {
				"handled": True,
				"allowed": False,
				"reason": f"Branch {branch} does not exist.",
			}

		if company:
			from retailedge.branch_profile import (
				get_exact_branch_profile,
				has_enabled_branch_profiles,
			)

			if has_enabled_branch_profiles(company=company) and not get_exact_branch_profile(
				company=company,
				branch=branch,
				active_only=True,
			):
				return {
					"handled": True,
					"allowed": False,
					"reason": (
						f"Branch {branch} is not configured as an enabled RetailEdge Branch "
						f"for Company {company}."
					),
				}

		from retailedge.branch_context import validate_user_branch_access

		access = validate_user_branch_access(
			branch,
			user=user,
			company=company or None,
			throw=False,
		)
		if not access.get("allowed"):
			return {
				"handled": True,
				"allowed": False,
				"reason": f"You do not have access to Branch {branch}.",
			}

	return {
		"handled": True,
		"allowed": True,
		"company": company,
		"branch": branch,
	}
