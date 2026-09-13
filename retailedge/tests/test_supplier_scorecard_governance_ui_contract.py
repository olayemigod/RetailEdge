from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]
HOST = APP_ROOT / "public" / "js" / "professional_purchasing" / "IncomingQualityInspection.vue"
COMPONENT = APP_ROOT / "public" / "js" / "professional_purchasing" / "SupplierScorecardGovernance.vue"
BACKEND = APP_ROOT / "supplier_scorecard_governance.py"


class TestSupplierScorecardGovernanceUIContract(TestCase):
	def test_professional_purchasing_extension_hosts_scorecard_without_removing_quality(self):
		host = HOST.read_text()

		self.assertIn('import SupplierScorecardGovernance from "./SupplierScorecardGovernance.vue"', host)
		self.assertIn("<SupplierScorecardGovernance", host)
		self.assertIn(':company="company"', host)
		self.assertIn(':branch="branch"', host)
		self.assertIn(':supplier="supplier"', host)
		self.assertIn("Incoming Quality Inspection", host)
		self.assertIn("create_incoming_quality_inspections", host)

	def test_edgesuite_surface_is_read_only_and_routes_privileged_setup_to_native_erpnext(self):
		component = COMPONENT.read_text()

		self.assertIn("Supplier Scorecard &amp; Governance", component)
		self.assertIn("retailedge.supplier_scorecard_governance.get_supplier_scorecard_capability", component)
		self.assertIn("retailedge.supplier_scorecard_governance.get_supplier_scorecard_summary", component)
		self.assertIn('frappe.set_route("Form", "Supplier Scorecard", this.summary.scorecard.name)', component)
		self.assertIn('frappe.set_route("List", "Supplier Scorecard")', component)
		self.assertIn('frappe.new_doc("Supplier Scorecard", { supplier: this.supplier })', component)
		self.assertIn("Native ERPNext permission required.", component)
		self.assertIn("ERPNext standings remain authoritative", component)
		self.assertNotIn("v-model", component)
		self.assertNotIn('type="checkbox"', component)
		self.assertNotIn('type="number"', component)
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("frappe.msgprint", component)
		self.assertNotIn("frappe.show_alert", component)
		self.assertNotIn("window.EdgeUI", component)

	def test_backend_is_permission_scoped_bounded_and_passive(self):
		source = BACKEND.read_text()

		self.assertIn('_permission(SUPPLIER_SCORECARD_DOCTYPE, "read"', source)
		self.assertIn('_permission(SUPPLIER_SCORECARD_DOCTYPE, "create")', source)
		self.assertIn('_permission(SUPPLIER_SCORECARD_PERIOD_DOCTYPE, "read")', source)
		self.assertIn("_resolve_scope(", source)
		self.assertIn("_assert_read(SUPPLIER_DOCTYPE, supplier)", source)
		self.assertIn('filters={"scorecard": scorecard, "docstatus": 1}', source)
		self.assertIn("limit_page_length=MAX_SCORECARD_PERIODS", source)
		self.assertIn('"warn_rfqs"', source)
		self.assertIn('"warn_pos"', source)
		self.assertIn('"prevent_rfqs"', source)
		self.assertIn('"prevent_pos"', source)
		self.assertNotIn("make_all_scorecards", source)
		self.assertNotIn(".save(", source)
		self.assertNotIn(".submit(", source)
		self.assertNotIn("frappe.db.set_value", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)


if __name__ == "__main__":
	import unittest

	unittest.main()
