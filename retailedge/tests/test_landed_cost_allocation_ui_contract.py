from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestLandedCostAllocationUIContract(TestCase):
	def test_professional_purchasing_exposes_landed_cost_inside_edgesuite(self):
		component = (APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text()

		self.assertIn("Allocate Landed Cost", component)
		self.assertIn("Prepare Landed Cost Draft", component)
		self.assertIn("retailedge.landed_cost_allocation.get_landed_cost_capability", component)
		self.assertIn("retailedge.landed_cost_allocation.search_landed_cost_sources", component)
		self.assertIn("retailedge.landed_cost_allocation.prepare_landed_cost_voucher_draft", component)
		self.assertIn("EdgeLinkField", component)
		self.assertIn("Purchase Receipt", component)
		self.assertIn("Stock-updating Purchase Invoice", component)
		self.assertIn("frappe.model.sync(result.document || {})", component)
		self.assertIn('frappe.set_route("Form", "Landed Cost Voucher", document.name)', component)
		self.assertIn("clearLandedCostSource", component)
		self.assertIn("Returns & Supplier Credits", component)
		self.assertIn("Purchase Material Requests", component)
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("frappe.msgprint", component)
		self.assertNotIn("window.EdgeUI", component)

	def test_guided_handoff_does_not_collect_accounting_charge_rows(self):
		component = (APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text()

		self.assertNotIn('v-model="landedCost.freightAmount"', component)
		self.assertNotIn('v-model="landedCost.expenseAccount"', component)
		self.assertNotIn('v-model="landedCost.taxes"', component)
		self.assertNotIn('v-model="landedCost.vendorInvoices"', component)
		self.assertIn("Distribution basis", component)
		self.assertIn('value="Amount"', component)
		self.assertIn('value="Qty"', component)
		self.assertIn('value="Distribute Manually"', component)

	def test_backend_uses_native_unsaved_lcv_without_posting_or_permission_bypass(self):
		source = (APP_ROOT / "landed_cost_allocation.py").read_text()

		self.assertIn("make_lcv(doctype, source.name)", source)
		self.assertIn('"persisted": False', source)
		self.assertIn('"posting_status": "Unsaved Draft"', source)
		self.assertIn('filters.update({"docstatus": 1, "is_return": 0})', source)
		self.assertIn('filters["update_stock"] = 1', source)
		self.assertIn("MAX_LINK_RESULTS", source)
		self.assertNotIn(".insert(", source)
		self.assertNotIn(".save(", source)
		self.assertNotIn(".submit(", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("update_landed_cost(", source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)


if __name__ == "__main__":
	import unittest

	unittest.main()
