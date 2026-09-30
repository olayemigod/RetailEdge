from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _

from retailedge.utils.settings import get_retailedge_settings


Transport = Callable[[str, dict, dict, int], dict]


class CoreEdgeRemoteError(Exception):
	pass


class CoreEdgeRemoteNotConfigured(CoreEdgeRemoteError):
	pass


class CoreEdgeRemoteAuthenticationFailed(CoreEdgeRemoteError):
	pass


class CoreEdgeRemoteUnavailable(CoreEdgeRemoteError):
	pass


class CoreEdgeRemoteResponseInvalid(CoreEdgeRemoteError):
	pass


@dataclass(frozen=True)
class CoreEdgeRemoteConfig:
	base_url: str
	site_identifier: str
	api_key: str
	api_secret: str
	timeout_seconds: int = 10
	client_id: str | None = None

	@property
	def authorization_header(self) -> str:
		return f"token {self.api_key}:{self.api_secret}"


def is_remote_services_enabled() -> bool:
	settings = get_retailedge_settings()
	return bool(int(getattr(settings, "enable_coreedge_remote_services", 0) or 0))


def get_remote_service_status() -> dict:
	enabled = is_remote_services_enabled()
	settings = get_retailedge_settings()
	config = None
	configuration_valid = True
	if enabled:
		try:
			config = get_coreedge_remote_config(required=False)
		except CoreEdgeRemoteNotConfigured:
			configuration_valid = False
	return {
		"enabled": enabled,
		"configured": bool(config),
		"configuration_valid": configuration_valid,
		"quota_enabled": bool(
			enabled and int(getattr(settings, "enable_coreedge_quota_integration", 0) or 0)
		),
		"base_url": config.base_url if config else None,
		"site_identifier": config.site_identifier if config else None,
		"client_id": config.client_id if config else None,
		"credentials_present": bool(config and config.api_key and config.api_secret),
	}


def get_coreedge_remote_config(*, required: bool = True) -> CoreEdgeRemoteConfig | None:
	values = {
		"base_url": str(frappe.conf.get("coreedge_service_url") or "").strip(),
		"site_identifier": str(
			frappe.conf.get("coreedge_service_site_identifier") or ""
		).strip(),
		"api_key": str(frappe.conf.get("coreedge_service_api_key") or "").strip(),
		"api_secret": str(frappe.conf.get("coreedge_service_api_secret") or "").strip(),
		"client_id": str(frappe.conf.get("coreedge_service_client_id") or "").strip() or None,
	}

	missing = [
		label
		for fieldname, label in (
			("base_url", "coreedge_service_url"),
			("site_identifier", "coreedge_service_site_identifier"),
			("api_key", "coreedge_service_api_key"),
			("api_secret", "coreedge_service_api_secret"),
		)
		if not values[fieldname]
	]
	if missing:
		if required:
			raise CoreEdgeRemoteNotConfigured(
				"CoreEdge remote service configuration is incomplete: "
				+ ", ".join(missing)
			)
		return None

	base_url = _normalize_base_url(values["base_url"])
	timeout_seconds = _bounded_timeout(
		frappe.conf.get("coreedge_service_timeout_seconds")
	)
	return CoreEdgeRemoteConfig(
		base_url=base_url,
		site_identifier=values["site_identifier"],
		api_key=values["api_key"],
		api_secret=values["api_secret"],
		timeout_seconds=timeout_seconds,
		client_id=values["client_id"],
	)


class RemoteCoreEdgeClient:
	def __init__(
		self,
		config: CoreEdgeRemoteConfig | None = None,
		transport: Transport | None = None,
	):
		self.config = config or get_coreedge_remote_config(required=True)
		self.transport = transport or self._http_transport

	def call(self, method: str, payload: dict | None = None) -> dict:
		method = str(method or "").strip().lstrip("/")
		if not method or not method.startswith("coreedge.api.v1."):
			raise CoreEdgeRemoteNotConfigured(
				"Only versioned CoreEdge service methods may be called."
			)
		request_payload = dict(payload or {})
		request_payload["site_identifier"] = self.config.site_identifier
		url = f"{self.config.base_url}/api/method/{method}"
		headers = {
			"Accept": "application/json",
			"Content-Type": "application/json",
			"Authorization": self.config.authorization_header,
		}
		try:
			response = self.transport(
				url,
				request_payload,
				headers,
				self.config.timeout_seconds,
			)
		except CoreEdgeRemoteError:
			raise
		except Exception as exc:
			raise CoreEdgeRemoteUnavailable(
				"CoreEdge remote service is unavailable."
			) from exc

		result = _unwrap_frappe_response(response)
		self._validate_bound_client(result)
		return result

	def _validate_bound_client(self, response: dict) -> None:
		client = response.get("client")
		if client is None:
			return
		if not isinstance(client, dict):
			raise CoreEdgeRemoteResponseInvalid(
				"CoreEdge response contains an invalid client scope."
			)
		returned_site = str(client.get("site_identifier") or "").strip().lower()
		expected_site = self.config.site_identifier.strip().lower()
		if returned_site and returned_site != expected_site:
			raise CoreEdgeRemoteResponseInvalid(
				"CoreEdge response site scope does not match this RetailEdge site."
			)
		if self.config.client_id:
			returned_client = str(client.get("client_id") or "").strip()
			if returned_client and returned_client != self.config.client_id:
				raise CoreEdgeRemoteResponseInvalid(
					"CoreEdge response client identity does not match configuration."
				)

	@staticmethod
	def _http_transport(url: str, payload: dict, headers: dict, timeout: int) -> dict:
		request = urllib.request.Request(
			url,
			data=json.dumps(payload, default=str).encode("utf-8"),
			headers=headers,
			method="POST",
		)
		try:
			with urllib.request.urlopen(request, timeout=timeout) as response:
				body = response.read().decode("utf-8")
		except urllib.error.HTTPError as exc:
			if exc.code in {401, 403}:
				raise CoreEdgeRemoteAuthenticationFailed(
					"CoreEdge service authentication failed."
				) from exc
			raise CoreEdgeRemoteUnavailable(
				"CoreEdge service returned an HTTP error."
			) from exc
		except (urllib.error.URLError, TimeoutError) as exc:
			raise CoreEdgeRemoteUnavailable(
				"CoreEdge remote service is unavailable."
			) from exc

		try:
			parsed: Any = json.loads(body)
		except json.JSONDecodeError as exc:
			raise CoreEdgeRemoteResponseInvalid(
				"CoreEdge response is not valid JSON."
			) from exc
		if not isinstance(parsed, dict):
			raise CoreEdgeRemoteResponseInvalid(
				"CoreEdge response must be a JSON object."
			)
		return parsed


def _unwrap_frappe_response(response: dict) -> dict:
	if not isinstance(response, dict):
		raise CoreEdgeRemoteResponseInvalid(
			"CoreEdge response must be an object."
		)
	message = response.get("message")
	result = message if isinstance(message, dict) else response
	if not isinstance(result, dict):
		raise CoreEdgeRemoteResponseInvalid(
			"CoreEdge response payload is invalid."
		)
	data = result.get("data")
	if data is not None and not isinstance(data, dict):
		raise CoreEdgeRemoteResponseInvalid(
			"CoreEdge service response data must be an object."
		)
	return result


def _normalize_base_url(value: str) -> str:
	parsed = urllib.parse.urlsplit(value.strip())
	if parsed.scheme not in {"http", "https"} or not parsed.netloc:
		raise CoreEdgeRemoteNotConfigured(
			"coreedge_service_url must be an absolute HTTP(S) URL."
		)
	if parsed.username or parsed.password:
		raise CoreEdgeRemoteNotConfigured(
			"Do not embed CoreEdge credentials in coreedge_service_url."
		)
	host = (parsed.hostname or "").lower()
	local_http = (
		host in {"localhost", "127.0.0.1", "::1"}
		or host.endswith(".local")
	)
	if parsed.scheme != "https" and not local_http:
		raise CoreEdgeRemoteNotConfigured(
			"CoreEdge remote services require HTTPS outside local development."
		)
	path = parsed.path.rstrip("/")
	return urllib.parse.urlunsplit(
		(parsed.scheme, parsed.netloc, path, "", "")
	).rstrip("/")


def _bounded_timeout(value) -> int:
	try:
		timeout = int(value or 10)
	except (TypeError, ValueError):
		timeout = 10
	return max(2, min(timeout, 60))
