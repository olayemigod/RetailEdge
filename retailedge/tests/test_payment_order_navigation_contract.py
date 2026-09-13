from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPaymentOrderNavigationContract(TestCase):
	def test_payment_orders_are_native_permission_aware_navigation(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		group_start = source.index('"key": "suppliers-payables"')
		group_end = source.index('"key": "insights"', group_start)
		group = source[group_start:group_end]

		supplier_payables = group.index('"label": "Supplier Payables"')
		payment_orders = group.index('"label": "Payment Orders"')
		accounts_payable = group.index('"label": "Accounts Payable (Detailed)"')

		self.assertLess(supplier_payables, payment_orders)
		self.assertLess(payment_orders, accounts_payable)
		self.assertEqual(group.count('"label": "Payment Orders"'), 1)
		self.assertIn('"target_type": "DocType", "target": "Payment Order"', group)

		self.assertIn('if target_type == "DocType":', source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', source)

	def test_retailedge_does_not_wrap_native_payment_order_posting(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()

		self.assertNotIn("prepare_payment_order", source)
		self.assertNotIn("create_payment_order", source)
		self.assertNotIn("submit_payment_order", source)
		self.assertNotIn('frappe.get_doc("Payment Order"', source)
		self.assertNotIn('"doctype": "Payment Order"', source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)


if __name__ == "__main__":
	import unittest

	unittest.main()
