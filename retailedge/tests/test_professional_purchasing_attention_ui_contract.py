from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalPurchasingAttentionUIContract(TestCase):
	def test_attention_stays_inside_governed_edgesuite_purchasing_page(self):
		component = (APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text()

		self.assertIn("window.EdgeSuiteUI", component)
		self.assertIn("EdgeAppShell", component)
		self.assertIn("Purchase Orders & Attention", component)
		self.assertIn("attentionFilter", component)
		self.assertIn("visibleRows", component)
		self.assertIn("attention_flags", component)
		self.assertIn("Attention", component)
		self.assertIn("sortBy('per_received')", component)
		self.assertIn("sortBy('per_billed')", component)
		self.assertIn('frappe.set_route("query-report", "Purchase Order Analysis")', component)
		self.assertNotIn("window.EdgeUI", component)
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("frappe.msgprint", component)
		self.assertNotIn("frappe.show_alert", component)

	def test_attention_backend_is_read_only_and_server_date_driven(self):
		source = (APP_ROOT / "professional_purchasing.py").read_text()

		self.assertIn("def _classify_purchase_order_attention", source)
		self.assertIn("today_date = getdate(today or nowdate())", source)
		self.assertIn('"attention_source_of_truth"', source)
		self.assertIn('"can_open_purchase_order_analysis"', source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)


if __name__ == "__main__":
	import unittest

	unittest.main()
