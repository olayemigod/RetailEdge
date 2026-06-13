# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch
from retailedge.services.edgepay_handoff_consumer import (
	fetch_pending_edgepay_handoffs,
	process_edgepay_handoff,
	process_pending_edgepay_handoffs,
	validate_edgepay_handoff,
	mark_edgepay_evidence_reviewed,
	mark_edgepay_evidence_rejected
)

class TestEdgePayHandoffConsumer(FrappeTestCase):
	def setUp(self):
		super(TestEdgePayHandoffConsumer, self).setUp()
		self.original_exists = frappe.db.exists
		self.original_get_doc = frappe.get_doc
		
		# Start global patchers for tests
		self.exists_patcher = patch("frappe.db.exists", side_effect=self.mock_exists)
		self.mocked_exists = self.exists_patcher.start()
		
		self.get_doc_patcher = patch("frappe.get_doc", side_effect=self.mock_get_doc)
		self.mocked_get_doc = self.get_doc_patcher.start()
		
		frappe.db.delete("EdgePay Status Handoff Event")
		frappe.db.delete("RetailEdge EdgePay Handoff Log")
		frappe.db.delete("EdgePay Payment Request")
		frappe.db.delete("RetailEdge EdgePay Payment Evidence")
		
		if not frappe.db.exists("EdgePay Provider", "Test Consumer Provider"):
			frappe.get_doc({
				"doctype": "EdgePay Provider",
				"provider_name": "Test Consumer Provider",
				"provider_code": "monnify",
				"enabled": 1,
				"sandbox_mode": 1,
				"provider_type": "Monnify",
				"status": "Active",
				"base_url": "https://sandbox.monnify.com/api",
				"api_key": "test_consumer_api_key",
				"secret_key": "test_consumer_secret_key"
			}).insert()

	def tearDown(self):
		self.get_doc_patcher.stop()
		self.exists_patcher.stop()
		
		frappe.db.delete("EdgePay Status Handoff Event")
		frappe.db.delete("RetailEdge EdgePay Handoff Log")
		frappe.db.delete("EdgePay Payment Request")
		frappe.db.delete("RetailEdge EdgePay Payment Evidence")
		if frappe.db.exists("EdgePay Provider", "Test Consumer Provider"):
			frappe.db.delete("EdgePay Provider", "Test Consumer Provider")
		super(TestEdgePayHandoffConsumer, self).tearDown()

	def mock_exists(self, *args, **kwargs):
		if args:
			dt = args[0]
			dn = args[1] if len(args) > 1 else None
		else:
			dt = kwargs.get("dt")
			dn = kwargs.get("dn")

		if dt == "Sales Invoice" and isinstance(dn, str) and dn.startswith("SINV-RE-"):
			if dn == "SINV-RE-MISSING":
				return False
			return True
		return self.original_exists(*args, **kwargs)

	def mock_get_doc(self, *args, **kwargs):
		if args:
			dt = args[0]
			name = args[1] if len(args) > 1 else None
		else:
			dt = kwargs.get("doctype")
			name = kwargs.get("name")

		if isinstance(dt, str) and dt == "Sales Invoice" and isinstance(name, str) and name.startswith("SINV-RE-"):
			if name == "SINV-RE-ERROR":
				raise Exception("Failed connection to provider using test_consumer_api_key test_consumer_secret_key")
			return frappe._dict({
				"doctype": "Sales Invoice",
				"name": name,
				"grand_total": 1500.0,
				"currency": "NGN",
				"docstatus": 1
			})
		return self.original_get_doc(*args, **kwargs)

	def create_payment_request(self, name, amount=1500.0, currency="NGN"):
		if not frappe.db.exists("EdgePay Payment Request", name):
			doc = frappe.get_doc({
				"doctype": "EdgePay Payment Request",
				"name": name,
				"provider": "Test Consumer Provider",
				"status": "Initiated",
				"amount": amount,
				"currency": currency,
				"customer_name": "Test Customer",
				"customer_email": "test@example.com",
				"request_reference": name + "-ref"
			})
			doc.flags.name_set = True
			doc.insert(ignore_permissions=True)

	def create_handoff_event(self, name, pr_name, source_app="RetailEdge", source_doctype="Sales Invoice", source_name="SINV-RE-0001", amount=1500.0, currency="NGN", status="Pending", request_status="Paid", provider_reference="test-prov-ref-123", transaction_reference="test-tx-ref-123"):
		self.create_payment_request(pr_name, amount=amount, currency=currency)
		doc = frappe.get_doc({
			"doctype": "EdgePay Status Handoff Event",
			"name": name,
			"payment_request": pr_name,
			"source_app": source_app,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"event_source": "Checkout",
			"event_type": "Payment Initiated",
			"request_status": request_status,
			"provider": "Test Consumer Provider",
			"provider_reference": provider_reference,
			"transaction_reference": transaction_reference,
			"amount": amount,
			"currency": currency,
			"processing_status": status,
			"idempotency_key": name + "-idemp"
		})
		doc.flags.name_set = True
		return doc.insert(ignore_permissions=True)

	def test_fetch_pending_edgepay_handoffs_only_for_retailedge(self):
		# Create a RetailEdge event
		self.create_handoff_event("EV-TEST-RE-001", "EP-PRQ-TEST-RE-001", source_app="RetailEdge", source_name="SINV-RE-0001")

		# Create a non-RetailEdge event (e.g. POSnext)
		self.create_handoff_event("EV-TEST-POS-001", "EP-PRQ-TEST-POS-001", source_app="POSnext", source_name="POS-0001")

		pending = fetch_pending_edgepay_handoffs()
		self.assertEqual(len(pending), 1)
		self.assertEqual(pending[0]["source_app"], "RetailEdge")
		self.assertEqual(pending[0]["source_name"], "SINV-RE-0001")

	def test_validate_required_fields(self):
		invalid_event = {
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
		}
		with self.assertRaises(frappe.ValidationError):
			validate_edgepay_handoff(invalid_event)

		invalid_app = {
			"source_app": "POSnext",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-RE-0001",
			"amount": 1000.0,
			"currency": "NGN",
			"request_status": "Initiated"
		}
		with self.assertRaises(frappe.ValidationError):
			validate_edgepay_handoff(invalid_app)

		invalid_amount = {
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-RE-0001",
			"amount": -100.0,
			"currency": "NGN",
			"request_status": "Initiated"
		}
		with self.assertRaises(frappe.ValidationError):
			validate_edgepay_handoff(invalid_amount)

	def test_fails_safely_when_source_document_is_missing(self):
		event = self.create_handoff_event("EV-TEST-RE-002", "EP-PRQ-TEST-RE-002", source_name="SINV-RE-MISSING")
		res = process_edgepay_handoff(event.as_dict())
		self.assertFalse(res)

		event_status = frappe.db.get_value("EdgePay Status Handoff Event", event.name, "processing_status")
		self.assertEqual(event_status, "Failed")

		logs = frappe.get_all("RetailEdge EdgePay Handoff Log", filters={"edgepay_event": event.name}, fields=["*"])
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].processing_status, "Failed")
		self.assertIn("does not exist", logs[0].error_message)

	def test_marks_event_delivered_after_successful_validation(self):
		event = self.create_handoff_event("EV-TEST-RE-003", "EP-PRQ-TEST-RE-003", source_name="SINV-RE-0003")
		res = process_edgepay_handoff(event.as_dict())
		self.assertTrue(res)

		event_status = frappe.db.get_value("EdgePay Status Handoff Event", event.name, "processing_status")
		self.assertEqual(event_status, "Delivered")

		logs = frappe.get_all("RetailEdge EdgePay Handoff Log", filters={"edgepay_event": event.name}, fields=["*"])
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].processing_status, "Processed")

	def test_redacts_secrets_from_errors_and_logs(self):
		event = self.create_handoff_event("EV-TEST-RE-004", "EP-PRQ-TEST-RE-004", source_name="SINV-RE-ERROR")
		res = process_edgepay_handoff(event.as_dict())
		self.assertFalse(res)

		edgepay_err = frappe.db.get_value("EdgePay Status Handoff Event", event.name, "error_message")
		self.assertNotIn("test_consumer_api_key", edgepay_err)
		self.assertNotIn("test_consumer_secret_key", edgepay_err)

		logs = frappe.get_all("RetailEdge EdgePay Handoff Log", filters={"edgepay_event": event.name}, fields=["error_message"])
		self.assertNotIn("test_consumer_api_key", logs[0].error_message)
		self.assertNotIn("test_consumer_secret_key", logs[0].error_message)

	def test_does_not_mutate_host_accounting_or_source_documents(self):
		event = self.create_handoff_event("EV-TEST-RE-005", "EP-PRQ-TEST-RE-005", source_name="SINV-RE-0005")

		pe_count = frappe.db.count("Payment Entry") if frappe.db.exists("DocType", "Payment Entry") else 0
		je_count = frappe.db.count("Journal Entry") if frappe.db.exists("DocType", "Journal Entry") else 0
		gl_count = frappe.db.count("GL Entry") if frappe.db.exists("DocType", "GL Entry") else 0
		bt_count = frappe.db.count("Bank Transaction") if frappe.db.exists("DocType", "Bank Transaction") else 0

		process_edgepay_handoff(event.as_dict())

		self.assertEqual(frappe.db.count("Payment Entry") if frappe.db.exists("DocType", "Payment Entry") else 0, pe_count)
		self.assertEqual(frappe.db.count("Journal Entry") if frappe.db.exists("DocType", "Journal Entry") else 0, je_count)
		self.assertEqual(frappe.db.count("GL Entry") if frappe.db.exists("DocType", "GL Entry") else 0, gl_count)
		self.assertEqual(frappe.db.count("Bank Transaction") if frappe.db.exists("DocType", "Bank Transaction") else 0, bt_count)

	def test_paid_handoff_creates_one_evidence_record_pending_review(self):
		event = self.create_handoff_event("EV-TEST-RE-006", "EP-PRQ-TEST-RE-006", source_name="SINV-RE-0006", request_status="Paid")
		res = process_edgepay_handoff(event.as_dict())
		self.assertTrue(res)

		evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters={"edgepay_handoff_event": event.name}, fields=["*"])
		self.assertEqual(len(evidences), 1)
		self.assertEqual(evidences[0].review_status, "Pending Review")
		self.assertEqual(evidences[0].processing_status, "Evidence Created")
		self.assertEqual(evidences[0].amount, 1500.0)
		self.assertEqual(evidences[0].currency, "NGN")
		self.assertEqual(evidences[0].created_from_edgepay_handoff, 1)

	def test_duplicate_paid_handoff_is_idempotent(self):
		event = self.create_handoff_event("EV-TEST-RE-007", "EP-PRQ-TEST-RE-007", source_name="SINV-RE-0007", request_status="Paid")
		res1 = process_edgepay_handoff(event.as_dict())
		self.assertTrue(res1)
		
		res2 = process_edgepay_handoff(event.as_dict())
		self.assertTrue(res2)

		evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters={"edgepay_handoff_event": event.name}, fields=["*"])
		self.assertEqual(len(evidences), 1)
		self.assertEqual(evidences[0].processing_status, "Evidence Updated")

	def test_failed_handoff_records_non_paid_evidence(self):
		event = self.create_handoff_event("EV-TEST-RE-008", "EP-PRQ-TEST-RE-008", source_name="SINV-RE-0008", request_status="Failed")
		res = process_edgepay_handoff(event.as_dict())
		self.assertTrue(res)

		evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters={"edgepay_handoff_event": event.name}, fields=["*"])
		self.assertEqual(len(evidences), 1)
		self.assertEqual(evidences[0].review_status, "Rejected")
		self.assertEqual(evidences[0].processing_status, "Evidence Created")

	def test_expired_cancelled_handoff_records_non_paid_evidence(self):
		event1 = self.create_handoff_event("EV-TEST-RE-009", "EP-PRQ-TEST-RE-009", source_name="SINV-RE-0009", request_status="Expired")
		event2 = self.create_handoff_event("EV-TEST-RE-010", "EP-PRQ-TEST-RE-010", source_name="SINV-RE-0010", request_status="Cancelled")

		res1 = process_edgepay_handoff(event1.as_dict())
		res2 = process_edgepay_handoff(event2.as_dict())
		self.assertTrue(res1)
		self.assertTrue(res2)

		ev1 = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters={"edgepay_handoff_event": event1.name}, fields=["*"])[0]
		ev2 = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters={"edgepay_handoff_event": event2.name}, fields=["*"])[0]
		self.assertEqual(ev1.review_status, "Rejected")
		self.assertEqual(ev2.review_status, "Rejected")

	def test_pending_handoff_does_not_mark_payment_as_paid(self):
		event = self.create_handoff_event("EV-TEST-RE-011", "EP-PRQ-TEST-RE-011", source_name="SINV-RE-0011", request_status="Pending")
		res = process_edgepay_handoff(event.as_dict())
		self.assertTrue(res)

		evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters={"edgepay_handoff_event": event.name}, fields=["*"])
		self.assertEqual(len(evidences), 1)
		self.assertEqual(evidences[0].review_status, "Pending Review")

	def test_amount_mismatch_sets_exception(self):
		event = self.create_handoff_event("EV-TEST-RE-012", "EP-PRQ-TEST-RE-012", source_name="SINV-RE-012", amount=2000.0)
		res = process_edgepay_handoff(event.as_dict())
		self.assertFalse(res)

		evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters={"edgepay_handoff_event": event.name}, fields=["*"])
		self.assertEqual(len(evidences), 1)
		self.assertEqual(evidences[0].review_status, "Exception")
		self.assertEqual(evidences[0].processing_status, "Failed")
		self.assertIn("Amount mismatch", evidences[0].error_message)

	def test_currency_mismatch_sets_exception(self):
		event = self.create_handoff_event("EV-TEST-RE-013", "EP-PRQ-TEST-RE-013", source_name="SINV-RE-013", currency="USD")
		res = process_edgepay_handoff(event.as_dict())
		self.assertFalse(res)

		evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters={"edgepay_handoff_event": event.name}, fields=["*"])
		self.assertEqual(len(evidences), 1)
		self.assertEqual(evidences[0].review_status, "Exception")
		self.assertEqual(evidences[0].processing_status, "Failed")
		self.assertIn("Currency mismatch", evidences[0].error_message)

	def test_review_actions_update_status_only(self):
		event = self.create_handoff_event("EV-TEST-RE-014", "EP-PRQ-TEST-RE-014", source_name="SINV-RE-014", request_status="Paid")

		initial_pe_count = frappe.db.count("Payment Entry") if frappe.db.exists("DocType", "Payment Entry") else 0
		initial_je_count = frappe.db.count("Journal Entry") if frappe.db.exists("DocType", "Journal Entry") else 0

		res = process_edgepay_handoff(event.as_dict())
		self.assertTrue(res)

		evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters={"edgepay_handoff_event": event.name}, fields=["name"])
		self.assertEqual(len(evidences), 1)
		evidence_name = evidences[0].name

		res_reviewed = mark_edgepay_evidence_reviewed(evidence_name)
		self.assertTrue(res_reviewed["ok"])
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", evidence_name, "review_status"), "Reviewed")

		res_rejected = mark_edgepay_evidence_rejected(evidence_name, reason="Manual Reject reason")
		self.assertTrue(res_rejected["ok"])
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", evidence_name, "review_status"), "Rejected")
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", evidence_name, "error_message"), "Manual Reject reason")

		pe_count = frappe.db.count("Payment Entry") if frappe.db.exists("DocType", "Payment Entry") else 0
		je_count = frappe.db.count("Journal Entry") if frappe.db.exists("DocType", "Journal Entry") else 0
		self.assertEqual(pe_count, initial_pe_count)
		self.assertEqual(je_count, initial_je_count)
