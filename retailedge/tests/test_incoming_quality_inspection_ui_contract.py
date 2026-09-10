from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]
PARENT = APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue"
COMPONENT = APP_ROOT / "public" / "js" / "professional_purchasing" / "IncomingQualityInspection.vue"
BACKEND = APP_ROOT / "incoming_quality_inspection.py"


class TestIncomingQualityInspectionUIContract(TestCase):
	def test_professional_purchasing_hosts_incoming_quality_component(self):
		parent = PARENT.read_text()

		self.assertIn('import IncomingQualityInspection from "./IncomingQualityInspection.vue"', parent)
		self.assertIn("<IncomingQualityInspection", parent)
		self.assertIn(':company="filters.company"', parent)
		self.assertIn(':branch="filters.branch"', parent)
		self.assertIn(':supplier="filters.supplier"', parent)
		self.assertIn("Returns & Supplier Credits", parent)
		self.assertIn("Allocate Landed Cost", parent)
		self.assertIn("Purchase Material Requests", parent)
		self.assertIn("Purchase Orders & Attention", parent)

	def test_edgesuite_component_uses_backend_filtered_draft_receipts_and_owned_review_submit(self):
		component = COMPONENT.read_text()

		self.assertIn("Incoming Quality Inspection", component)
		self.assertIn("Draft Purchase Receipt", component)
		self.assertIn("retailedge.incoming_quality_inspection.search_incoming_quality_receipts", component)
		self.assertIn("retailedge.incoming_quality_inspection.get_incoming_quality_receipt_context", component)
		self.assertIn("retailedge.incoming_quality_inspection.get_incoming_quality_inspection_review", component)
		self.assertIn("retailedge.incoming_quality_inspection.submit_incoming_quality_inspection_review", component)
		self.assertIn("retailedge.incoming_quality_inspection.create_incoming_quality_inspections", component)
		self.assertIn("company: this.company || null", component)
		self.assertIn("branch: this.branch || null", component)
		self.assertIn("supplier: this.supplier || null", component)
		self.assertIn("child_row_reference: row.child_row_reference", component)
		self.assertIn("Review Quality Inspections", component)
		self.assertIn("Submit Quality Inspections", component)
		self.assertIn("Advanced: Prepare in ERPNext", component)

	def test_scope_changes_reset_quality_source_inside_child_component(self):
		component = COMPONENT.read_text()

		self.assertIn("company() { this.resetForScopeChange(); }", component)
		self.assertIn("branch() { this.resetForScopeChange(); }", component)
		self.assertIn("supplier() { this.resetForScopeChange(); }", component)
		self.assertIn("if (this.source || this.context.purchase_receipt) this.clearReceipt();", component)

	def test_component_stays_edgesuite_and_native_routes_are_capability_gated(self):
		component = COMPONENT.read_text()

		self.assertIn("window.EdgeSuiteUI?.components", component)
		self.assertIn("EdgeLinkField", component)
		self.assertIn("EdgeEmptyState", component)
		self.assertIn('frappe.boot?.edgesuite_ui_access?.mode !== "edgesuite_only"', component)
		self.assertIn("if (!this.nativeFallbackEnabled", component)
		self.assertIn('frappe.set_route("Form", "Quality Inspection", name)', component)
		self.assertIn('frappe.set_route("Form", "Purchase Receipt", name)', component)
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("frappe.msgprint", component)
		self.assertNotIn("window.EdgeUI", component)

	def test_backend_delegates_to_erpnext_quality_lifecycle_without_posting_bypass(self):
		source = BACKEND.read_text()

		self.assertIn("check_item_quality_inspection(", source)
		self.assertIn("make_quality_inspections(", source)
		self.assertIn('filters.update({"docstatus": 0, "is_return": 0})', source)
		self.assertIn('inspection_type="Incoming"', source)
		self.assertIn("_ALLOWED_SELECTION_KEYS", source)
		self.assertIn("def get_incoming_quality_inspection_review(", source)
		self.assertIn("def submit_incoming_quality_inspection_review(", source)
		self.assertIn("quality_inspection.insert()", source)
		self.assertIn("quality_inspection.submit()", source)
		self.assertIn('"persistence": "none"', source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)
		self.assertNotIn('frappe.new_doc("Quality Inspection")', source)


if __name__ == "__main__":
	import unittest

	unittest.main()
