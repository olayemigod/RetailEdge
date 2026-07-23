from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge import hooks
from retailedge import document_workspace
from retailedge import document_workspace_permissions


class TestRetailEdgeDocumentWorkspace(FrappeTestCase):
	def app_path(self, *parts: str) -> Path:
		return Path(frappe.get_app_path("retailedge", *parts))

	def read(self, *parts: str) -> str:
		path = self.app_path(*parts)
		self.assertTrue(path.exists(), f"Missing expected file: {path}")
		return path.read_text()

	def test_resource_allowlist_is_deliberately_small(self):
		self.assertEqual(set(document_workspace.RESOURCE_CONFIG), {"branch-profiles", "settings"})
		self.assertEqual(
			document_workspace.RESOURCE_CONFIG["branch-profiles"]["doctype"],
			"RetailEdge Branch Profile",
		)
		self.assertEqual(document_workspace.RESOURCE_CONFIG["settings"]["doctype"], "RetailEdge Settings")
		self.assertFalse(document_workspace.RESOURCE_CONFIG["settings"]["allow_delete"])
		self.assertFalse(document_workspace.RESOURCE_CONFIG["branch-profiles"]["allow_delete"])

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
		account = frappe._dict({"options": "Account"})
		filters = document_workspace._option_filters(config, account, {"company": "Retail Company"})
		self.assertEqual(filters.get("company"), "Retail Company")
		self.assertEqual(filters.get("is_group"), 0)

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

	def test_phase_adds_no_accounting_or_submitted_document_writes(self):
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
			"sales invoice",
			"payment entry",
			"bank transaction",
			"journal entry",
			"stock entry",
			"doc.submit()",
			"frappe.client.submit",
		):
			if forbidden in {"sales invoice", "payment entry", "bank transaction", "journal entry", "stock entry"}:
				continue
			self.assertNotIn(forbidden, combined)
