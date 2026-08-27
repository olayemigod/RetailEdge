from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.bank_account_policy import (
	resolve_retailedge_bank_account,
	search_retailedge_bank_accounts,
)


@frappe.whitelist()
def search_bank_matching_bank_accounts(
	company: str,
	branch: str = "",
	txt: str = "",
	limit: int = 20,
) -> list[dict[str, Any]]:
	"""Bank Matching selector with strict Company -> Branch -> Bank Account scope.

	With no Branch selected, only company-wide Bank Accounts are returned. Once a
	Branch is selected, only Bank Accounts explicitly scoped to that Branch are
	returned; company-wide accounts are intentionally excluded from this selector.
	"""
	return search_retailedge_bank_accounts(
		company=company,
		branch=branch,
		txt=txt,
		limit=limit,
		strict_branch_scope=1,
	)


@frappe.whitelist(methods=["POST"])
def validate_bank_matching_bank_account_filter(
	company: str,
	branch: str = "",
	bank_account: str = "",
) -> dict[str, Any]:
	"""Validate an explicit Bank Matching Bank Account filter server-side."""
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	bank_account = str(bank_account or "").strip()
	if not bank_account:
		return {"valid": True, "bank_account": "", "branch": branch}
	if not company:
		frappe.throw(_("Select a Company before filtering Bank Matching by Bank Account."))

	resolved = resolve_retailedge_bank_account(
		company=company,
		branch=branch,
		bank_account=bank_account,
		strict_branch_scope=True,
	)
	return {
		"valid": True,
		"bank_account": resolved.get("bank_account"),
		"branch": resolved.get("branch"),
		"scope": resolved.get("scope"),
	}
