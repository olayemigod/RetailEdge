from __future__ import annotations

from pathlib import Path
from unittest import TestCase

APP_ROOT = Path(__file__).resolve().parents[1]
COMPONENT = APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue"
HANDOFF = APP_ROOT / "procurement_tracker_handoff.py"


class TestProcurementTrackerHandoffUIContract(TestCase):
	def test_existing_edgesuite_purchasing_page_owns_the_handoff(self):
		component = COMPONENT.read_text()

		self.assertIn("window.EdgeSuiteUI?.components", component)
		self.assertIn(
			"retailedge.procurement_tracker_handoff.get_procurement_tracker_handoff",
			component,
		)
		self.assertIn('v-if="procurementTracker.available"', component)
		self.assertIn('@click="openProcurementTracker"', component)
		self.assertIn(">Procurement Tracker</button>", component)
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("window.EdgeUI", component)

	def test_native_tracker_route_carries_company_but_not_branch(self):
		component = COMPONENT.read_text()
		method_start = component.index("openProcurementTracker()")
		method_end = component.index("openPurchaseOrder(name)", method_start)
		method = component[method_start:method_end]

		self.assertIn("this.procurementTracker?.available", method)
		self.assertIn("frappe.route_options = { company:", method)
		self.assertIn('frappe.set_route("query-report"', method)
		self.assertIn('"Procurement Tracker"', method)
		self.assertNotIn("branch", method.lower())

	def test_backend_is_capability_only_and_does_not_clone_native_tracker(self):
		source = HANDOFF.read_text()

		self.assertIn('PROCUREMENT_TRACKER_REPORT = "Procurement Tracker"', source)
		self.assertIn("has_unrestricted_report_scope", source)
		self.assertIn("validate_report_scope", source)
		self.assertIn("company_wide_view = not resolved_branch", source)
		self.assertIn('"company_wide_only": True', source)
		self.assertNotIn("erpnext.buying.report.procurement_tracker", source)
		self.assertNotIn("frappe.qb", source)
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn(".insert(", source)
		self.assertNotIn(".save(", source)
		self.assertNotIn(".submit(", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_existing_purchasing_draft_first_flows_remain_present(self):
		component = COMPONENT.read_text()

		self.assertIn("prepare_request_for_quotation_draft", component)
		self.assertIn("prepare_purchase_receipt_draft", component)
		self.assertIn("Prepare Draft RFQ", component)
		self.assertIn("Prepare Receipt", component)
		self.assertIn('frappe.set_route("query-report", "Supplier Quotation Comparison")', component)
		self.assertIn('frappe.set_route("query-report", "Purchase Order Analysis")', component)


if __name__ == "__main__":
	import unittest

	unittest.main()
