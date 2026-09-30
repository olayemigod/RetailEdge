from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from retailedge.coreedge_sales_quota import (
	OPERATION_DOCTYPE,
	SalesTransactionQuotaConfig,
	before_submit_sales_transaction_quota,
	finalize_sales_quota_operation,
	is_counted_sales_transaction,
	make_sales_quota_operation_key,
	retry_pending_sales_quota_operations,
)
from retailedge.integrations.coreedge_remote_usage import CoreEdgeRemoteUsageUnavailable


class SalesQuotaContractTests(unittest.TestCase):
	def _doc(self, doctype="Sales Invoice", name="SINV-TEST-001", **values):
		return SimpleNamespace(
			doctype=doctype,
			name=name,
			company=values.pop("company", "Test Company"),
			branch=values.pop("branch", None),
			is_return=values.pop("is_return", 0),
			is_consolidated=values.pop("is_consolidated", 0),
			**values,
		)

	def test_counting_contract_counts_positive_sales_invoice(self):
		self.assertEqual(
			is_counted_sales_transaction(self._doc()),
			(True, "counted_sale"),
		)

	def test_counting_contract_counts_positive_pos_invoice(self):
		self.assertEqual(
			is_counted_sales_transaction(
				self._doc(doctype="POS Invoice", name="POSINV-TEST-001")
			),
			(True, "counted_sale"),
		)

	def test_counting_contract_skips_returns(self):
		for doctype in ("Sales Invoice", "POS Invoice"):
			eligible, reason = is_counted_sales_transaction(
				self._doc(doctype=doctype, is_return=1)
			)
			self.assertFalse(eligible)
			self.assertEqual(reason, "return_or_credit_note")

	def test_counting_contract_skips_consolidated_pos_closing_sales_invoice(self):
		eligible, reason = is_counted_sales_transaction(
			self._doc(is_consolidated=1)
		)
		self.assertFalse(eligible)
		self.assertEqual(reason, "pos_consolidated_sales_invoice")

	def test_counting_contract_skips_unsupported_doctype(self):
		eligible, reason = is_counted_sales_transaction(
			self._doc(doctype="Sales Order", name="SO-001")
		)
		self.assertFalse(eligible)
		self.assertEqual(reason, "unsupported_doctype")

	def test_config_is_disabled_and_fail_closed_by_default(self):
		config = SalesTransactionQuotaConfig.from_mapping({})
		self.assertFalse(config.enabled)
		self.assertTrue(config.fail_closed)
		self.assertEqual(config.entitlement_key, "SALES_TRANSACTIONS")
		self.assertEqual(config.reservation_seconds, 3600)

	@patch("retailedge.coreedge_sales_quota.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota.get_sales_transaction_quota_config")
	def test_disabled_integration_never_calls_remote(self, mock_config, mock_client):
		mock_config.return_value = SalesTransactionQuotaConfig(enabled=False)
		before_submit_sales_transaction_quota(self._doc())
		mock_client.assert_not_called()

	@patch("retailedge.coreedge_sales_quota.frappe.db.after_rollback.add")
	@patch("retailedge.coreedge_sales_quota.frappe.db.after_commit.add")
	@patch("retailedge.coreedge_sales_quota._enqueue_finalize_operation")
	@patch("retailedge.coreedge_sales_quota._insert_quota_operation")
	@patch("retailedge.coreedge_sales_quota.frappe.db.get_value", return_value=None)
	@patch("retailedge.coreedge_sales_quota.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota.get_sales_transaction_quota_config")
	def test_successful_reserve_registers_commit_and_rollback_paths(
		self,
		mock_config,
		mock_client,
		_mock_existing,
		mock_insert,
		mock_enqueue_finalize,
		mock_after_commit,
		mock_after_rollback,
	):
		mock_config.return_value = SalesTransactionQuotaConfig(enabled=True)
		client = MagicMock()
		client.reserve_usage.return_value = {
			"data": {
				"ok": True,
				"status": "Reserved",
				"quota": {
					"status": "Active",
					"reservation_reference": "CEUR-TEST-001",
					"expires_on": "2026-10-01 01:00:00",
					"warning": False,
					"reason_code": "WITHIN_LIMIT",
					"message": "Within limit",
				},
			}
		}
		mock_client.return_value = client
		mock_insert.return_value = SimpleNamespace(name="quota-op-001")
		doc = self._doc()

		before_submit_sales_transaction_quota(doc)

		client.reserve_usage.assert_called_once()
		kwargs = client.reserve_usage.call_args.kwargs
		self.assertEqual(kwargs["reference_doctype"], "Sales Invoice")
		self.assertEqual(kwargs["reference_name"], "SINV-TEST-001")
		self.assertEqual(kwargs["expires_in_seconds"], 3600)
		mock_after_commit.assert_called_once()
		commit_callback = mock_after_commit.call_args.args[0]
		commit_callback()
		mock_enqueue_finalize.assert_called_once_with("quota-op-001")
		mock_after_rollback.assert_called_once()

	def test_operation_key_is_stable_and_scoped_by_doctype(self):
		first = make_sales_quota_operation_key("Sales Invoice", "SINV-001")
		second = make_sales_quota_operation_key("Sales Invoice", "SINV-001")
		pos = make_sales_quota_operation_key("POS Invoice", "SINV-001")
		self.assertEqual(first, second)
		self.assertNotEqual(first, pos)
		self.assertLessEqual(len(first), 140)

	@patch("retailedge.coreedge_sales_quota.frappe.db.get_value", return_value=None)
	@patch("retailedge.coreedge_sales_quota.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota.get_sales_transaction_quota_config")
	def test_explicit_quota_denial_blocks_even_when_outage_policy_is_fail_open(
		self,
		mock_config,
		mock_client,
		_mock_existing,
	):
		mock_config.return_value = SalesTransactionQuotaConfig(
			enabled=True,
			fail_closed=False,
		)
		client = MagicMock()
		client.reserve_usage.return_value = {
			"data": {
				"ok": False,
				"status": "Blocked",
				"reason_code": "LIMIT_EXCEEDED",
				"message": "Limit exceeded",
			}
		}
		mock_client.return_value = client
		with patch("retailedge.coreedge_sales_quota._log_quota_failure"):
			with self.assertRaises(frappe.ValidationError):
				before_submit_sales_transaction_quota(self._doc())

	@patch("retailedge.coreedge_sales_quota._log_quota_failure")
	@patch("retailedge.coreedge_sales_quota.frappe.db.get_value", return_value=None)
	@patch("retailedge.coreedge_sales_quota.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota.get_sales_transaction_quota_config")
	def test_remote_outage_fails_closed_by_default(
		self,
		mock_config,
		mock_client,
		_mock_existing,
		_mock_log,
	):
		mock_config.return_value = SalesTransactionQuotaConfig(enabled=True, fail_closed=True)
		client = MagicMock()
		client.reserve_usage.side_effect = CoreEdgeRemoteUsageUnavailable("down")
		mock_client.return_value = client
		with self.assertRaises(frappe.ValidationError):
			before_submit_sales_transaction_quota(self._doc())

	@patch("retailedge.coreedge_sales_quota._log_quota_failure")
	@patch("retailedge.coreedge_sales_quota.frappe.db.get_value", return_value=None)
	@patch("retailedge.coreedge_sales_quota.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota.get_sales_transaction_quota_config")
	def test_remote_outage_can_be_explicitly_fail_open(
		self,
		mock_config,
		mock_client,
		_mock_existing,
		_mock_log,
	):
		mock_config.return_value = SalesTransactionQuotaConfig(enabled=True, fail_closed=False)
		client = MagicMock()
		client.reserve_usage.side_effect = CoreEdgeRemoteUsageUnavailable("down")
		mock_client.return_value = client
		before_submit_sales_transaction_quota(self._doc())

	@patch("retailedge.coreedge_sales_quota._release_rolled_back_reservation")
	@patch("retailedge.coreedge_sales_quota.frappe.db.after_rollback.add")
	@patch("retailedge.coreedge_sales_quota.frappe.db.after_commit.add")
	@patch("retailedge.coreedge_sales_quota._insert_quota_operation")
	@patch("retailedge.coreedge_sales_quota.frappe.db.get_value", return_value=None)
	@patch("retailedge.coreedge_sales_quota.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota.get_sales_transaction_quota_config")
	def test_registered_rollback_callback_releases_reservation(
		self,
		mock_config,
		mock_client,
		_mock_existing,
		mock_insert,
		_mock_after_commit,
		mock_after_rollback,
		mock_release,
	):
		mock_config.return_value = SalesTransactionQuotaConfig(enabled=True)
		client = MagicMock()
		client.reserve_usage.return_value = {
			"data": {
				"ok": True,
				"quota": {
					"status": "Active",
					"reservation_reference": "CEUR-ROLLBACK",
				}
			}
		}
		mock_client.return_value = client
		mock_insert.return_value = SimpleNamespace(name="quota-op-rollback")
		before_submit_sales_transaction_quota(self._doc())

		callback = mock_after_rollback.call_args.args[0]
		callback()
		mock_release.assert_called_once()
		self.assertEqual(
			mock_release.call_args.kwargs["reservation_reference"],
			"CEUR-ROLLBACK",
		)

	def test_hooks_attach_before_submit_only_and_no_cancel_refund_hook(self):
		hooks = Path(
			frappe.get_app_path("retailedge", "hooks.py")
		).read_text()
		self.assertIn(
			'"before_submit": "retailedge.coreedge_sales_quota.before_submit_sales_transaction_quota"',
			hooks,
		)
		self.assertNotIn(
			'"on_cancel": "retailedge.coreedge_sales_quota',
			hooks,
		)


class SalesQuotaOperationTests(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.delete(OPERATION_DOCTYPE, {"operation_key": ["like", "quota-operation-%"]})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete(OPERATION_DOCTYPE, {"source_name": ["like", "quota-test-%"]})
		super().tearDown()

	def _operation(self, suffix="one"):
		doc = frappe.get_doc(
			{
				"doctype": OPERATION_DOCTYPE,
				"operation_key": f"quota-operation-{suffix}",
				"status": "Pending Finalize",
				"source_doctype": "User",
				"source_name": "Administrator",
				"entitlement_key": "SALES_TRANSACTIONS",
				"units": 1,
				"reservation_reference": f"CEUR-{suffix}",
				"reservation_expires_on": add_to_date(now_datetime(), hours=1),
				"reserve_idempotency_key": f"reserve-{suffix}",
				"finalize_idempotency_key": f"finalize-{suffix}",
				"release_idempotency_key": f"release-{suffix}",
				"reserved_on": now_datetime(),
			}
		)
		doc.flags.allow_retailedge_quota_operation_create = True
		return doc.insert(ignore_permissions=True)

	def test_direct_operation_creation_is_blocked(self):
		doc = frappe.get_doc(
			{
				"doctype": OPERATION_DOCTYPE,
				"operation_key": "quota-operation-forged",
				"status": "Pending Finalize",
				"source_doctype": "User",
				"source_name": "Administrator",
				"entitlement_key": "SALES_TRANSACTIONS",
				"units": 1,
				"reservation_reference": "CEUR-forged",
				"reserve_idempotency_key": "reserve-forged",
				"finalize_idempotency_key": "finalize-forged",
				"release_idempotency_key": "release-forged",
				"reserved_on": now_datetime(),
			}
		)
		with self.assertRaises(frappe.PermissionError):
			doc.insert(ignore_permissions=True)

	def test_operation_is_engine_updated_and_non_deletable(self):
		doc = self._operation("protected")
		doc.status = "Finalized"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(OPERATION_DOCTYPE, doc.name, ignore_permissions=True)

	@patch("retailedge.coreedge_sales_quota._lock_operation")
	@patch("retailedge.coreedge_sales_quota._save_operation")
	@patch("retailedge.coreedge_sales_quota.frappe.db.get_value", return_value=1)
	@patch("retailedge.coreedge_sales_quota.frappe.get_doc")
	@patch("retailedge.coreedge_sales_quota.get_remote_usage_client")
	def test_finalize_success_marks_operation_finalized(
		self,
		mock_client,
		mock_get_doc,
		_mock_docstatus,
		mock_save,
		_mock_lock,
	):
		operation = SimpleNamespace(
			name="op-finalize",
			status="Pending Finalize",
			attempt_count=0,
			last_attempt_on=None,
			source_doctype="Sales Invoice",
			source_name="SINV-001",
			reservation_expires_on=add_to_date(now_datetime(), hours=1),
			reservation_reference="CEUR-finalize",
			finalize_idempotency_key="finalize-key",
			entitlement_key="SALES_TRANSACTIONS",
			last_error=None,
			finalized_on=None,
			reason_code=None,
			remote_message=None,
		)
		mock_get_doc.return_value = operation
		client = MagicMock()
		client.finalize_usage.return_value = {
			"data": {
				"ok": True,
				"quota": {
					"reason_code": "RESERVATION_FINALIZED",
					"message": "Finalized",
				}
			}
		}
		mock_client.return_value = client

		result = finalize_sales_quota_operation("op-finalize")

		self.assertEqual(result["status"], "Finalized")
		self.assertEqual(operation.status, "Finalized")
		self.assertEqual(operation.attempt_count, 1)
		mock_save.assert_called_once()

	@patch("retailedge.coreedge_sales_quota._lock_operation")
	@patch("retailedge.coreedge_sales_quota._save_operation")
	@patch("retailedge.coreedge_sales_quota.frappe.db.get_value", return_value=1)
	@patch("retailedge.coreedge_sales_quota.frappe.get_doc")
	@patch("retailedge.coreedge_sales_quota.get_remote_usage_client")
	def test_finalize_transport_failure_remains_pending_for_retry(
		self,
		mock_client,
		mock_get_doc,
		_mock_docstatus,
		mock_save,
		_mock_lock,
	):
		operation = SimpleNamespace(
			name="op-retry",
			status="Pending Finalize",
			attempt_count=0,
			last_attempt_on=None,
			source_doctype="Sales Invoice",
			source_name="SINV-002",
			reservation_expires_on=add_to_date(now_datetime(), hours=1),
			reservation_reference="CEUR-retry",
			finalize_idempotency_key="finalize-retry",
			entitlement_key="SALES_TRANSACTIONS",
			last_error=None,
			finalized_on=None,
			reason_code=None,
			remote_message=None,
		)
		mock_get_doc.return_value = operation
		client = MagicMock()
		client.finalize_usage.side_effect = CoreEdgeRemoteUsageUnavailable("temporary")
		mock_client.return_value = client

		result = finalize_sales_quota_operation("op-retry")

		self.assertEqual(result["status"], "Pending Finalize")
		self.assertEqual(operation.attempt_count, 1)
		self.assertIn("temporary", operation.last_error)
		mock_save.assert_called_once()

	@patch("retailedge.coreedge_sales_quota._lock_operation")
	@patch("retailedge.coreedge_sales_quota._save_operation")
	@patch("retailedge.coreedge_sales_quota.frappe.db.get_value", return_value=1)
	@patch("retailedge.coreedge_sales_quota.frappe.get_doc")
	def test_expired_reservation_moves_to_needs_review(
		self,
		mock_get_doc,
		_mock_docstatus,
		mock_save,
		_mock_lock,
	):
		operation = SimpleNamespace(
			name="op-expired",
			status="Pending Finalize",
			attempt_count=0,
			last_attempt_on=None,
			source_doctype="Sales Invoice",
			source_name="SINV-003",
			reservation_expires_on=add_to_date(now_datetime(), minutes=-1),
			reservation_reference="CEUR-expired",
			finalize_idempotency_key="finalize-expired",
			entitlement_key="SALES_TRANSACTIONS",
			last_error=None,
			finalized_on=None,
			reason_code=None,
			remote_message=None,
		)
		mock_get_doc.return_value = operation

		result = finalize_sales_quota_operation("op-expired")

		self.assertEqual(result["status"], "Needs Review")
		self.assertIn("expired", operation.last_error.lower())
		mock_save.assert_called_once()

	@patch("retailedge.coreedge_sales_quota._enqueue_finalize_operation")
	@patch("retailedge.coreedge_sales_quota.frappe.get_all")
	def test_retry_worker_queues_only_pending_operations(self, mock_get_all, mock_enqueue):
		mock_get_all.return_value = [
			frappe._dict(name="op-one"),
			frappe._dict(name="op-two"),
		]
		mock_enqueue.return_value = True
		queued = retry_pending_sales_quota_operations()
		self.assertEqual(queued, 2)
		self.assertEqual(mock_enqueue.call_count, 2)


if __name__ == "__main__":
	unittest.main()
