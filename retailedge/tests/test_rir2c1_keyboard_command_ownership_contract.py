from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
HOOKS = APP_ROOT / "hooks.py"
PRODUCT_MENU = APP_ROOT / "public" / "js" / "retailedge_product_menu.bundle.js"
HISTORICAL_ASSET = APP_ROOT / "public" / "js" / "edgesuite_keyboard_shortcuts.js"
CANDIDATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "edgesuite-ui-candidate-compat.yml"
DECISION_DOC = REPO_ROOT / "docs" / "rir2c1_keyboard_command_ownership.md"


class TestRIR2C1KeyboardCommandOwnershipContract(unittest.TestCase):
	def test_retailedge_depends_on_shared_edgesuite_runtime_without_duplicate_keyboard_asset(self):
		hooks = HOOKS.read_text()
		self.assertIn('required_apps = ["edgesuite_ui"]', hooks)
		self.assertNotIn("edgesuite_keyboard_shortcuts.js", hooks)
		self.assertFalse(HISTORICAL_ASSET.exists())

	def test_current_product_menu_keeps_permission_aware_guided_create_searchable_from_shared_menu(self):
		source = PRODUCT_MENU.read_text()
		self.assertIn('const GUIDED_CREATE_ACTION = "guided-create"', source)
		self.assertIn("link_to: GUIDED_CREATE_ACTION", source)
		self.assertIn("edgeUI.registerProductMenu(config)", source)
		self.assertIn("requestGuidedCreate()", source)
		self.assertIn('new CustomEvent("retailedge-open-guided-create")', source)

	def test_candidate_compatibility_freezes_shared_keyboard_guard_contract(self):
		workflow = CANDIDATE_WORKFLOW.read_text()
		self.assertIn("e40ea4d7dc000d17443a0571c1e246b61bfd3e1d", workflow)
		for required in (
			"edgeui_ctrl_k_guard.js",
			"edgeui_ctrl_s_guard.js",
			"openProductMenu",
			".edge-product-menu__search",
			"form.doc.docstatus",
			"await form.save()",
			"saveCurrentContext",
			"registerSaveHandler",
			"edgesuite:save-request",
		):
			with self.subTest(required=required):
				self.assertIn(required, workflow)
		self.assertIn("ignore_permissions|frappe\\.db\\.set_value|frappe\\.client\\.save", workflow)

	def test_decision_document_records_shared_ownership_and_historical_supersession(self):
		doc = DECISION_DOC.read_text()
		self.assertIn("RIR2C1", doc)
		self.assertIn("bdeacaaa88899946d313e488592ca3ff98dff887", doc)
		self.assertIn("65d1844328fe5563c662aa229bb22bb92b11442b", doc)
		self.assertIn("981a6e4803373ca00df2376309c15af6ffac3a40", doc)
		self.assertIn("SUPERSEDED_SHARED_RUNTIME", doc)
		self.assertIn("do not cherry-pick", doc.lower())


if __name__ == "__main__":
	unittest.main()
