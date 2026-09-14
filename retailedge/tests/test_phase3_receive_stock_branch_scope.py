from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import professional_purchase_receipt as receipt


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_purchase_receipt.py"


class TestPhase3ReceiveStockBranchScope(unittest.TestCase):
	@patch.object(receipt, "validate_guided_branch_warehouse")
	@patch.object(receipt.frappe.db, "get_value", return_value="RetailEdge Consulting")
	def test_receiving_warehouse_is_revalidated_against_po_branch(
		self,
		_mock_company,
		mock_validate,
	):
		blocker = receipt._warehouse_scope_blocker(
			warehouse="Ketu Stores - RC",
			company="RetailEdge Consulting",
			branch="Ketu",
			item_code="ITEM-001",
		)
		self.assertIsNone(blocker)
		mock_validate.assert_called_once_with(
			company="RetailEdge Consulting",
			branch="Ketu",
			warehouse="Ketu Stores - RC",
			user=frappe.session.user,
		)

	@patch.object(
		receipt,
		"validate_guided_branch_warehouse",
		side_effect=frappe.ValidationError("Branch mismatch"),
	)
	@patch.object(receipt.frappe.db, "get_value", return_value="RetailEdge Consulting")
	def test_invalid_branch_warehouse_becomes_edgesuite_preflight_blocker(
		self,
		_mock_company,
		_mock_validate,
	):
		blocker = receipt._warehouse_scope_blocker(
			warehouse="Ikeja Stores - RC",
			company="RetailEdge Consulting",
			branch="Ketu",
			item_code="ITEM-001",
		)
		self.assertEqual(blocker["key"], "warehouse_branch")
		self.assertEqual(blocker["item_code"], "ITEM-001")
		self.assertIn("Ketu", blocker["label"])
		self.assertIn("Ikeja Stores - RC", blocker["label"])

	@patch.object(receipt, "validate_guided_branch_warehouse")
	@patch.object(receipt.frappe.db, "get_value", return_value="Other Company")
	def test_cross_company_warehouse_is_blocked_before_branch_validation(
		self,
		_mock_company,
		mock_validate,
	):
		blocker = receipt._warehouse_scope_blocker(
			warehouse="Other Stores - OC",
			company="RetailEdge Consulting",
			branch="Ketu",
			item_code="ITEM-001",
		)
		self.assertEqual(blocker["key"], "warehouse_company")
		mock_validate.assert_not_called()

	def test_receive_stock_uses_current_operational_contract_not_legacy_branch_validator(self):
		source = BACKEND.read_text(encoding="utf-8")
		self.assertIn("validate_guided_branch_warehouse", source)
		self.assertIn("_warehouse_scope_blocker(", source)
		self.assertIn('"key": "warehouse_branch"', source)
		self.assertNotIn("validate_user_branch_access", source)

	def test_preview_and_workflow_draft_both_use_same_warehouse_preflight(self):
		source = BACKEND.read_text(encoding="utf-8")
		self.assertGreaterEqual(source.count("_warehouse_scope_blocker("), 3)
		self.assertIn('"standard_receipt_eligible": not blockers', source)
		self.assertIn("if blockers:", source)


if __name__ == "__main__":
	unittest.main()
