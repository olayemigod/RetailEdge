from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = APP_ROOT / "public" / "js" / "retailedge_business_hub.bundle.js"
HELPER = APP_ROOT / "public" / "js" / "retailedge_business_hub" / "guided_create_search.js"
BUSINESS_HUB = APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
GUIDED_CREATE_CSS = APP_ROOT / "public" / "css" / "retailedge_guided_create_menu.css"
REPO_ROOT = APP_ROOT.parent
DECISION_DOC = REPO_ROOT / "docs" / "rir2d1_searchable_create_picker.md"


class TestRIR2D1SearchableCreatePickerContract(unittest.TestCase):
	def test_business_hub_remains_the_permission_source_for_create_actions(self):
		source = BUSINESS_HUB.read_text()
		self.assertIn("this.quickActions = data.quick_actions || []", source)
		self.assertIn('v-for="action in quickActions"', source)
		self.assertIn("runQuickAction(action)", source)

	def test_search_helper_filters_rendered_permitted_actions_only(self):
		source = HELPER.read_text()
		self.assertIn('const LIST_SELECTOR = ".create-picker-list"', source)
		self.assertIn('const ITEM_SELECTOR = ".create-picker-item"', source)
		self.assertIn('type="search"', source)
		self.assertIn('aria-label="Search permitted Create entries"', source)
		self.assertIn("actionMatches(button, query)", source)
		self.assertIn("button.hidden = !visible", source)
		self.assertIn("No permitted Create entry matches your search.", source)
		self.assertNotIn("frappe.call", source)
		self.assertNotIn("frappe.new_doc", source)
		self.assertNotIn("ignore_permissions", source)

	def test_search_is_lifecycle_owned_by_business_hub_bundle(self):
		source = BUNDLE.read_text()
		self.assertIn('import { installGuidedCreateSearch } from "./retailedge_business_hub/guided_create_search"', source)
		self.assertIn("const destroyGuidedCreateSearch = installGuidedCreateSearch(window)", source)
		self.assertIn("destroyGuidedCreateSearch()", source)
		self.assertIn("originalUnmount()", source)

	def test_existing_guided_create_css_contains_search_and_empty_state_contract(self):
		css = GUIDED_CREATE_CSS.read_text()
		for class_name in (
			".guided-create-search",
			".guided-create-search-input",
			".guided-create-search-count",
			".guided-create-search-empty",
		):
			with self.subTest(class_name=class_name):
				self.assertIn(class_name, css)

	def test_decision_document_keeps_scope_bounded(self):
		doc = DECISION_DOC.read_text()
		self.assertIn("RIR2D1", doc)
		self.assertIn("permission-approved `quick_actions`", doc)
		self.assertIn("does not change creation permissions", doc)
		self.assertIn("manual browser/persona QA remains required", doc.lower())


if __name__ == "__main__":
	unittest.main()
