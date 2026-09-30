from __future__ import annotations

import unittest

from retailedge.integrations.coreedge_remote_usage import (
	CoreEdgeRemoteUsageAuthenticationFailed,
	CoreEdgeRemoteUsageClient,
	CoreEdgeRemoteUsageConfig,
	CoreEdgeRemoteUsageNotConfigured,
	CoreEdgeRemoteUsageResponseInvalid,
	CoreEdgeRemoteUsageUnavailable,
)


class CoreEdgeRemoteUsageClientTests(unittest.TestCase):
	def _config(self, **overrides):
		values = {
			"coreedge_remote_usage_enabled": 1,
			"coreedge_base_url": "https://coreedge.example.com",
			"coreedge_site_identifier": "retail.example.com",
			"coreedge_api_key": "api-key-123",
			"coreedge_api_secret": "secret-456",
			"coreedge_timeout_seconds": 9,
		}
		values.update(overrides)
		return CoreEdgeRemoteUsageConfig.from_mapping(values)

	def test_disabled_by_default(self):
		config = CoreEdgeRemoteUsageConfig.from_mapping({})
		self.assertFalse(config.enabled)
		self.assertFalse(config.readiness()["ready"])
		with self.assertRaises(CoreEdgeRemoteUsageNotConfigured):
			config.assert_ready()

	def test_readiness_is_secret_free(self):
		config = self._config()
		status = config.sanitized()
		self.assertTrue(status["ready"])
		self.assertTrue(status["api_key_configured"])
		self.assertTrue(status["api_secret_configured"])
		serialized = repr(status)
		self.assertNotIn("api-key-123", serialized)
		self.assertNotIn("secret-456", serialized)
		self.assertNotIn("secret-456", repr(config))

	def test_incomplete_credentials_fail_before_transport(self):
		called = []

		def transport(*args):
			called.append(args)
			return {"message": {"data": {"ok": True}}}

		client = CoreEdgeRemoteUsageClient(
			self._config(coreedge_api_secret=""),
			transport=transport,
		)
		with self.assertRaises(CoreEdgeRemoteUsageNotConfigured):
			client.get_usage_status("SALES_TRANSACTIONS")
		self.assertEqual(called, [])

	def test_status_uses_frappe_token_auth_and_bound_site_only(self):
		calls = []

		def transport(url, payload, headers, timeout):
			calls.append((url, payload, headers, timeout))
			return {
				"message": {
					"data": {
						"ok": True,
						"quota": {"allowed": True},
					}
				}
			}

		client = CoreEdgeRemoteUsageClient(self._config(), transport=transport)
		result = client.get_usage_status(
			"SALES_TRANSACTIONS",
			requested_units=1,
			request_id="status-001",
		)

		self.assertTrue(result["data"]["ok"])
		url, payload, headers, timeout = calls[0]
		self.assertTrue(url.endswith("service_entitlement_usage.get_usage_status"))
		self.assertEqual(headers["Authorization"], "token api-key-123:secret-456")
		self.assertEqual(timeout, 9)
		self.assertEqual(payload["site_identifier"], "retail.example.com")
		self.assertEqual(payload["entitlement_key"], "SALES_TRANSACTIONS")
		self.assertEqual(payload["requested_units"], 1)
		self.assertNotIn("tenant", payload)
		self.assertNotIn("product_app", payload)
		self.assertNotIn("correlation_id", payload)

	def test_reserve_forwards_business_idempotency_and_reference(self):
		calls = []

		def transport(url, payload, headers, timeout):
			calls.append((url, payload, headers, timeout))
			return {
				"message": {
					"data": {
						"ok": True,
						"status": "Reserved",
						"quota": {"reservation_reference": "CEUR-001"},
					}
				}
			}

		client = CoreEdgeRemoteUsageClient(self._config(), transport=transport)
		result = client.reserve_usage(
			"SALES_TRANSACTIONS",
			1,
			"SalesInvoice:SINV-0001:submit",
			reference_doctype="Sales Invoice",
			reference_name="SINV-0001",
			correlation_id="SINV-0001",
		)

		self.assertEqual(result["data"]["status"], "Reserved")
		url, payload, _headers, _timeout = calls[0]
		self.assertTrue(url.endswith("service_entitlement_usage.reserve_usage"))
		self.assertEqual(payload["idempotency_key"], "SalesInvoice:SINV-0001:submit")
		self.assertEqual(payload["reference_doctype"], "Sales Invoice")
		self.assertEqual(payload["reference_name"], "SINV-0001")
		self.assertEqual(payload["expires_in_seconds"], 900)
		self.assertNotIn("tenant", payload)
		self.assertNotIn("product_app", payload)

	def test_finalize_release_and_snapshot_use_exact_contract_paths(self):
		paths = []

		def transport(url, payload, headers, timeout):
			paths.append((url, payload))
			return {"message": {"data": {"ok": True}}}

		client = CoreEdgeRemoteUsageClient(self._config(), transport=transport)
		client.finalize_usage("CEUR-001", "finalize-key")
		client.release_usage("CEUR-002", "release-key", "ERPNext submit rolled back.")
		client.submit_usage_snapshot("ACTIVE_USERS", 12, "users-snapshot-2026-10-01")

		self.assertTrue(paths[0][0].endswith("service_entitlement_usage.finalize_usage"))
		self.assertTrue(paths[1][0].endswith("service_entitlement_usage.release_usage"))
		self.assertTrue(paths[2][0].endswith("service_entitlement_usage.submit_usage_snapshot"))
		self.assertEqual(paths[0][1]["reservation_reference"], "CEUR-001")
		self.assertEqual(paths[1][1]["reason"], "ERPNext submit rolled back.")
		self.assertEqual(paths[2][1]["usage_value"], 12)

	def test_transport_authentication_failure_is_preserved(self):
		def transport(*_args):
			raise CoreEdgeRemoteUsageAuthenticationFailed(
				"COREDGE_REMOTE_USAGE_AUTHENTICATION_FAILED"
			)

		client = CoreEdgeRemoteUsageClient(self._config(), transport=transport)
		with self.assertRaises(CoreEdgeRemoteUsageAuthenticationFailed):
			client.get_usage_status("SALES_TRANSACTIONS")

	def test_unknown_transport_error_becomes_unavailable(self):
		def transport(*_args):
			raise RuntimeError("network down")

		client = CoreEdgeRemoteUsageClient(self._config(), transport=transport)
		with self.assertRaises(CoreEdgeRemoteUsageUnavailable):
			client.get_usage_status("SALES_TRANSACTIONS")

	def test_non_dict_response_is_rejected(self):
		client = CoreEdgeRemoteUsageClient(
			self._config(),
			transport=lambda *_args: ["invalid"],
		)
		with self.assertRaises(CoreEdgeRemoteUsageResponseInvalid):
			client.get_usage_status("SALES_TRANSACTIONS")

	def test_response_without_service_data_contract_is_rejected(self):
		client = CoreEdgeRemoteUsageClient(
			self._config(),
			transport=lambda *_args: {"message": {"ok": True}},
		)
		with self.assertRaises(CoreEdgeRemoteUsageResponseInvalid):
			client.get_usage_status("SALES_TRANSACTIONS")

	def test_timeout_is_bounded_to_safe_default(self):
		self.assertEqual(
			self._config(coreedge_timeout_seconds=0).timeout_seconds,
			8,
		)
		self.assertEqual(
			self._config(coreedge_timeout_seconds=121).timeout_seconds,
			8,
		)
		self.assertEqual(
			self._config(coreedge_timeout_seconds=30).timeout_seconds,
			30,
		)


if __name__ == "__main__":
	unittest.main()
