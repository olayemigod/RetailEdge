import unittest
from unittest.mock import patch

import frappe

from retailedge import bank_internal_transfer_confirmation_guard as guard


class InternalTransferConfirmationGuardTests(unittest.TestCase):
	@patch.object(guard.identity, "_opposite_confirmed_leg_rows")
	@patch.object(guard.identity, "_same_leg_match_rows", return_value=[])
	@patch.object(guard.identity, "_is_submitted_internal_transfer", return_value=True)
	@patch.object(guard.frappe.db, "get_value", return_value=None)
	@patch.object(guard.frappe, "throw")
	def test_opposite_leg_is_allowed_without_false_throw(
		self,
		frappe_throw,
		_get_value,
		_is_internal_transfer,
		_same_leg_rows,
		opposite_rows,
	):
		opposite_rows.return_value = [frappe._dict({"name": "MATCH-IN", "bank_transaction": "BT-IN"})]
		doc = frappe._dict(
			{
				"name": "MATCH-OUT",
				"bank_transaction": "BT-OUT",
				"payment_entry": "ACC-PAY-2026-00007",
				"sales_invoice": None,
			}
		)

		self.assertTrue(guard.validate_internal_transfer_confirmation_leg(doc))
		frappe_throw.assert_not_called()

	@patch.object(guard.identity, "_opposite_confirmed_leg_rows", return_value=[])
	@patch.object(guard.identity, "_same_leg_match_rows")
	@patch.object(guard.identity, "_is_submitted_internal_transfer", return_value=True)
	@patch.object(guard.frappe.db, "get_value", return_value=None)
	def test_same_leg_duplicate_still_blocks(
		self,
		_get_value,
		_is_internal_transfer,
		same_leg_rows,
		_opposite_rows,
	):
		same_leg_rows.return_value = [frappe._dict({"name": "MATCH-OUT-OLD", "bank_transaction": "BT-OUT-OLD"})]
		doc = frappe._dict(
			{
				"name": "MATCH-OUT",
				"bank_transaction": "BT-OUT",
				"payment_entry": "ACC-PAY-2026-00007",
				"sales_invoice": None,
			}
		)

		with self.assertRaises(frappe.ValidationError):
			guard.validate_internal_transfer_confirmation_leg(doc)

	@patch.object(guard.identity, "_is_submitted_internal_transfer", return_value=False)
	def test_ordinary_payment_entry_is_not_handled(self, _is_internal_transfer):
		doc = frappe._dict(
			{
				"name": "MATCH-1",
				"bank_transaction": "BT-1",
				"payment_entry": "ACC-PAY-1",
				"sales_invoice": None,
			}
		)
		self.assertFalse(guard.validate_internal_transfer_confirmation_leg(doc))


if __name__ == "__main__":
	unittest.main()
