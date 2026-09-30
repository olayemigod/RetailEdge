from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from retailedge.integrations.coreedge_remote import CoreEdgeRemoteUnavailable
from retailedge.integrations.quota_operations import (
	build_operation_key,
	finalize_quota_operation,
	prepare_transaction_quota,
	release_quota_operation,
	retry_pending_quota_operations,
)


class TestRetailEdgeCoreEdgeQuotaOperationOutbox(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.suffix = uuid.uuid4().hex[:8]
		self.todo = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": f"Quota transaction {self.suffix}",
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete(
			"RetailEdge CoreEdge Quota Operation",
			{"transaction_doctype": "ToDo", "transaction_name": self.todo.name},
		)
		if frappe.db.exists("ToDo", self.todo.name):
			frappe.delete_doc("ToDo", self.todo.name, force=True, ignore_permissions=True)
		super().tearDown()

	def test_operation_key_is_stable_and_event_specific(self):
		first = build_operation_key(
			entitlement_key="RETAILEDGE_SALES_TRANSACTIONS",
			transaction_doctype="Sales Invoice",
			transaction_name="SINV-0001",
			transaction_event="Submit",
		)
		second = build_operation_key(
			entitlement_key="RETAILEDGE_SALES_TRANSACTIONS",
			transaction_doctype="Sales Invoice",
			transaction_name="SINV-0001",
			transaction_event="Submit",
		)
		cancel = build_operation_key(
			entitlement_key="RETAILEDGE_SALES_TRANSACTIONS",
			transaction_doctype="Sales Invoice",
			transaction_name="SINV-0001",
			transaction_event="Cancel",
		)
		self.assertEqual(first, second)
		self.assertNotEqual(first, cancel)
		self.assertLessEqual(len(first), 140)

	def test_prepare_reserves_and_persists_outbox_in_local_transaction(self):
		with (
			patch(
				"retailedge.integrations.quota_operations.reserve_usage",
				return_value=self._reserve_response("CEUR-TEST-001"),
			) as reserve,
			patch.object(frappe.db.after_commit, "add") as after_commit,
			patch.object(frappe.db.after_rollback, "add") as after_rollback,
		):
			result = prepare_transaction_quota(
				self.todo,
				entitlement_key="RETAILEDGE_SALES_TRANSACTIONS",
				units=1,
			)

		self.assertEqual(result["status"], "Reserved")
		self.assertEqual(result["reservation_reference"], "CEUR-TEST-001")
		self.assertTrue(
			frappe.db.exists(
				"RetailEdge CoreEdge Quota Operation",
				result["operation_key"],
			)
		)
		payload = reserve.call_args.kwargs
		self.assertEqual(payload["reference_doctype"], "ToDo")
		self.assertEqual(payload["reference_name"], self.todo.name)
		self.assertTrue(payload["idempotency_key"].startswith("reserve:re-qop-"))
		after_commit.assert_called_once()
		after_rollback.assert_called_once()

	def test_blocked_remote_reservation_creates_no_local_outbox(self):
		with (
			patch(
				"retailedge.integrations.quota_operations.reserve_usage",
				return_value={
					"data": {
						"ok": False,
						"reason_code": "LIMIT_EXCEEDED",
						"message": "Transaction quota exhausted.",
					}
				},
			),
			patch.object(frappe.db.after_commit, "add"),
			patch.object(frappe.db.after_rollback, "add"),
		):
			with self.assertRaises(frappe.ValidationError):
				prepare_transaction_quota(
					self.todo,
					entitlement_key="RETAILEDGE_SALES_TRANSACTIONS",
				)

		self.assertEqual(
			frappe.db.count(
				"RetailEdge CoreEdge Quota Operation",
				{"transaction_name": self.todo.name},
			),
			0,
		)

	def test_repeated_prepare_reuses_existing_operation_without_second_reserve(self):
		with (
			patch(
				"retailedge.integrations.quota_operations.reserve_usage",
				return_value=self._reserve_response("CEUR-TEST-REUSE"),
			) as reserve,
			patch.object(frappe.db.after_commit, "add"),
			patch.object(frappe.db.after_rollback, "add"),
		):
			first = prepare_transaction_quota(
				self.todo,
				entitlement_key="RETAILEDGE_SALES_TRANSACTIONS",
			)
			second = prepare_transaction_quota(
				self.todo,
				entitlement_key="RETAILEDGE_SALES_TRANSACTIONS",
			)

		self.assertEqual(first["operation_key"], second["operation_key"])
		self.assertEqual(reserve.call_count, 1)
		self.assertEqual(
			frappe.db.count(
				"RetailEdge CoreEdge Quota Operation",
				{"transaction_name": self.todo.name},
			),
			1,
		)

	def test_finalize_success_marks_operation_finalized_once(self):
		operation = self._make_operation("Reserved", "CEUR-FINALIZE-001")
		with (
			patch(
				"retailedge.integrations.quota_operations._transaction_state",
				return_value="Submitted",
			),
			patch(
				"retailedge.integrations.quota_operations.finalize_usage",
				return_value={
					"data": {
						"ok": True,
						"status": "Finalized",
						"quota": {
							"status": "Finalized",
							"finalized_on": str(now_datetime()),
						},
					}
				},
			) as finalize,
		):
			first = finalize_quota_operation(operation.name)
			second = finalize_quota_operation(operation.name)

		self.assertEqual(first["status"], "Finalized")
		self.assertEqual(second["status"], "Finalized")
		self.assertEqual(finalize.call_count, 1)
		operation.reload()
		self.assertEqual(operation.attempt_count, 1)

	def test_finalize_unavailable_remains_pending_for_retry(self):
		operation = self._make_operation("Reserved", "CEUR-PENDING-001")
		with (
			patch(
				"retailedge.integrations.quota_operations._transaction_state",
				return_value="Submitted",
			),
			patch(
				"retailedge.integrations.quota_operations.finalize_usage",
				side_effect=CoreEdgeRemoteUnavailable("network unavailable"),
			),
		):
			result = finalize_quota_operation(operation.name)

		self.assertEqual(result["status"], "Finalize Pending")
		operation.reload()
		self.assertEqual(operation.status, "Finalize Pending")
		self.assertTrue(operation.next_retry_on)
		self.assertEqual(operation.last_error_code, "CoreEdgeRemoteUnavailable")

	def test_expired_reservation_becomes_reconciliation_required(self):
		operation = self._make_operation(
			"Reserved",
			"CEUR-EXPIRED-001",
			expires_on=add_to_date(now_datetime(), seconds=-1),
		)
		with (
			patch(
				"retailedge.integrations.quota_operations._transaction_state",
				return_value="Submitted",
			),
			patch(
				"retailedge.integrations.quota_operations.finalize_usage",
			) as finalize,
		):
			result = finalize_quota_operation(operation.name)

		self.assertEqual(result["status"], "Reconciliation Required")
		self.assertEqual(
			result["last_error_code"],
			"RESERVATION_EXPIRED_BEFORE_FINALIZE",
		)
		finalize.assert_not_called()

	def test_cancelled_transaction_is_never_silently_finalized_or_released(self):
		operation = self._make_operation("Reserved", "CEUR-CANCELLED-001")
		with (
			patch(
				"retailedge.integrations.quota_operations._transaction_state",
				return_value="Cancelled",
			),
			patch(
				"retailedge.integrations.quota_operations.finalize_usage",
			) as finalize,
		):
			result = finalize_quota_operation(operation.name)

		self.assertEqual(result["status"], "Reconciliation Required")
		self.assertEqual(
			result["last_error_code"],
			"LOCAL_TRANSACTION_CANCELLED",
		)
		finalize.assert_not_called()

	def test_release_success_marks_operation_released(self):
		operation = self._make_operation("Reserved", "CEUR-RELEASE-001")
		with patch(
			"retailedge.integrations.quota_operations.release_usage",
			return_value={
				"data": {
					"ok": True,
					"status": "Released",
					"quota": {
						"status": "Released",
						"released_on": str(now_datetime()),
					},
				}
			},
		):
			result = release_quota_operation(
				operation.name,
				reason="Business transaction did not commit.",
			)

		self.assertEqual(result["status"], "Released")
		operation.reload()
		self.assertEqual(operation.status, "Released")

	def test_release_unavailable_remains_release_pending(self):
		operation = self._make_operation("Reserved", "CEUR-RELEASE-PENDING")
		with patch(
			"retailedge.integrations.quota_operations.release_usage",
			side_effect=CoreEdgeRemoteUnavailable("network unavailable"),
		):
			result = release_quota_operation(
				operation.name,
				reason="Business transaction did not commit.",
			)

		self.assertEqual(result["status"], "Release Pending")
		operation.reload()
		self.assertTrue(operation.next_retry_on)
		self.assertEqual(operation.last_error_code, "CoreEdgeRemoteUnavailable")

	def test_scheduler_retries_finalize_and_release_pending_rows(self):
		finalize_row = self._make_operation("Finalize Pending", "CEUR-SCHED-FINAL")
		release_row = self._make_operation(
			"Release Pending",
			"CEUR-SCHED-RELEASE",
			transaction_name=self._make_second_todo(),
		)
		release_row.notes = "Retry release after failed business operation."
		release_row.flags.allow_quota_operation_update = True
		release_row.save(ignore_permissions=True)

		with (
			patch(
				"retailedge.integrations.quota_operations.finalize_quota_operation",
				return_value={"status": "Finalized"},
			) as finalize,
			patch(
				"retailedge.integrations.quota_operations.release_quota_operation",
				return_value={"status": "Released"},
			) as release,
		):
			result = retry_pending_quota_operations(limit=10)

		self.assertEqual(result["processed"], 2)
		finalize.assert_called_once_with(finalize_row.name)
		release.assert_called_once()
		self.assertEqual(release.call_args.args[0], release_row.name)

	def test_engine_only_history_blocks_manual_create_update_and_delete(self):
		manual = frappe.get_doc(
			{
				"doctype": "RetailEdge CoreEdge Quota Operation",
				"operation_key": f"manual-{self.suffix}",
				"status": "Reserved",
				"entitlement_key": "TEST",
				"units": 1,
				"transaction_doctype": "ToDo",
				"transaction_name": self.todo.name,
				"transaction_event": "Submit",
				"reservation_reference": "CEUR-MANUAL",
				"reserve_idempotency_key": "reserve-manual",
				"finalize_idempotency_key": "finalize-manual",
				"release_idempotency_key": "release-manual",
			}
		)
		with self.assertRaises(frappe.PermissionError):
			manual.insert(ignore_permissions=True)

		operation = self._make_operation("Reserved", "CEUR-HISTORY-001")
		operation.status = "Failed"
		with self.assertRaises(frappe.PermissionError):
			operation.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(
				"RetailEdge CoreEdge Quota Operation",
				operation.name,
				ignore_permissions=True,
			)

	def test_finalize_and_release_idempotency_keys_are_distinct(self):
		operation = self._make_operation("Reserved", "CEUR-KEYS-001")
		self.assertNotEqual(
			operation.reserve_idempotency_key,
			operation.finalize_idempotency_key,
		)
		self.assertNotEqual(
			operation.finalize_idempotency_key,
			operation.release_idempotency_key,
		)
		self.assertTrue(operation.reserve_idempotency_key.startswith("reserve:"))
		self.assertTrue(operation.finalize_idempotency_key.startswith("finalize:"))
		self.assertTrue(operation.release_idempotency_key.startswith("release:"))

	def test_scheduler_hook_exists_but_sales_invoice_hook_is_still_absent(self):
		import retailedge

		hooks_path = Path(retailedge.__file__).resolve().parent / "hooks.py"
		hooks = hooks_path.read_text()
		self.assertIn(
			"retailedge.integrations.quota_operations.retry_pending_quota_operations",
			hooks,
		)
		sales_hook_block = hooks.split('"Sales Invoice": {', 1)[1].split("},", 1)[0]
		self.assertNotIn("quota", sales_hook_block.lower())

	def test_doctype_permissions_are_read_only_for_human_roles(self):
		import retailedge

		path = (
			Path(retailedge.__file__).resolve().parent
			/ "retailedge"
			/ "doctype"
			/ "retailedge_coreedge_quota_operation"
			/ "retailedge_coreedge_quota_operation.json"
		)
		data = json.loads(path.read_text())
		self.assertTrue(data["permissions"])
		for row in data["permissions"]:
			self.assertEqual(row.get("read"), 1)
			self.assertEqual(row.get("create", 0), 0)
			self.assertEqual(row.get("write", 0), 0)
			self.assertEqual(row.get("delete", 0), 0)

	def _make_operation(
		self,
		status: str,
		reservation_reference: str,
		*,
		expires_on=None,
		transaction_name: str | None = None,
	):
		transaction_name = transaction_name or self.todo.name
		operation_key = build_operation_key(
			entitlement_key="RETAILEDGE_SALES_TRANSACTIONS",
			transaction_doctype="ToDo",
			transaction_name=transaction_name,
			transaction_event="Submit",
		)
		doc = frappe.get_doc(
			{
				"doctype": "RetailEdge CoreEdge Quota Operation",
				"operation_key": operation_key,
				"status": status,
				"entitlement_key": "RETAILEDGE_SALES_TRANSACTIONS",
				"units": 1,
				"transaction_doctype": "ToDo",
				"transaction_name": transaction_name,
				"transaction_event": "Submit",
				"reservation_reference": reservation_reference,
				"reservation_status": "Active",
				"reserved_on": now_datetime(),
				"expires_on": expires_on or add_to_date(now_datetime(), minutes=15),
				"reserve_idempotency_key": f"reserve:{operation_key}",
				"finalize_idempotency_key": f"finalize:{operation_key}",
				"release_idempotency_key": f"release:{operation_key}",
				"actor": "Administrator",
			}
		)
		doc.flags.allow_quota_operation_create = True
		doc.insert(ignore_permissions=True)
		return doc

	def _make_second_todo(self):
		doc = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": f"Quota transaction second {self.suffix}",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(
			lambda: frappe.db.delete("ToDo", {"name": doc.name})
		)
		return doc.name

	def _reserve_response(self, reservation_reference: str):
		return {
			"data": {
				"ok": True,
				"status": "Reserved",
				"quota": {
					"reservation_reference": reservation_reference,
					"status": "Active",
					"reserved_on": str(now_datetime()),
					"expires_on": str(add_to_date(now_datetime(), minutes=15)),
				},
			}
		}
