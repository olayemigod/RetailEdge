# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch
from retailedge.services.edgepay_handoff_consumer import (
	fetch_pending_edgepay_handoffs,
	process_edgepay_handoff,
	process_pending_edgepay_handoffs,
	validate_edgepay_handoff
)

class TestEdgePayHandoffConsumer(FrappeTestCase):
	def setUp(self):
		super(TestEdgePayHandoffConsumer, self).setUp()
		self.original_exists = frappe.db.exists
		frappe.db.delete("EdgePay Status Handoff Event")
		frappe.db.delete("RetailEdge EdgePay Handoff Log")
		frappe.db.delete("EdgePay Payment Request")
		
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
		frappe.db.delete("EdgePay Status Handoff Event")
		frappe.db.delete("RetailEdge EdgePay Handoff Log")
		frappe.db.delete("EdgePay Payment Request")
		if frappe.db.exists("EdgePay Provider", "Test Consumer Provider"):
			frappe.db.delete("EdgePay Provider", "Test Consumer Provider")
		super(TestEdgePayHandoffConsumer, self).tearDown()

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

	def create_handoff_event(self, name, pr_name, source_app="RetailEdge", source_doctype="Sales Invoice", source_name="SINV-RE-0001", amount=1500.0, currency="NGN", status="Pending"):
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
			"request_status": "Initiated",
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

		def mock_exists(dt, dn=None):
			if dt == "Sales Invoice" and dn == "SINV-RE-MISSING":
				return False
			return self.original_exists(dt, dn)

		with patch("frappe.db.exists", side_effect=mock_exists):
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

		def mock_exists(dt, dn=None):
			if dt == "Sales Invoice" and dn == "SINV-RE-0003":
				return True
			return self.original_exists(dt, dn)

		with patch("frappe.db.exists", side_effect=mock_exists):
			res = process_edgepay_handoff(event.as_dict())
			self.assertTrue(res)

		event_status = frappe.db.get_value("EdgePay Status Handoff Event", event.name, "processing_status")
		self.assertEqual(event_status, "Delivered")

		logs = frappe.get_all("RetailEdge EdgePay Handoff Log", filters={"edgepay_event": event.name}, fields=["*"])
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].processing_status, "Processed")

	def test_redacts_secrets_from_errors_and_logs(self):
		event = self.create_handoff_event("EV-TEST-RE-004", "EP-PRQ-TEST-RE-004", source_name="SINV-RE-0004")

		def mock_exists(dt, dn=None):
			if dt == "Sales Invoice" and dn == "SINV-RE-0004":
				raise Exception("Failed connection to provider using test_consumer_api_key test_consumer_secret_key")
			return self.original_exists(dt, dn)

		with patch("frappe.db.exists", side_effect=mock_exists):
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

		def mock_exists(dt, dn=None):
			if dt == "Sales Invoice" and dn == "SINV-RE-0005":
				return True
			return self.original_exists(dt, dn)

		pe_count = frappe.db.count("Payment Entry") if frappe.db.exists("DocType", "Payment Entry") else 0
		je_count = frappe.db.count("Journal Entry") if frappe.db.exists("DocType", "Journal Entry") else 0
		gl_count = frappe.db.count("GL Entry") if frappe.db.exists("DocType", "GL Entry") else 0
		bt_count = frappe.db.count("Bank Transaction") if frappe.db.exists("DocType", "Bank Transaction") else 0

		with patch("frappe.db.exists", side_effect=mock_exists):
			process_edgepay_handoff(event.as_dict())

		self.assertEqual(frappe.db.count("Payment Entry") if frappe.db.exists("DocType", "Payment Entry") else 0, pe_count)
		self.assertEqual(frappe.db.count("Journal Entry") if frappe.db.exists("DocType", "Journal Entry") else 0, je_count)
		self.assertEqual(frappe.db.count("GL Entry") if frappe.db.exists("DocType", "GL Entry") else 0, gl_count)
		self.assertEqual(frappe.db.count("Bank Transaction") if frappe.db.exists("DocType", "Bank Transaction") else 0, bt_count)
