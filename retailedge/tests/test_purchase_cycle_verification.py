from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import frappe

from retailedge.purchase_cycle_verification import (
	MAX_VERIFICATION_INVOICES,
	_classify_invoice,
	_coverage_status,
	_buying_policy,
)

APP_ROOT = Path(__file__).resolve().parents[1]


def row(**values):
	return frappe._dict(values)


class TestPurchaseCycleVerification(TestCase):
	def test_fully_linked_invoice_is_linked(self):
		result = _classify_invoice(
			invoice="PINV-0001",
			is_return=False,
			items=[row(purchase_order="PO-1", po_detail="POI-1", purchase_receipt="PR-1", pr_detail="PRI-1", stock_qty=5, base_net_rate=100)],
			po_details={"POI-1": row(name="POI-1", parent="PO-1", stock_qty=10, base_net_rate=100)},
			pr_details={"PRI-1": row(name="PRI-1", parent="PR-1", stock_qty=10, base_net_rate=100)},
			permitted_pos={"PO-1"},
			permitted_prs={"PR-1"},
		)
		self.assertEqual(result["verification_status"], "Linked")
		self.assertEqual(result["po_links"], "1/1")
		self.assertEqual(result["receipt_links"], "1/1")
		self.assertEqual(result["review_flags"], 0)

	def test_po_only_is_not_falsely_called_an_error(self):
		result = _classify_invoice(
			invoice="PINV-0002",
			is_return=False,
			items=[row(purchase_order="PO-1", po_detail="POI-1", purchase_receipt="", pr_detail="", stock_qty=3, base_net_rate=75)],
			po_details={"POI-1": row(name="POI-1", parent="PO-1", stock_qty=10, base_net_rate=75)},
			pr_details={},
			permitted_pos={"PO-1"},
			permitted_prs=set(),
		)
		self.assertEqual(result["verification_status"], "PO Linked")
		self.assertEqual(result["review_flags"], 0)

	def test_partial_billing_below_receipt_quantity_is_not_flagged(self):
		result = _classify_invoice(
			invoice="PINV-0003",
			is_return=False,
			items=[row(purchase_order="PO-1", po_detail="POI-1", purchase_receipt="PR-1", pr_detail="PRI-1", stock_qty=4, base_net_rate=50)],
			po_details={"POI-1": row(name="POI-1", parent="PO-1", stock_qty=10, base_net_rate=50)},
			pr_details={"PRI-1": row(name="PRI-1", parent="PR-1", stock_qty=10, base_net_rate=50)},
			permitted_pos={"PO-1"},
			permitted_prs={"PR-1"},
		)
		self.assertEqual(result["verification_status"], "Linked")
		self.assertEqual(result["review_flags"], 0)
		self.assertNotIn("quantity", result["review_reason"].lower())

	def test_invoice_quantity_above_direct_receipt_quantity_is_review(self):
		result = _classify_invoice(
			invoice="PINV-0004",
			is_return=False,
			items=[row(purchase_order="PO-1", po_detail="POI-1", purchase_receipt="PR-1", pr_detail="PRI-1", stock_qty=11, base_net_rate=50)],
			po_details={"POI-1": row(name="POI-1", parent="PO-1", stock_qty=20, base_net_rate=50)},
			pr_details={"PRI-1": row(name="PRI-1", parent="PR-1", stock_qty=10, base_net_rate=50)},
			permitted_pos={"PO-1"},
			permitted_prs={"PR-1"},
		)
		self.assertEqual(result["verification_status"], "Review")
		self.assertEqual(result["review_flags"], 1)
		self.assertIn("exceeds", result["review_reason"].lower())

	def test_company_currency_rate_difference_is_review(self):
		result = _classify_invoice(
			invoice="PINV-0005",
			is_return=False,
			items=[row(purchase_order="PO-1", po_detail="POI-1", purchase_receipt="", pr_detail="", stock_qty=2, base_net_rate=101)],
			po_details={"POI-1": row(name="POI-1", parent="PO-1", stock_qty=10, base_net_rate=100)},
			pr_details={},
			permitted_pos={"PO-1"},
			permitted_prs=set(),
		)
		self.assertEqual(result["verification_status"], "Review")
		self.assertEqual(result["review_flags"], 1)
		self.assertIn("rate differs", result["review_reason"].lower())

	def test_mixed_and_unlinked_coverage_are_neutral(self):
		self.assertEqual(_coverage_status(line_count=2, po_links=1, receipt_links=1, review_flags=0), "Mixed Links")
		self.assertEqual(_coverage_status(line_count=2, po_links=0, receipt_links=0, review_flags=0), "Unlinked")

	def test_return_is_classified_separately(self):
		result = _classify_invoice(
			invoice="PINV-RET-1",
			is_return=True,
			items=[row(purchase_order="PO-1", po_detail="POI-1", purchase_receipt="PR-1", pr_detail="PRI-1", stock_qty=-1, base_net_rate=100)],
			po_details={},
			pr_details={},
			permitted_pos=set(),
			permitted_prs=set(),
		)
		self.assertEqual(result["verification_status"], "Return")
		self.assertEqual(result["review_flags"], 0)

	def test_buying_policy_is_read_only_native_context(self):
		settings = frappe._dict(
			po_required="Yes",
			pr_required="No",
			maintain_same_rate=1,
			maintain_same_rate_action="Warn",
		)
		with (
			patch("retailedge.purchase_cycle_verification.frappe.has_permission", return_value=True),
			patch("retailedge.purchase_cycle_verification.frappe.get_single", return_value=settings),
		):
			policy = _buying_policy()
		self.assertEqual(policy["po_required"], "Yes")
		self.assertEqual(policy["pr_required"], "No")
		self.assertEqual(policy["maintain_same_rate"], 1)
		self.assertEqual(policy["maintain_same_rate_action"], "Warn")

	def test_scope_is_bounded_and_source_has_no_posting_side_effects(self):
		self.assertEqual(MAX_VERIFICATION_INVOICES, 100)
		source = (APP_ROOT / "purchase_cycle_verification.py").read_text()
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn('new_doc("GL Entry")', source)
		self.assertNotIn('new_doc("Stock Ledger Entry")', source)
		self.assertNotIn('new_doc("Payment Entry")', source)
		self.assertNotIn(".submit()", source)


if __name__ == "__main__":
	import unittest

	unittest.main()
