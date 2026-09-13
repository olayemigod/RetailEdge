from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import coexistence, transaction_branch_attribution

APP_ROOT = Path(__file__).resolve().parents[1]


class TestMultiAppCoexistence(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_hooks_do_not_take_over_frappe_or_erpnext_entrypoints(self):
		hooks = self.read("hooks.py")
		self.assertNotIn('\nhome_page = ', hooks)
		self.assertNotIn('\nauth_hooks = [', hooks)
		self.assertNotIn('"frappe.', hooks.split("override_whitelisted_methods = {", 1)[1])
		self.assertNotIn('"erpnext.', hooks.split("override_whitelisted_methods = {", 1)[1])

	def test_optional_coreedge_integration_remains_optional(self):
		hooks = self.read("hooks.py")
		self.assertIn('required_apps = ["edgesuite_ui"]', hooks)
		self.assertNotIn('required_apps = ["coreedge"]', hooks.lower())
		self.assertNotIn("from coreedge", hooks.lower())
		self.assertNotIn("import coreedge", hooks.lower())

	def test_shared_frontend_runtime_is_edgesuiteui_only(self):
		for relative in (
			"public/js/retailedge_business_hub.bundle.js",
			"public/js/retailedge_business_hub_page.js",
			"public/js/retailedge_product_menu.bundle.js",
		):
			with self.subTest(relative=relative):
				source = self.read(relative)
				self.assertIn("EdgeSuiteUI", source)
				self.assertNotIn("window.EdgeUI", source)
				self.assertNotIn("global.EdgeUI", source)

	def test_branch_fieldnames_remain_namespaced_but_visible_labels_are_neutral(self):
		self.assertIn("retailedge_branch", coexistence.VISIBLE_BRANCH_FIELD_METADATA)
		self.assertEqual(
			coexistence.VISIBLE_BRANCH_FIELD_METADATA["retailedge_branch"]["label"],
			"Operating Branch",
		)
		self.assertNotIn(
			"RetailEdge",
			coexistence.VISIBLE_BRANCH_FIELD_METADATA["retailedge_branch"]["description"],
		)
		source = self.read("transaction_branch_attribution.py")
		self.assertIn('"fieldname": "retailedge_branch"', source)
		self.assertIn('"label": "Operating Branch"', source)
		self.assertIn('"description": "Branch attributed for operating context, filtering and reporting."', source)
		self.assertNotIn('"label": "RetailEdge Branch"', source)
		self.assertNotIn("RetailEdge branch attribution already exists", source)
		hooks = self.read("hooks.py")
		installer = hooks.index("retailedge.transaction_branch_attribution.ensure_transaction_branch_custom_fields")
		neutralizer = hooks.index("retailedge.coexistence.ensure_neutral_branch_field_labels")
		self.assertLess(installer, neutralizer)

	def test_guided_create_generic_selectors_are_modal_scoped(self):
		css = self.read("public/css/retailedge_guided_create_menu.css")
		for selector in (
			".create-picker-list {",
			".guided-create-search {",
			".guided-create-search-input {",
			".create-picker-item {",
			".create-picker-icon {",
			".create-picker-copy {",
			".create-picker-mode {",
		):
			self.assertNotIn(f"\n{selector}", css)
		self.assertIn(".edge-modal:has(.create-picker-list) .create-picker-item {", css)
		self.assertIn(".edge-modal:has(.create-picker-list) .guided-create-search {", css)

	def test_global_desk_styles_do_not_take_over_html_or_body(self):
		for relative in (
			"public/css/retailedge_cards.css",
			"public/css/retailedge_workspace_home.css",
			"public/css/retailedge_guided_create_menu.css",
		):
			with self.subTest(relative=relative):
				css = self.read(relative)
				self.assertNotIn("\nbody {", css)
				self.assertNotIn("\nhtml {", css)
				self.assertNotIn("\n* {", css)

	def test_backfill_is_dry_run_first_and_not_a_whitelisted_runtime_api(self):
		signature = inspect.signature(transaction_branch_attribution.run_transaction_branch_backfill)
		self.assertTrue(signature.parameters["dry_run"].default)
		source = self.read("transaction_branch_attribution.py")
		function_pos = source.index("def run_transaction_branch_backfill(")
		preceding = source[max(0, function_pos - 120):function_pos]
		self.assertNotIn("@frappe.whitelist", preceding)
		self.assertIn("if not dry_run and would_update:", source)
		self.assertIn("update_modified=False", source)

	@patch("retailedge.coexistence.frappe.only_for")
	@patch("retailedge.transaction_branch_attribution.run_transaction_branch_backfill")
	def test_backfill_write_wrapper_requires_system_manager_and_exact_confirmation(self, mock_backfill, mock_only_for):
		with self.assertRaises(frappe.ValidationError):
			coexistence.apply_branch_attribution_backfill(confirmation="yes")
		mock_only_for.assert_called_once_with("System Manager")
		mock_backfill.assert_not_called()

		mock_only_for.reset_mock()
		coexistence.apply_branch_attribution_backfill(
			doctype="Sales Invoice",
			confirmation=coexistence.BACKFILL_CONFIRMATION,
		)
		mock_only_for.assert_called_once_with("System Manager")
		mock_backfill.assert_called_once()
		self.assertFalse(mock_backfill.call_args.kwargs["dry_run"])

	def test_shared_erpnext_form_scripts_are_additive(self):
		hooks = self.read("hooks.py")
		self.assertIn('"Sales Invoice": "public/js/sales_documents.js"', hooks)
		sales_js = self.read("public/js/sales_documents.js")
		self.assertNotIn("clear_custom_buttons", sales_js)
		self.assertNotIn("set_df_property(\"status\", \"hidden\"", sales_js)
		self.assertNotIn("frappe.ui.form.off", sales_js)


if __name__ == "__main__":
	unittest.main()
