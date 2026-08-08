# -*- coding: utf-8 -*-

from pathlib import Path
from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.integrations.edgepay_service import (
	EdgePayServiceError,
	EdgePayServiceNotConfigured,
	_get_authorization_header,
	_normalize_response,
	get_edgepay_service_config,
	is_edgepay_service_configured,
	redact_edgepay_error,
)
from retailedge.services import edgepay_handoff_consumer as consumer


class TestEdgePayServiceAdapter(FrappeTestCase):
	def test_retailedge_has_no_edgepay_package_import(self):
		app_root = Path(__file__).resolve().parents[1]
		violations = []
		for path in app_root.rglob("*.py"):
			content = path.read_text(encoding="utf-8")
			if "from edgepayv1" in content or "import edgepayv1" in content:
				violations.append(str(path.relative_to(app_root)))
		self.assertEqual(violations, [])

	def test_service_is_not_configured_without_endpoint_and_credentials(self):
		with patch.dict(
			frappe.conf,
			{
				"edgepay_service_url": "",
				"edgepay_service_api_key": "",
				"edgepay_service_api_secret": "",
				"edgepay_service_bearer_token": "",
			},
			clear=False,
		):
			self.assertFalse(is_edgepay_service_configured())
			with self.assertRaises(EdgePayServiceNotConfigured):
				_get_authorization_header(get_edgepay_service_config())

	def test_frappe_token_auth_contract(self):
		config = {
			"api_key": "service-key",
			"api_secret": "service-secret",
			"bearer_token": "",
		}
		self.assertEqual(_get_authorization_header(config), "token service-key:service-secret")

	def test_bearer_token_takes_precedence_when_provisioned(self):
		config = {
			"api_key": "service-key",
			"api_secret": "service-secret",
			"bearer_token": "scoped-token",
		}
		self.assertEqual(_get_authorization_header(config), "Bearer scoped-token")

	def test_response_normalizes_frappe_message_envelope(self):
		response = Mock(status_code=200)
		response.json.return_value = {
			"message": {
				"ok": True,
				"status": "success",
				"data": [{"name": "EP-SHE-0001"}],
			}
		}
		result = _normalize_response(response)
		self.assertTrue(result["ok"])
		self.assertEqual(result["data"][0]["name"], "EP-SHE-0001")

	def test_remote_error_is_converted_to_adapter_error(self):
		response = Mock(status_code=503)
		response.json.return_value = {"message": "Service unavailable"}
		with self.assertRaises(EdgePayServiceError):
			_normalize_response(response)

	def test_configured_secrets_are_redacted(self):
		with patch.dict(
			frappe.conf,
			{
				"edgepay_service_url": "https://edgepay.example.com",
				"edgepay_service_api_key": "key-123",
				"edgepay_service_api_secret": "secret-456",
				"edgepay_service_bearer_token": "token-789",
			},
			clear=False,
		):
			redacted = redact_edgepay_error("key-123 secret-456 token-789")
			self.assertNotIn("key-123", redacted)
			self.assertNotIn("secret-456", redacted)
			self.assertNotIn("token-789", redacted)


class TestEdgePayHandoffConsumer(FrappeTestCase):
	def test_fetch_pending_handoffs_filters_non_retailedge_events(self):
		remote_response = {
			"ok": True,
			"data": [
				{"name": "EP-SHE-0001", "source_app": "RetailEdge"},
				{"name": "EP-SHE-0002", "source_app": "retailedge"},
				{"name": "EP-SHE-0003", "source_app": "VetEdge"},
			],
		}
		with patch.object(consumer, "get_pending_payment_handoffs", return_value=remote_response):
			events = consumer.fetch_pending_edgepay_handoffs(limit=20)
		self.assertEqual([event["name"] for event in events], ["EP-SHE-0001", "EP-SHE-0002"])

	def test_fetch_pending_handoffs_fails_closed_when_service_unavailable(self):
		with patch.object(
			consumer,
			"get_pending_payment_handoffs",
			side_effect=EdgePayServiceError("offline"),
		):
			self.assertEqual(consumer.fetch_pending_edgepay_handoffs(), [])

	def test_validate_required_fields_without_edgepay_doctypes(self):
		invalid_event = {"source_app": "RetailEdge", "source_doctype": "Sales Invoice"}
		with self.assertRaises(frappe.ValidationError):
			consumer.validate_edgepay_handoff(invalid_event)

	def test_validate_rejects_wrong_source_app(self):
		event = {
			"source_app": "VetEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-TEST-0001",
			"amount": 1000,
			"currency": "NGN",
			"request_status": "Paid",
		}
		with self.assertRaises(frappe.ValidationError):
			consumer.validate_edgepay_handoff(event)

	def test_validate_accepts_local_source_document_without_edgepay_installed(self):
		event = {
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-TEST-0001",
			"amount": 1000,
			"currency": "NGN",
			"request_status": "Paid",
		}
		with patch.object(frappe.db, "exists", return_value=True):
			consumer.validate_edgepay_handoff(event)

	def test_delivery_ack_uses_remote_service_adapter(self):
		with patch.object(
			consumer,
			"mark_payment_handoff_delivered",
			return_value={"ok": True, "status": "success"},
		) as remote_ack:
			result = consumer.mark_edgepay_handoff_delivered("EP-SHE-0001")
		remote_ack.assert_called_once_with("EP-SHE-0001")
		self.assertTrue(result["ok"])

	def test_failure_ack_redacts_before_remote_service_call(self):
		with patch.object(consumer, "redact_edgepay_error", return_value="safe-error"), patch.object(
			consumer,
			"mark_payment_handoff_failed",
			return_value={"ok": True, "status": "success"},
		) as remote_ack:
			consumer.mark_edgepay_handoff_failed("EP-SHE-0002", "unsafe-error")
		remote_ack.assert_called_once_with("EP-SHE-0002", error_message="safe-error")

	def test_pending_processor_does_not_require_edgepay_app(self):
		with patch.object(consumer, "fetch_pending_edgepay_handoffs", return_value=[]):
			self.assertEqual(consumer.process_pending_edgepay_handoffs(limit=10), 0)

	def test_consumer_source_does_not_post_accounting(self):
		source = Path(consumer.__file__).read_text(encoding="utf-8")
		for forbidden in (
			'frappe.new_doc("Payment Entry")',
			'frappe.new_doc("Journal Entry")',
			'frappe.get_doc({"doctype": "Payment Entry"',
			'frappe.get_doc({"doctype": "Journal Entry"',
		):
			self.assertNotIn(forbidden, source)
