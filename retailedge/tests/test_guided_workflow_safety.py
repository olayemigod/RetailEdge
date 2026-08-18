from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

GUIDED_BACKENDS = (
	"guided_sales_invoice.py",
	"guided_payment.py",
	"guided_cash_transfer.py",
	"cash_custody.py",
	"guided_purchase_invoice.py",
	"guided_cashier_expense.py",
	"guided_stock_transfer.py",
	"guided_stock_adjustment.py",
)


class TestGuidedWorkflowSafety(unittest.TestCase):
	def test_guided_backends_do_not_submit_or_apply_workflows(self):
		for filename in GUIDED_BACKENDS:
			with self.subTest(filename=filename):
				source = (APP_ROOT / filename).read_text(encoding="utf-8")
				self.assertNotIn(".submit()", source)
				self.assertNotIn("frappe.model.workflow.apply_workflow", source)
				self.assertNotIn("apply_workflow(", source)
				self.assertNotIn("docstatus = 1", source)
				self.assertNotIn("docstatus=1", source)

	def test_business_hub_describes_guided_results_as_drafts(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
		).read_text(encoding="utf-8")
		self.assertIn("saved as Draft", component)
		self.assertNotIn("transaction completed", component.lower())
		self.assertNotIn("workflow completed", component.lower())

	def test_stock_adjustment_is_permission_owned_by_stock_reconciliation(self):
		from retailedge.edgesuite_ui import QUICK_ACTIONS

		action = next(action for action in QUICK_ACTIONS if action["key"] == "adjust-stock")
		self.assertEqual(action["doctype"], "Stock Reconciliation")


if __name__ == "__main__":
	unittest.main()
