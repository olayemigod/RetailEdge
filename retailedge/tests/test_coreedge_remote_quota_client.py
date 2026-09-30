from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.integrations.coreedge_remote import (
	CoreEdgeRemoteConfig,
	CoreEdgeRemoteNotConfigured,
	CoreEdgeRemoteResponseInvalid,
	RemoteCoreEdgeClient,
	_normalize_base_url,
	get_remote_service_status,
)
from retailedge.integrations.quota import (
	finalize_usage,
	get_usage_status,
	release_usage,
	reserve_usage,
	submit_usage_snapshot,
)


class CoreEdgeRemoteClientTests(unittest.TestCase):
	def _config(self, **overrides):
		values = {
			"base_url": "https://coreedge.example.com",
			"site_identifier": "retail.example.com",
			"api_key": "api-key-test",
			"api_secret": "api-secret-test",
			"timeout_seconds": 12,
			"client_id": "retail-client",
		}
		values.update(overrides)
		return CoreEdgeRemoteConfig(**values)

	def test_config_repr_never_contains_credentials(self):
		config_repr = repr(self._config())
		self.assertNotIn("api-key-test", config_repr)
		self.assertNotIn("api-secret-test", config_repr)

	def test_transport_uses_frappe_token_auth_and_bound_site_identifier(self):
		captured = {}

		def transport(url, payload, headers, timeout):
			captured.update(
				{
					"url": url,
					"payload": payload,
					"headers": headers,
					"timeout": timeout,
				}
			)
			return {
				"message": {
					"api_version": "v1",
					"client": {
						"client_id": "retail-client",
						"site_identifier": "retail.example.com",
					},
					"data": {"ok": True},
				}
			}

		client = RemoteCoreEdgeClient(self._config(), transport=transport)
		result = client.call(
			"coreedge.api.v1.service_entitlement_usage.get_usage_status",
			{"entitlement_key": "RETAILEDGE_SALES_TRANSACTIONS"},
		)

		self.assertTrue(result["data"]["ok"])
		self.assertEqual(
			captured["url"],
			"https://coreedge.example.com/api/method/"
			"coreedge.api.v1.service_entitlement_usage.get_usage_status",
		)
		self.assertEqual(
			captured["headers"]["Authorization"],
			"token api-key-test:api-secret-test",
		)
		self.assertEqual(
			captured["payload"]["site_identifier"],
			"retail.example.com",
		)
		self.assertEqual(captured["timeout"], 12)

	def test_caller_cannot_override_bound_site_identifier(self):
		captured = {}

		def transport(_url, payload, _headers, _timeout):
			captured.update(payload)
			return {
				"message": {
					"client": {
						"client_id": "retail-client",
						"site_identifier": "retail.example.com",
					},
					"data": {"ok": True},
				}
			}

		client = RemoteCoreEdgeClient(self._config(), transport=transport)
		client.call(
			"coreedge.api.v1.service_entitlement_usage.get_usage_status",
			{"site_identifier": "attacker.example.com"},
		)
		self.assertEqual(captured["site_identifier"], "retail.example.com")

	def test_remote_response_client_scope_mismatch_fails_closed(self):
		def transport(_url, _payload, _headers, _timeout):
			return {
				"message": {
					"client": {
						"client_id": "different-client",
						"site_identifier": "other.example.com",
					},
					"data": {"ok": True},
				}
			}

		client = RemoteCoreEdgeClient(self._config(), transport=transport)
		with self.assertRaises(CoreEdgeRemoteResponseInvalid):
			client.call(
				"coreedge.api.v1.service_entitlement_usage.get_usage_status",
				{},
			)

	def test_non_versioned_coreedge_method_is_rejected(self):
		client = RemoteCoreEdgeClient(
			self._config(),
			transport=lambda *_args: {},
		)
		with self.assertRaises(CoreEdgeRemoteNotConfigured):
			client.call("coreedge.api.legacy_method", {})

	def test_https_required_outside_local_development(self):
		with self.assertRaises(CoreEdgeRemoteNotConfigured):
			_normalize_base_url("http://coreedge.example.com")
		self.assertEqual(
			_normalize_base_url("http://coreedge.local:8000/"),
			"http://coreedge.local:8000",
		)

	def test_credentials_are_not_returned_by_remote_status(self):
		settings = SimpleNamespace(
			enable_coreedge_remote_services=1,
			enable_coreedge_quota_integration=1,
		)
		with (
			patch(
				"retailedge.integrations.coreedge_remote.get_retailedge_settings",
				return_value=settings,
			),
			patch(
				"retailedge.integrations.coreedge_remote.get_coreedge_remote_config",
				return_value=self._config(),
			),
		):
			status = get_remote_service_status()
		self.assertTrue(status["configured"])
		self.assertTrue(status["credentials_present"])
		self.assertNotIn("api_key", status)
		self.assertNotIn("api_secret", status)
		self.assertNotIn("api-key-test", str(status))
		self.assertNotIn("api-secret-test", str(status))


class CoreEdgeQuotaAdapterTests(unittest.TestCase):
	def setUp(self):
		self.calls = []
		self.client = SimpleNamespace(call=self._call)

	def _call(self, method, payload):
		self.calls.append((method, payload))
		return {
			"api_version": "v1",
			"data": {"ok": True},
		}

	def _enabled_status(self):
		return {
			"enabled": True,
			"configured": True,
			"quota_enabled": True,
			"credentials_present": True,
		}

	def test_status_uses_v1_usage_endpoint_without_tenant_or_product(self):
		with patch(
			"retailedge.integrations.quota.get_remote_service_status",
			return_value=self._enabled_status(),
		):
			get_usage_status(
				"RETAILEDGE_SALES_TRANSACTIONS",
				requested_units=1,
				client=self.client,
			)
		method, payload = self.calls[-1]
		self.assertEqual(
			method,
			"coreedge.api.v1.service_entitlement_usage.get_usage_status",
		)
		self.assertEqual(payload["requested_units"], 1)
		self.assertNotIn("tenant", payload)
		self.assertNotIn("product_app", payload)

	def test_reserve_passes_stable_business_identity_only(self):
		with patch(
			"retailedge.integrations.quota.get_remote_service_status",
			return_value=self._enabled_status(),
		):
			reserve_usage(
				"RETAILEDGE_SALES_TRANSACTIONS",
				1,
				idempotency_key="SalesInvoice:SINV-0001:submit",
				reference_doctype="Sales Invoice",
				reference_name="SINV-0001",
				client=self.client,
			)
		method, payload = self.calls[-1]
		self.assertEqual(
			method,
			"coreedge.api.v1.service_entitlement_usage.reserve_usage",
		)
		self.assertEqual(payload["units"], 1)
		self.assertEqual(
			payload["idempotency_key"],
			"SalesInvoice:SINV-0001:submit",
		)
		self.assertNotIn("tenant", payload)
		self.assertNotIn("product_app", payload)

	def test_finalize_release_and_snapshot_use_separate_operations(self):
		with patch(
			"retailedge.integrations.quota.get_remote_service_status",
			return_value=self._enabled_status(),
		):
			finalize_usage(
				"CEUR-20260930-ABC",
				idempotency_key="finalize-1",
				client=self.client,
			)
			release_usage(
				"CEUR-20260930-DEF",
				idempotency_key="release-1",
				reason="Document submission failed before commit.",
				client=self.client,
			)
			submit_usage_snapshot(
				"RETAILEDGE_USERS",
				4,
				idempotency_key="users-snapshot-1",
				client=self.client,
			)

		methods = [row[0] for row in self.calls]
		self.assertEqual(
			methods,
			[
				"coreedge.api.v1.service_entitlement_usage.finalize_usage",
				"coreedge.api.v1.service_entitlement_usage.release_usage",
				"coreedge.api.v1.service_entitlement_usage.submit_usage_snapshot",
			],
		)

	def test_invalid_quota_requests_fail_before_transport(self):
		with patch(
			"retailedge.integrations.quota.get_remote_service_status",
			return_value=self._enabled_status(),
		):
			with self.assertRaises(frappe.ValidationError):
				reserve_usage(
					"RETAILEDGE_SALES_TRANSACTIONS",
					0,
					idempotency_key="zero-units",
					client=self.client,
				)
			with self.assertRaises(frappe.ValidationError):
				reserve_usage(
					"RETAILEDGE_SALES_TRANSACTIONS",
					1,
					idempotency_key="contains spaces",
					client=self.client,
				)
			with self.assertRaises(frappe.ValidationError):
				reserve_usage(
					"RETAILEDGE_SALES_TRANSACTIONS",
					1,
					idempotency_key="ttl-too-long",
					expires_in_seconds=3601,
					client=self.client,
				)
			with self.assertRaises(frappe.ValidationError):
				submit_usage_snapshot(
					"RETAILEDGE_USERS",
					-1,
					idempotency_key="negative-snapshot",
					client=self.client,
				)
		self.assertEqual(self.calls, [])

	def test_disabled_quota_integration_fails_closed_before_transport(self):
		with patch(
			"retailedge.integrations.quota.get_remote_service_status",
			return_value={
				"enabled": True,
				"configured": True,
				"quota_enabled": False,
			},
		):
			with self.assertRaises(CoreEdgeRemoteNotConfigured):
				reserve_usage(
					"RETAILEDGE_SALES_TRANSACTIONS",
					1,
					idempotency_key="should-not-run",
					client=self.client,
				)
		self.assertEqual(self.calls, [])


class RetailEdgeQuotaIntegrationBoundaryTests(unittest.TestCase):
	def test_client_foundation_does_not_hook_sales_invoice_submission(self):
		from pathlib import Path

		import retailedge

		app_root = Path(retailedge.__file__).resolve().parent
		hooks = (app_root / "hooks.py").read_text()
		sales_event = (app_root / "events" / "sales_invoice.py").read_text()
		sales_hook_block = hooks.split('"Sales Invoice": {', 1)[1].split("},", 1)[0]
		self.assertNotIn("quota", sales_hook_block.lower())
		self.assertNotIn("integrations.quota", sales_event)
		self.assertNotIn("prepare_transaction_quota(", sales_event)
		self.assertNotIn("reserve_usage(", sales_event)
		self.assertNotIn("finalize_usage(", sales_event)

	def test_settings_schema_contains_no_remote_credentials(self):
		from pathlib import Path

		import retailedge

		settings_path = (
			Path(retailedge.__file__).resolve().parent
			/ "retailedge"
			/ "doctype"
			/ "retailedge_settings"
			/ "retailedge_settings.json"
		)
		content = settings_path.read_text().lower()
		for forbidden in (
			'"coreedge_service_api_key"',
			'"coreedge_service_api_secret"',
			'"coreedge_service_password"',
			'"coreedge_service_token"',
		):
			self.assertNotIn(forbidden, content)


class RetailEdgeSettingsRemoteCoreEdgeTests(unittest.TestCase):
	def test_quota_requires_remote_services_switch(self):
		from retailedge.retailedge.doctype.retailedge_settings.retailedge_settings import (
			RetailEdgeSettings,
		)

		doc = SimpleNamespace(
			enable_coreedge_remote_services=0,
			enable_coreedge_quota_integration=1,
		)
		with self.assertRaises(frappe.ValidationError):
			RetailEdgeSettings._validate_coreedge_remote_services(doc)

	def test_remote_guidance_does_not_request_credentials_in_doctype(self):
		from retailedge.retailedge.doctype.retailedge_settings.retailedge_settings import (
			RetailEdgeSettings,
		)

		doc = SimpleNamespace(
			enable_coreedge_remote_services=1,
			enable_coreedge_quota_integration=1,
			coreedge_remote_service_guidance=None,
		)
		RetailEdgeSettings._validate_coreedge_remote_services(doc)
		guidance = doc.coreedge_remote_service_guidance
		self.assertIn("protected site configuration", guidance)
		self.assertIn("coreedge_service_api_secret", guidance)
