from __future__ import annotations

from unittest import TestCase

import frappe

from retailedge.purchase_cycle_verification import _classify_invoice


class TestPurchaseCycleVerificationReferenceIntegrity(TestCase):
	def test_po_item_must_belong_to_named_purchase_order(self):
		result = _classify_invoice(
			invoice="PINV-PO-MISMATCH",
			is_return=False,
			items=[frappe._dict(purchase_order="PO-1", po_detail="POI-1", purchase_receipt="", pr_detail="", stock_qty=1, base_net_rate=10)],
			po_details={"POI-1": frappe._dict(name="POI-1", parent="PO-2", stock_qty=1, base_net_rate=10)},
			pr_details={},
			permitted_pos={"PO-1", "PO-2"},
			permitted_prs=set(),
		)
		self.assertEqual(result["verification_status"], "Review")
		self.assertIn("does not belong", result["review_reason"])

	def test_receipt_item_must_belong_to_named_purchase_receipt(self):
		result = _classify_invoice(
			invoice="PINV-PR-MISMATCH",
			is_return=False,
			items=[frappe._dict(purchase_order="", po_detail="", purchase_receipt="PR-1", pr_detail="PRI-1", stock_qty=1, base_net_rate=10)],
			po_details={},
			pr_details={"PRI-1": frappe._dict(name="PRI-1", parent="PR-2", stock_qty=1, base_net_rate=10)},
			permitted_pos=set(),
			permitted_prs={"PR-1", "PR-2"},
		)
		self.assertEqual(result["verification_status"], "Review")
		self.assertIn("does not belong", result["review_reason"])


if __name__ == "__main__":
	import unittest

	unittest.main()
