import unittest
from unittest.mock import patch

import frappe

from retailedge import bank_internal_transfer_identity as identity


class InternalTransferBankLegIdentityTests(unittest.TestCase):
	def test_ordinary_payment_entry_keeps_document_level_identity(self):
		self.assertEqual(
			identity.build_payment_entry_leg_key(
				"ACC-PAY-1",
				"Pay",
				"Outflow",
				paid_from="GT Bank - RC",
				paid_to="Creditors - RC",
			),
			("Payment Entry", "ACC-PAY-1"),
		)

	def test_internal_transfer_inflow_and_outflow_are_distinct_bank_legs(self):
		inflow = identity.build_payment_entry_leg_key(
			"ACC-PAY-2026-00007",
			"Internal Transfer",
			"Inflow",
			paid_from="GT Bank - RC",
			paid_to="Bank - RC",
		)
		outflow = identity.build_payment_entry_leg_key(
			"ACC-PAY-2026-00007",
			"Internal Transfer",
			"Outflow",
			paid_from="GT Bank - RC",
			paid_to="Bank - RC",
		)
		self.assertEqual(
			inflow,
			("Payment Entry", "ACC-PAY-2026-00007", "Inflow", "Bank - RC"),
		)
		self.assertEqual(
			outflow,
			("Payment Entry", "ACC-PAY-2026-00007", "Outflow", "GT Bank - RC"),
		)
		self.assertNotEqual(inflow, outflow)

	def test_internal_transfer_same_bank_leg_remains_duplicate_identity(self):
		first = identity.build_payment_entry_leg_key(
			"ACC-PAY-2026-00007",
			"Internal Transfer",
			"Outflow",
			paid_from="GT Bank - RC",
			paid_to="Bank - RC",
		)
		second = identity.build_payment_entry_leg_key(
			"ACC-PAY-2026-00007",
			"Internal Transfer",
			"Outflow",
			paid_from="GT Bank - RC",
			paid_to="Bank - RC",
		)
		self.assertEqual(first, second)

	def test_internal_transfer_unknown_direction_fails_closed_to_document_identity(self):
		self.assertEqual(
			identity.build_payment_entry_leg_key(
				"ACC-PAY-2026-00007",
				"Internal Transfer",
				"",
				paid_from="GT Bank - RC",
				paid_to="Bank - RC",
			),
			("Payment Entry", "ACC-PAY-2026-00007"),
		)

	@patch.object(identity.frappe.db, "get_value", return_value="RE-BTM-ACTIVE")
	def test_invalid_payment_entry_metadata_fails_closed(self, _get_value):
		self.assertEqual(identity._payment_entry_metadata("PE-ACTIVE"), frappe._dict())
		self.assertFalse(identity._is_submitted_internal_transfer("PE-ACTIVE"))

	@patch.object(identity, "_active_payment_entry_match_rows")
	@patch.object(identity, "_bank_transaction_direction")
	@patch.object(identity, "_payment_entry_metadata")
	def test_same_leg_filter_ignores_only_the_proven_opposite_leg(
		self,
		payment_entry_metadata,
		bank_transaction_direction,
		active_rows,
	):
		payment_entry_metadata.return_value = frappe._dict(
			{
				"name": "ACC-PAY-2026-00007",
				"payment_type": "Internal Transfer",
				"paid_from": "GT Bank - RC",
				"paid_to": "Bank - RC",
				"docstatus": 1,
			}
		)
		bank_transaction_direction.side_effect = lambda bank_transaction: {
			"BT-IN": "Inflow",
			"BT-OUT": "Outflow",
		}.get(bank_transaction, "")
		active_rows.return_value = [
			frappe._dict({"name": "MATCH-IN", "bank_transaction": "BT-IN"}),
			frappe._dict({"name": "MATCH-OUT", "bank_transaction": "BT-OUT"}),
		]

		rows = identity._same_leg_match_rows(
			"ACC-PAY-2026-00007",
			"BT-OUT",
			confirmed_only=True,
		)
		self.assertEqual([row.name for row in rows], ["MATCH-OUT"])

	@patch.object(identity, "_active_payment_entry_match_rows")
	@patch.object(identity, "_bank_transaction_direction")
	@patch.object(identity, "_payment_entry_metadata")
	def test_ambiguous_historical_leg_remains_conflicting(
		self,
		payment_entry_metadata,
		bank_transaction_direction,
		active_rows,
	):
		payment_entry_metadata.return_value = frappe._dict(
			{
				"name": "ACC-PAY-2026-00007",
				"payment_type": "Internal Transfer",
				"paid_from": "GT Bank - RC",
				"paid_to": "Bank - RC",
				"docstatus": 1,
			}
		)
		bank_transaction_direction.side_effect = lambda bank_transaction: {
			"BT-OUT": "Outflow",
			"BT-UNKNOWN": "",
		}.get(bank_transaction, "")
		active_rows.return_value = [
			frappe._dict({"name": "MATCH-UNKNOWN", "bank_transaction": "BT-UNKNOWN"}),
		]

		rows = identity._same_leg_match_rows(
			"ACC-PAY-2026-00007",
			"BT-OUT",
			confirmed_only=True,
		)
		self.assertEqual([row.name for row in rows], ["MATCH-UNKNOWN"])

	@patch.object(identity, "_is_submitted_internal_transfer")
	def test_candidate_key_without_explicit_leg_evidence_keeps_legacy_identity(self, is_internal_transfer):
		original = lambda row: ("Payment Entry", row.get("document_name"))
		row = {
			"document_type": "Payment Entry",
			"document_name": "PE-ACTIVE",
			"bank_transaction": "BT-ACTIVE",
		}
		self.assertEqual(
			identity._patched_candidate_document_key(original, row),
			("Payment Entry", "PE-ACTIVE"),
		)
		is_internal_transfer.assert_not_called()

	@patch.object(identity, "_is_submitted_internal_transfer", return_value=True)
	def test_current_queue_duplicate_key_is_leg_aware(self, _is_internal_transfer):
		original = lambda row: ("Payment Entry", row.get("document_name"))
		row = {
			"document_type": "Payment Entry",
			"document_name": "ACC-PAY-2026-00007",
			"direction": "Outflow",
			"payment_account": "GT Bank - RC",
		}
		self.assertEqual(
			identity._patched_candidate_document_key(original, row),
			("Payment Entry", "ACC-PAY-2026-00007", "Outflow", "GT Bank - RC"),
		)


if __name__ == "__main__":
	unittest.main()
