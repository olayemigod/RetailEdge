from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestRecurringBillingNavigationContract(TestCase):
	def test_recurring_billing_uses_native_permission_aware_navigation(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		group_start = source.index('"key": "money"')
		group_end = source.index('"key": "expenses"', group_start)
		group = source[group_start:group_end]

		payment_reconciliation = group.index('"label": "Payment Reconciliation"')
		subscriptions = group.index('"label": "Subscriptions"')
		subscription_plans = group.index('"label": "Subscription Plans"')
		bank_transactions = group.index('"label": "Bank Transactions"')

		self.assertLess(payment_reconciliation, subscriptions)
		self.assertLess(subscriptions, subscription_plans)
		self.assertLess(subscription_plans, bank_transactions)
		self.assertEqual(group.count('"label": "Subscriptions"'), 1)
		self.assertEqual(group.count('"label": "Subscription Plans"'), 1)
		self.assertIn('"target_type": "DocType", "target": "Subscription"', group)
		self.assertIn('"target_type": "DocType", "target": "Subscription Plan"', group)

		self.assertIn('if target_type == "DocType":', source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', source)

	def test_retailedge_does_not_wrap_native_subscription_generation(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()

		self.assertNotIn("generate_subscription_invoice", source)
		self.assertNotIn("create_subscription_invoice", source)
		self.assertNotIn("process_subscriptions", source)
		self.assertNotIn("submit_subscription_invoice", source)
		self.assertNotIn('frappe.get_doc("Subscription"', source)
		self.assertNotIn('frappe.new_doc("Subscription"', source)
		self.assertNotIn('"doctype": "Subscription"', source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)


if __name__ == "__main__":
	import unittest

	unittest.main()
