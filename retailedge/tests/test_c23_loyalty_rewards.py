from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestC23LoyaltyRewards(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_status_uses_customer_assignment_and_erpnext_balance_authority(self):
		source = self.read("loyalty_rewards.py")
		for contract in (
			'frappe.db.get_value("Customer", customer, "loyalty_program")',
			"get_loyalty_program_details_with_points",
			'expiry_date=status["posting_date"]',
			'frappe.db.get_value("Loyalty Program", program, "company")',
			'_assert_read("Customer", customer)',
			'_assert_read("Company", company)',
		):
			self.assertIn(contract, source)
		self.assertNotIn('values.get("loyalty_program")', source)
		self.assertNotIn("get_loyalty_programs(", source)

	def test_seller_summary_omits_accounting_configuration(self):
		source = self.read("loyalty_rewards.py")
		status_block = source[source.index("status: dict"):source.index("if not program:")]
		self.assertNotIn("expense_account", status_block)
		self.assertNotIn("cost_center", status_block)
		self.assertIn('"available_points": 0', status_block)
		self.assertIn('"available_redemption_value": 0', status_block)

	def test_draft_handoff_uses_native_sales_invoice_validation(self):
		source = self.read("professional_sales_invoice.py")
		self.assertIn("apply_loyalty_redemption_to_draft", source)
		self.assertLess(source.index("doc.apply_shipping_rule()"), source.index("apply_loyalty_redemption_to_draft(doc"))
		self.assertLess(
			source.index("apply_loyalty_redemption_to_draft(doc"),
			source.index("doc.save()", source.index("needs_save")),
		)
		for fieldname in (
			"redeem_loyalty_points",
			"loyalty_program",
			"loyalty_points",
			"loyalty_amount",
		):
			self.assertIn(fieldname, source)

	def test_loyalty_flow_does_not_write_ledger_or_submit(self):
		sources = self.read("loyalty_rewards.py") + self.read("professional_sales_invoice.py")
		for forbidden in (
			'frappe.new_doc("Loyalty Point Entry")',
			'frappe.get_doc({"doctype": "Loyalty Point Entry"',
			".submit(",
			"ignore_permissions=True",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, sources)

	def test_guided_ui_is_new_invoice_only_and_refreshes_stale_points(self):
		dialog = self.read("public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue")
		self.assertIn("retailedge.loyalty_rewards.get_customer_loyalty_status", dialog)
		self.assertIn("Available Points", dialog)
		self.assertIn("Current Tier", dialog)
		self.assertIn("Point Value", dialog)
		self.assertIn("Programme validity", dialog)
		self.assertIn("Points to Redeem", dialog)
		self.assertIn("this.values.loyalty_points = 0", dialog)
		self.assertIn("this.loyaltyToken += 1", dialog)
		self.assertIn("postingDateChanged", dialog)
		self.assertIn('v-if="values.customer" class="loyalty-panel"', dialog)
		self.assertLess(dialog.index('form v-else class="selling-form"'), dialog.index('class="loyalty-panel"'))
		self.assertLess(dialog.index('class="loyalty-panel"'), dialog.index("</form>"))

	def test_navigation_uses_native_loyalty_program_target(self):
		source = self.read("edgesuite_ui.py")
		start = source.index('"key": "pricing-promotions"')
		end = source.index('"key": "buy"', start)
		group = source[start:end]
		self.assertIn('"target": "Loyalty Program"', group)
		self.assertIn('"target_type": "DocType"', group)
		self.assertEqual(source.count('"target": "Loyalty Program"'), 1)


if __name__ == "__main__":
	unittest.main()
