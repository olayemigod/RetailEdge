from __future__ import annotations

import inspect
import unittest
from pathlib import Path

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
		source = self.read("coreedge_adapter.py")
		self.assertIn("get_installed_apps", source)
		self.assertIn('"coreedge"', source.lower())
		self.assertNotIn("required_apps = [\"coreedge\"]", self.read("hooks.py"))

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

	def test_backfill_is_dry_run_first_and_not_a_whitelisted_runtime_api(self):
		signature = inspect.signature(transaction_branch_attribution.run_transaction_branch_backfill)
		self.assertTrue(signature.parameters["dry_run"].default)
		source = self.read("transaction_branch_attribution.py")
		function_pos = source.index("def run_transaction_branch_backfill(")
		preceding = source[max(0, function_pos - 120):function_pos]
		self.assertNotIn("@frappe.whitelist", preceding)
		self.assertIn("if not dry_run and would_update:", source)
		self.assertIn("update_modified=False", source)

	def test_shared_erpnext_form_scripts_are_additive(self):
		hooks = self.read("hooks.py")
		self.assertIn('"Sales Invoice": "public/js/sales_documents.js"', hooks)
		sales_js = self.read("public/js/sales_documents.js")
		self.assertNotIn("clear_custom_buttons", sales_js)
		self.assertNotIn("set_df_property(\"status\", \"hidden\"", sales_js)
		self.assertNotIn("frappe.ui.form.off", sales_js)


if __name__ == "__main__":
	unittest.main()
