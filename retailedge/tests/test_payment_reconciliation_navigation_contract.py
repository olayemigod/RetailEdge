from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPaymentReconciliationNavigationContract(TestCase):
	def test_payment_reconciliation_is_native_permission_aware_navigation(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		group_start = source.index('"key": "money"')
		group_end = source.index('"key": "expenses"', group_start)
		group = source[group_start:group_end]

		payments = group.index('"label": "Payments"')
		payment_reconciliation = group.index('"label": "Payment Reconciliation"')
		bank_transactions = group.index('"label": "Bank Transactions"')

		self.assertLess(payments, payment_reconciliation)
		self.assertLess(payment_reconciliation, bank_transactions)
		self.assertEqual(group.count('"label": "Payment Reconciliation"'), 1)
		self.assertIn(
			'"target_type": "DocType", "target": "Payment Reconciliation"',
			group,
		)

		self.assertIn('if target_type == "DocType":', source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', source)

	def test_retailedge_does_not_wrap_native_reconciliation_or_refund_posting(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()

		self.assertNotIn("create_payment_reconciliation", source)
		self.assertNotIn("submit_payment_reconciliation", source)
		self.assertNotIn("reconcile_customer_credit", source)
		self.assertNotIn("refund_credit_note", source)
		self.assertNotIn('frappe.get_doc("Payment Reconciliation"', source)
		self.assertNotIn('"doctype": "Payment Reconciliation"', source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)


if __name__ == "__main__":
	import unittest

	unittest.main()
