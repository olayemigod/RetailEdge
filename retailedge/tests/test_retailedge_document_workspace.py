from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge import document_workspace
from retailedge import document_workspace_permissions
from retailedge import hooks


class TestRetailEdgeDocumentWorkspace(FrappeTestCase):
	def app_path(self, *parts: str) -> Path:
		return Path(frappe.get_app_path("retailedge", *parts))

	def read(self, *parts: str) -> str:
		path = self.app_path(*parts)
		self.assertTrue(path.exists(), f"Missing expected file: {path}")
		return path.read_text()

	def test_resource_allowlist_contains_only_safe_setup_resources(self):
		self.assertEqual(
			set(document_workspace.RESOURCE_CONFIG),
			{
				"branch-profiles",
				"expense-categories",
				"statement-mapping-templates",
				"settings",
			},
		)
		self.assertEqual(
			document_workspace.RESOURCE_CONFIG["branch-profiles"]["doctype"],
			"RetailEdge Branch Profile",
		)
		self.assertEqual(
			document_workspace.RESOURCE_CONFIG["expense-categories"]["doctype"],
			"RetailEdge Expense Category",
		)
		self.assertEqual(
			document_workspace.RESOURCE_CONFIG["statement-mapping-templates"]["doctype"],
			"RetailEdge Statement Mapping Template",
		)
		self.assertEqual(document_workspace.RESOURCE_CONFIG["settings"]["doctype"], "RetailEdge Settings")
		for config in document_workspace.RESOURCE_CONFIG.values():
			self.assertFalse(config["allow_delete"])

	def test_page_bundle_and_vue_are_source_controlled(self):
		page_path = self.app_path(
			"retailedge",
			"page",
			"retailedge_document_workspace",
			"retailedge_document_workspace.json",
		)
		page = json.loads(page_path.read_text())
		self.assertEqual(page["name"], "retailedge-document-workspace")
		self.assertEqual(page["module"], "RetailEdge")
		self.assertTrue(page["roles"])
		self.assertTrue(self.app_path("public", "js", "retailedge_document_workspace.bundle.js").exists())
		self.assertTrue(
			self.app_path(
				"public",
				"js",
				"retailedge_document_workspace",
				"RetailEdgeDocumentWorkspace.vue",
			).exists()
		)

	def test_loader_requires_shared_runtime_before_product_bundle(self):
		content = self.read(
			"retailedge",
			"page",
			"retailedge_document_workspace",
			"retailedge_document_workspace.js",
		)
		edgeui_index = content.find('requireAsync("edgeui.bundle.js")')
		product_index = content.find('requireAsync("retailedge_document_workspace.bundle.js")')
		self.assertGreaterEqual(edgeui_index, 0)
		self.assertGreaterEqual(product_index, 0)
		self.assertLess(edgeui_index, product_index)
		self.assertIn("failed to load", content)
		self.assertIn("on_page_hide", content)
		self.assertIn("unmount", content)

	def test_bundle_uses_shared_app_factory_and_runtime_guards(self):
		bundle = self.read("public", "js", "retailedge_document_workspace.bundle.js")
		self.assertIn("createRetailEdgeApp", bundle)
		self.assertIn("installRetailEdgeWorkspaceRuntime", bundle)
		self.assertNotIn("window.EdgeUI =", bundle)
		self.assertNotIn("coreedge/public", bundle.lower())
		self.assertNotIn("../../../../../coreedge", bundle.lower())

	def test_vue_uses_shared_document_components(self):
		content = self.read(
			"public",
			"js",
			"retailedge_document_workspace",
			"RetailEdgeDocumentWorkspace.vue",
		)
		for component in (
			"EdgeAppShell",
			"EdgePageLayout",
			"EdgePageHeader",
			"EdgeFilterBar",
			"EdgeDataTable",
			"EdgeDocumentForm",
			"EdgeWorkflowBar",
			"EdgeSettingsLayout",
			"EdgeLinkField",
		):
			self.assertIn(component, content)
		self.assertIn("Open native Frappe view", content)
		self.assertIn("site-wide controls", content)
		self.assertNotIn("delete_document", content)
		self.assertNotIn("apply_workflow", content)

	def test_shared_runtime_contract_includes_document_components(self):
		factory = self.read("public", "js", "retailedge_ui", "app_factory.js")
		for component in (
			"EdgeDataTable",
			"EdgeDocumentForm",
			"EdgeWorkflowBar",
			"EdgeSettingsLayout",
		):
			self.assertIn(f'"{component}"', factory)

	def test_runtime_exposes_safe_master_resources(self):
		runtime = self.read(
			"public",
			"js",
			"retailedge_document_workspace",
			"workspace_runtime.js",
		)
		self.assertIn('"expense-categories"', runtime)
		self.assertIn('"statement-mapping-templates"', runtime)
		self.assertIn("mergeResourceOptions", runtime)
		self.assertNotIn('"cashier-expenses"', runtime)
		self.assertNotIn('"sales-invoices"', runtime)

	def test_branch_profile_schema_clears_company_and_branch_dependents(self):
		config = {"key": "branch-profiles", **document_workspace.RESOURCE_CONFIG["branch-profiles"]}
		schema = document_workspace._build_form_schema(config, frappe.get_meta("RetailEdge Branch Profile"))
		fields = {
			field["fieldname"]: field
			for tab in schema["tabs"]
			for section in tab["sections"]
			for field in section["fields"]
		}
		self.assertIn("branch", fields["company"]["clear_fields"])
		self.assertIn("default_cash_account", fields["company"]["clear_fields"])
		self.assertIn("default_pos_profile", fields["branch"]["clear_fields"])
		self.assertIn("default_warehouse", fields["branch"]["clear_fields"])

	def test_master_schemas_clear_company_dependent_accounting_links(self):
		cases = (
			("expense-categories", "RetailEdge Expense Category", {"expense_account", "default_cost_center"}),
			("statement-mapping-templates", "RetailEdge Statement Mapping Template", {"default_account"}),
		)
		for resource, doctype, expected in cases:
			config = {"key": resource, **document_workspace.RESOURCE_CONFIG[resource]}
			schema = document_workspace._build_form_schema(config, frappe.get_meta(doctype))
			fields = {
				field["fieldname"]: field
				for tab in schema["tabs"]
				for section in tab["sections"]
				for field in section["fields"]
			}
			self.assertTrue(expected.issubset(set(fields["company"]["clear_fields"])))

	def test_settings_schema_retains_tabs_and_dependencies(self):
		config = {"key": "settings", **document_workspace.RESOURCE_CONFIG["settings"]}
		schema = document_workspace._build_form_schema(config, frappe.get_meta("RetailEdge Settings"))
		self.assertGreaterEqual(len(schema["tabs"]), 5)
		fields = {
			field["fieldname"]: field
			for tab in schema["tabs"]
			for section in tab["sections"]
			for field in section["fields"]
		}
		self.assertEqual(
			fields["allow_pos_posting_date_override"]["depends_on"],
			"eval:doc.enable_posting_date_control",
		)
		self.assertEqual(
			fields["auto_prepare_exact_bank_matches"]["depends_on"],
			"eval:doc.enable_bank_auto_match",
		)

	def test_company_scoped_link_filters_are_context_aware(self):
		config = {"key": "branch-profiles", **document_workspace.RESOURCE_CONFIG["branch-profiles"]}
		account = frappe._dict({"fieldname": "default_cash_account", "options": "Account"})
		filters = document_workspace._option_filters(config, account, {"company": "Retail Company"})
		self.assertEqual(filters.get("company"), "Retail Company")
		self.assertEqual(filters.get("is_group"), 0)

	def test_expense_account_filter_requires_company_and_expense_root(self):
		config = {
			"key": "expense-categories",
			**document_workspace.RESOURCE_CONFIG["expense-categories"],
		}
		account = frappe._dict({"fieldname": "expense_account", "options": "Account"})
		with patch.object(document_workspace, "has_field", return_value=True):
			empty = document_workspace._option_filters(config, account, {})
			scoped = document_workspace._option_filters(config, account, {"company": "Retail Company"})
		self.assertEqual(empty, {"name": ["in", []]})
		self.assertEqual(scoped["company"], "Retail Company")
		self.assertEqual(scoped["is_group"], 0)
		self.assertEqual(scoped["root_type"], "Expense")

	def test_only_branch_profiles_receive_branch_list_filters(self):
		with patch.object(
			document_workspace,
			"_allowed_branch_filters",
			return_value={"branch": ["in", ["Branch A"]]},
		):
			branch_config = {
				"key": "branch-profiles",
				**document_workspace.RESOURCE_CONFIG["branch-profiles"],
			}
			expense_config = {
				"key": "expense-categories",
				**document_workspace.RESOURCE_CONFIG["expense-categories"],
			}
			self.assertEqual(
				document_workspace._resource_list_filters(branch_config, {"company": "Retail Company"}),
				{"branch": ["in", ["Branch A"]]},
			)
			self.assertEqual(document_workspace._resource_list_filters(expense_config, {}), {})

	def test_named_document_branch_scope_is_resource_specific(self):
		content = self.read("document_workspace.py")
		self.assertIn('if config["key"] == "branch-profiles":', content)
		self.assertIn("_assert_branch_profile_scope(doc)", content)
		self.assertNotIn("query_filters = _allowed_branch_filters(requested.get", content)

	def test_child_role_rows_are_normalized_by_parent_table(self):
		content = self.read("document_workspace.py")
		self.assertIn('"default_cashiers": "Cashier"', content)
		self.assertIn('"default_managers": "Manager"', content)
		self.assertIn('"default_auditors": "Auditor"', content)
		self.assertIn('payload["role_type"] = CHILD_ROLE_BY_FIELD[fieldname]', content)

	def test_branch_profile_query_condition_is_registered(self):
		self.assertEqual(
			hooks.permission_query_conditions["RetailEdge Branch Profile"],
			"retailedge.document_workspace_permissions.get_branch_profile_query",
		)
		with (
			patch.object(document_workspace_permissions, "user_has_global_branch_access", return_value=False),
			patch.object(
				document_workspace_permissions,
				"get_user_allowed_branches",
				return_value={"branches": ["Branch A", "Branch B"]},
			),
		):
			condition = document_workspace_permissions.get_branch_profile_query("restricted@example.com")
		self.assertIn("RetailEdge Branch Profile", condition)
		self.assertIn("Branch A", condition)
		self.assertIn("Branch B", condition)

	def test_global_branch_roles_receive_no_extra_query_condition(self):
		with patch.object(document_workspace_permissions, "user_has_global_branch_access", return_value=True):
			self.assertEqual(document_workspace_permissions.get_branch_profile_query("manager@example.com"), "")

	def test_provider_uses_normal_frappe_save_and_optimistic_locking(self):
		content = self.read("document_workspace.py")
		self.assertIn("frappe.TimestampMismatchError", content)
		self.assertIn("doc.insert()", content)
		self.assertIn("doc.save()", content)
		self.assertNotIn("doc.submit()", content)
		self.assertNotIn("frappe.delete_doc", content)
		self.assertNotIn("apply_workflow", content)

	def test_master_validation_rejects_unsafe_account_links(self):
		content = self.read("document_workspace.py")
		self.assertIn('required_root_type="Expense"', content)
		self.assertIn("require_non_group=True", content)
		self.assertIn("_validate_expense_category_links", content)
		self.assertIn("_validate_statement_mapping_links", content)

	def test_all_provider_endpoints_are_whitelisted(self):
		for method in (
			document_workspace.get_resource_definition,
			document_workspace.get_document_list,
			document_workspace.get_document,
			document_workspace.save_document,
			document_workspace.get_link_options,
		):
			is_whitelisted = getattr(method, "_is_whitelisted", False)
			if not is_whitelisted and hasattr(frappe, "whitelisted"):
				is_whitelisted = method in frappe.whitelisted
			self.assertTrue(is_whitelisted)

	def test_product_menu_exposes_setup_workspace_without_replacing_native_links(self):
		content = self.read("public", "js", "retailedge_product_menu.js")
		self.assertIn("RetailEdge Setup Workspace", content)
		self.assertIn("retailedge-document-workspace", content)
		self.assertIn('Settings: "Configure RetailEdge behaviour and controls."', content)
		self.assertIn('"Branch Profile": "Manage branch-specific defaults', content)
		self.assertIn('"Expense Category": "Maintain approved expense classifications', content)
		self.assertIn('"Statement Mapping Template": "Define reusable statement column mappings', content)

	def test_phase_adds_no_submitted_or_accounting_document_writes(self):
		paths = [
			self.app_path("document_workspace.py"),
			self.app_path("public", "js", "retailedge_document_workspace.bundle.js"),
			self.app_path(
				"public",
				"js",
				"retailedge_document_workspace",
				"RetailEdgeDocumentWorkspace.vue",
			),
		]
		combined = "\n".join(path.read_text().lower() for path in paths)
		for forbidden in (
			"doc.submit()",
			"doc.cancel()",
			"frappe.delete_doc",
			"frappe.client.submit",
			"make_gl_entries",
			"journal_entry.insert",
			"payment_entry.insert",
		):
			self.assertNotIn(forbidden, combined)
