from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "incoming_quality_inspection.py"
COMPONENT = APP_ROOT / "public" / "js" / "professional_purchasing" / "IncomingQualityInspection.vue"


class TestRIR2F3F18IncomingQualityInspectionOwnershipContract(TestCase):
	def test_backend_exposes_persistence_free_review_and_locked_standard_submit(self):
		source = BACKEND.read_text()

		self.assertIn("def get_incoming_quality_inspection_review(", source)
		self.assertIn("def submit_incoming_quality_inspection_review(", source)
		self.assertIn('"persistence": "none"', source)
		self.assertIn("FOR UPDATE", source)
		self.assertIn("expected_source_modified", source)
		self.assertIn("quality_inspection.insert()", source)
		self.assertIn("quality_inspection.submit()", source)
		self.assertIn('"source_of_truth": "ERPNext Quality Inspection validate and submit"', source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_backend_rebuilds_template_and_accepts_reading_values_only(self):
		source = BACKEND.read_text()

		self.assertIn("_ALLOWED_REVIEW_SELECTION_KEYS", source)
		self.assertIn("_ALLOWED_READING_KEYS", source)
		self.assertIn("get_item_specification_details()", source)
		self.assertIn("manual_inspection", source)
		self.assertIn("Advanced ERPNext", source)
		self.assertIn("reading_value", source)
		for index in range(1, 11):
			self.assertIn(f'"reading_{index}"', source)
		self.assertNotIn('value.get("status")', source)
		self.assertNotIn('value.get("min_value")', source)
		self.assertNotIn('value.get("max_value")', source)
		self.assertNotIn('value.get("acceptance_formula")', source)

	def test_edgesuite_component_owns_review_and_submit_before_native_fallback(self):
		component = COMPONENT.read_text()

		self.assertIn("retailedge.incoming_quality_inspection.get_incoming_quality_inspection_review", component)
		self.assertIn("retailedge.incoming_quality_inspection.submit_incoming_quality_inspection_review", component)
		self.assertIn("Review Quality Inspections", component)
		self.assertIn("Submit Quality Inspections", component)
		self.assertIn("nativeFallbackEnabled", component)
		self.assertIn("Advanced: Prepare in ERPNext", component)
		self.assertIn("expected_source_modified", component)
		self.assertIn("reading_value", component)
		self.assertIn("reading_1", component)
		self.assertNotIn("Create Draft Quality Inspections", component)
		self.assertNotIn("then continue readings and submission on the native Quality Inspection forms", component)

	def test_native_routes_are_explicitly_capability_gated(self):
		component = COMPONENT.read_text()

		self.assertIn("if (!this.nativeFallbackEnabled", component)
		self.assertIn('frappe.set_route("Form", "Quality Inspection"', component)
		self.assertIn('frappe.set_route("Form", "Purchase Receipt"', component)
		self.assertIn('frappe.boot?.edgesuite_ui_access?.mode !== "edgesuite_only"', component)


if __name__ == "__main__":
	import unittest

	unittest.main()
