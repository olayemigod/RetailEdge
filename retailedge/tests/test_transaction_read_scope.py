from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import retailedge.transaction_read_scope as scope


APP_ROOT = Path(__file__).resolve().parents[1]


def _escape(value):
	return f"'{value}'"


def _doc(*, company: str, branch: str):
	return SimpleNamespace(
		doctype="Sales Invoice",
		company=company,
		retailedge_branch=branch,
		is_new=lambda: False,
	)


def test_explicit_working_branch_is_a_server_query_scope():
	with (
		patch.object(
			scope,
			"_explicit_working_scope",
			return_value={"company": "RetailEdge Consulting", "branch": "Ketu", "company_wide": False},
		),
		patch.object(scope, "_meta_has_field", return_value=True),
		patch.object(scope.frappe.db, "escape", side_effect=_escape),
	):
		condition = scope.get_sales_invoice_permission_query_conditions(
			"manager@example.com", doctype="Sales Invoice"
		)
	assert "`tabSales Invoice`.`company` = 'RetailEdge Consulting'" in condition
	assert "`tabSales Invoice`.`retailedge_branch` in ('Ketu')" in condition


def test_all_branches_keeps_company_as_hard_boundary():
	with (
		patch.object(
			scope,
			"_explicit_working_scope",
			return_value={"company": "RetailEdge Consulting", "branch": "", "company_wide": True},
		),
		patch.object(scope, "_meta_has_field", return_value=True),
		patch.object(scope.frappe.db, "escape", side_effect=_escape),
	):
		condition = scope.get_sales_invoice_permission_query_conditions(
			"manager@example.com", doctype="Sales Invoice"
		)
	assert condition == "`tabSales Invoice`.`company` = 'RetailEdge Consulting'"
	assert "retailedge_branch" not in condition


def test_assignment_history_limits_native_lists_when_no_explicit_switch_exists():
	with (
		patch.object(scope, "_explicit_working_scope", return_value={}),
		patch.object(scope, "user_has_global_branch_access", return_value=False),
		patch.object(scope, "has_branch_assignments", return_value=True),
		patch.object(
			scope,
			"_active_assignment_pairs",
			return_value=[
				("RetailEdge Consulting", "Ketu"),
				("RetailEdge Consulting", "Lagos Island"),
			],
		),
		patch.object(scope, "_meta_has_field", return_value=True),
		patch.object(scope.frappe.db, "escape", side_effect=_escape),
	):
		condition = scope.get_sales_invoice_permission_query_conditions(
			"branch-user@example.com", doctype="Sales Invoice"
		)
	assert "'Ketu'" in condition
	assert "'Lagos Island'" in condition
	assert "RetailEdge Consulting" in condition


def test_users_without_branch_assignment_history_keep_native_erp_permissions():
	with (
		patch.object(scope, "_explicit_working_scope", return_value={}),
		patch.object(scope, "user_has_global_branch_access", return_value=False),
		patch.object(scope, "has_branch_assignments", return_value=False),
	):
		assert scope.get_sales_invoice_permission_query_conditions(
			"native-user@example.com", doctype="Sales Invoice"
		) == ""


def test_direct_document_access_denies_other_branch_but_allows_native_checks_to_continue():
	with patch.object(
		scope,
		"_explicit_working_scope",
		return_value={"company": "RetailEdge Consulting", "branch": "Ketu", "company_wide": False},
	):
		assert scope.has_permission(
			_doc(company="RetailEdge Consulting", branch="Ketu"),
			user="manager@example.com",
			ptype="read",
		) is True
		assert scope.has_permission(
			_doc(company="RetailEdge Consulting", branch="Lagos Island"),
			user="manager@example.com",
			ptype="read",
		) is False


def test_direct_company_wide_scope_rejects_another_company():
	with patch.object(
		scope,
		"_explicit_working_scope",
		return_value={"company": "RetailEdge Consulting", "branch": "", "company_wide": True},
	):
		assert scope.has_permission(
			_doc(company="RetailEdge Consulting", branch="Lagos Island"),
			user="manager@example.com",
			ptype="read",
		) is True
		assert scope.has_permission(
			_doc(company="Other Company", branch="Lagos Island"),
			user="manager@example.com",
			ptype="read",
		) is False


def test_query_hooks_have_v16_compatible_doctype_wrappers():
	hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
	source = (APP_ROOT / "transaction_read_scope.py").read_text(encoding="utf-8")
	contracts = {
		"Sales Invoice": "get_sales_invoice_permission_query_conditions",
		"Purchase Invoice": "get_purchase_invoice_permission_query_conditions",
		"Stock Entry": "get_stock_entry_permission_query_conditions",
		"Payment Entry": "get_payment_entry_permission_query_conditions",
	}
	for doctype, function in contracts.items():
		assert f'"{doctype}": "retailedge.transaction_read_scope.{function}"' in hooks
		assert f"def {function}(user: str | None = None, doctype: str | None = None)" in source
	assert "def has_permission(doc, ptype: str | None = None, user: str | None = None, debug: bool = False)" in source
	assert "retailedge.transaction_read_scope.has_permission" in hooks


def test_professional_selling_keeps_native_if_owner_and_user_permissions_in_path():
	source = (APP_ROOT / "professional_selling.py").read_text(encoding="utf-8")
	start = source.index("def get_professional_selling_list(")
	end = source.index("\n\n@frappe.whitelist()\ndef _delivery_has_direct_sales_order_billing", start)
	list_source = source[start:end]
	assert "frappe.get_list(" in list_source
	assert "frappe.get_all(" not in list_source
	linked_start = source.index("def _readable_linked_documents(")
	linked_end = source.index("\n\ndef _readable_parent_linked_documents", linked_start)
	linked_source = source[linked_start:linked_end]
	assert 'frappe.has_permission(parent_doctype, "read", doc=doc)' in linked_source


def test_professional_selling_prefers_stored_retailedge_branch_attribution():
	source = (APP_ROOT / "professional_selling.py").read_text(encoding="utf-8")
	assert "def _transaction_branch_field(doctype: str)" in source
	assert 'if has_field(doctype, "retailedge_branch")' in source
	assert 'return "retailedge_branch"' in source
	assert "branch_field = _transaction_branch_field(doctype)" in source


def test_retailedge_roles_receive_only_minimum_branch_master_visibility():
	roles = (APP_ROOT / "setup_roles.py").read_text(encoding="utf-8")
	assert "def _ensure_operational_branch_read()" in roles
	assert 'add_permission("Branch", role_name, 0)' in roles
	assert 'update_permission_property("Branch", role_name, 0, "read", 1)' in roles
	assert 'update_permission_property("Branch", role_name, 0, "select", 1)' in roles
	branch_scope = roles[roles.index("def _ensure_operational_branch_read()") : roles.index("def _add_canonical_roles_for_alias_assignments")]
	for denied in ('"write", 1', '"create", 1', '"delete", 1', '"import", 1'):
		assert denied not in branch_scope
