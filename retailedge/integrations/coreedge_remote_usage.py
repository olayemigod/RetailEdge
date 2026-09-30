from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import frappe


Transport = Callable[[str, dict, dict, int], dict]

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}
_DEFAULT_TIMEOUT_SECONDS = 8
_MAX_TIMEOUT_SECONDS = 120

_PATH_STATUS = "/api/method/coreedge.api.v1.service_entitlement_usage.get_usage_status"
_PATH_RESERVE = "/api/method/coreedge.api.v1.service_entitlement_usage.reserve_usage"
_PATH_FINALIZE = "/api/method/coreedge.api.v1.service_entitlement_usage.finalize_usage"
_PATH_RELEASE = "/api/method/coreedge.api.v1.service_entitlement_usage.release_usage"
_PATH_SNAPSHOT = "/api/method/coreedge.api.v1.service_entitlement_usage.submit_usage_snapshot"


class CoreEdgeRemoteUsageError(RuntimeError):
	pass


class CoreEdgeRemoteUsageNotConfigured(CoreEdgeRemoteUsageError):
	pass


class CoreEdgeRemoteUsageAuthenticationFailed(CoreEdgeRemoteUsageError):
	pass


class CoreEdgeRemoteUsageUnavailable(CoreEdgeRemoteUsageError):
	pass


class CoreEdgeRemoteUsageResponseInvalid(CoreEdgeRemoteUsageError):
	pass


def _parse_bool(value: Any, default: bool = False) -> bool:
	if value is None:
		return default
	if isinstance(value, bool):
		return value
	if isinstance(value, int):
		return value != 0
	text = str(value).strip().lower()
	if text in _TRUE_VALUES:
		return True
	if text in _FALSE_VALUES:
		return False
	return default


def _parse_timeout(value: Any) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		return _DEFAULT_TIMEOUT_SECONDS
	if 1 <= parsed <= _MAX_TIMEOUT_SECONDS:
		return parsed
	return _DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class CoreEdgeRemoteUsageConfig:
	enabled: bool = False
	base_url: str = ""
	site_identifier: str = ""
	api_key: str = field(default="", repr=False)
	api_secret: str = field(default="", repr=False)
	timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS

	@classmethod
	def from_mapping(
		cls,
		values: Mapping[str, Any] | None = None,
	) -> "CoreEdgeRemoteUsageConfig":
		values = values or {}
		return cls(
			enabled=_parse_bool(values.get("coreedge_remote_usage_enabled"), default=False),
			base_url=str(values.get("coreedge_base_url") or "").strip().rstrip("/"),
			site_identifier=str(values.get("coreedge_site_identifier") or "").strip().lower(),
			api_key=str(values.get("coreedge_api_key") or "").strip(),
			api_secret=str(values.get("coreedge_api_secret") or "").strip(),
			timeout_seconds=_parse_timeout(values.get("coreedge_timeout_seconds")),
		)

	def readiness(self) -> dict:
		blockers: list[str] = []
		if self.enabled:
			if not self.base_url:
				blockers.append("CoreEdge base URL is not configured.")
			if not self.site_identifier:
				blockers.append("CoreEdge site identifier is not configured.")
			if not self.api_key or not self.api_secret:
				blockers.append("CoreEdge API credentials are incomplete.")
		return {
			"enabled": self.enabled,
			"ready": self.enabled and not blockers,
			"blockers": blockers,
		}

	def sanitized(self) -> dict:
		return {
			**self.readiness(),
			"base_url_configured": bool(self.base_url),
			"site_identifier_configured": bool(self.site_identifier),
			"api_key_configured": bool(self.api_key),
			"api_secret_configured": bool(self.api_secret),
			"timeout_seconds": self.timeout_seconds,
		}

	def assert_ready(self) -> None:
		status = self.readiness()
		if not self.enabled:
			raise CoreEdgeRemoteUsageNotConfigured("COREDGE_REMOTE_USAGE_DISABLED")
		if status["blockers"]:
			raise CoreEdgeRemoteUsageNotConfigured("COREDGE_REMOTE_USAGE_NOT_CONFIGURED")


def get_remote_usage_config() -> CoreEdgeRemoteUsageConfig:
	return CoreEdgeRemoteUsageConfig.from_mapping(frappe.conf)


def get_remote_usage_readiness() -> dict:
	return get_remote_usage_config().sanitized()


def get_remote_usage_client() -> "CoreEdgeRemoteUsageClient":
	return CoreEdgeRemoteUsageClient(get_remote_usage_config())


class CoreEdgeRemoteUsageClient:
	def __init__(
		self,
		config: CoreEdgeRemoteUsageConfig | None = None,
		transport: Transport | None = None,
	):
		self.config = config or get_remote_usage_config()
		self.transport = transport or self._http_transport

	def get_usage_status(
		self,
		entitlement_key: str,
		requested_units: int = 0,
		*,
		request_id: str | None = None,
		correlation_id: str | None = None,
		source_path: str | None = None,
	) -> dict:
		return self._request(
			_PATH_STATUS,
			{
				"site_identifier": self.config.site_identifier,
				"entitlement_key": entitlement_key,
				"requested_units": requested_units,
				"request_id": request_id,
				"correlation_id": correlation_id,
				"source_path": source_path,
			},
		)

	def reserve_usage(
		self,
		entitlement_key: str,
		units: int,
		idempotency_key: str,
		*,
		expires_in_seconds: int = 900,
		reference_doctype: str | None = None,
		reference_name: str | None = None,
		request_id: str | None = None,
		correlation_id: str | None = None,
		source_path: str | None = None,
	) -> dict:
		return self._request(
			_PATH_RESERVE,
			{
				"site_identifier": self.config.site_identifier,
				"entitlement_key": entitlement_key,
				"units": units,
				"idempotency_key": idempotency_key,
				"expires_in_seconds": expires_in_seconds,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"request_id": request_id,
				"correlation_id": correlation_id,
				"source_path": source_path,
			},
		)

	def finalize_usage(
		self,
		reservation_reference: str,
		idempotency_key: str,
		*,
		request_id: str | None = None,
		correlation_id: str | None = None,
		source_path: str | None = None,
	) -> dict:
		return self._request(
			_PATH_FINALIZE,
			{
				"site_identifier": self.config.site_identifier,
				"reservation_reference": reservation_reference,
				"idempotency_key": idempotency_key,
				"request_id": request_id,
				"correlation_id": correlation_id,
				"source_path": source_path,
			},
		)

	def release_usage(
		self,
		reservation_reference: str,
		idempotency_key: str,
		reason: str,
		*,
		request_id: str | None = None,
		correlation_id: str | None = None,
		source_path: str | None = None,
	) -> dict:
		return self._request(
			_PATH_RELEASE,
			{
				"site_identifier": self.config.site_identifier,
				"reservation_reference": reservation_reference,
				"idempotency_key": idempotency_key,
				"reason": reason,
				"request_id": request_id,
				"correlation_id": correlation_id,
				"source_path": source_path,
			},
		)

	def submit_usage_snapshot(
		self,
		entitlement_key: str,
		usage_value: int,
		idempotency_key: str,
		*,
		reference_doctype: str | None = None,
		reference_name: str | None = None,
		request_id: str | None = None,
		correlation_id: str | None = None,
		source_path: str | None = None,
	) -> dict:
		return self._request(
			_PATH_SNAPSHOT,
			{
				"site_identifier": self.config.site_identifier,
				"entitlement_key": entitlement_key,
				"usage_value": usage_value,
				"idempotency_key": idempotency_key,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"request_id": request_id,
				"correlation_id": correlation_id,
				"source_path": source_path,
			},
		)

	def _request(self, path: str, payload: dict) -> dict:
		self.config.assert_ready()
		url = f"{self.config.base_url}{path}"
		headers = {
			"Accept": "application/json",
			"Content-Type": "application/json",
			"Authorization": f"token {self.config.api_key}:{self.config.api_secret}",
		}
		safe_payload = {key: value for key, value in payload.items() if value is not None}
		try:
			response = self.transport(
				url,
				safe_payload,
				headers,
				self.config.timeout_seconds,
			)
		except CoreEdgeRemoteUsageError:
			raise
		except Exception as exc:
			raise CoreEdgeRemoteUsageUnavailable("COREDGE_REMOTE_USAGE_UNAVAILABLE") from exc

		if not isinstance(response, dict):
			raise CoreEdgeRemoteUsageResponseInvalid("COREDGE_REMOTE_USAGE_RESPONSE_INVALID")
		message = response.get("message")
		result = message if isinstance(message, dict) else response
		if not isinstance(result, dict) or not isinstance(result.get("data"), dict):
			raise CoreEdgeRemoteUsageResponseInvalid("COREDGE_REMOTE_USAGE_RESPONSE_INVALID")
		return result

	@staticmethod
	def _http_transport(url: str, payload: dict, headers: dict, timeout: int) -> dict:
		request = urllib.request.Request(
			url,
			data=json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8"),
			headers=headers,
			method="POST",
		)
		try:
			with urllib.request.urlopen(request, timeout=timeout) as response:
				body = response.read().decode("utf-8")
		except urllib.error.HTTPError as exc:
			if exc.code in {401, 403}:
				raise CoreEdgeRemoteUsageAuthenticationFailed(
					"COREDGE_REMOTE_USAGE_AUTHENTICATION_FAILED"
				) from exc
			raise CoreEdgeRemoteUsageUnavailable("COREDGE_REMOTE_USAGE_UNAVAILABLE") from exc
		except (urllib.error.URLError, TimeoutError) as exc:
			raise CoreEdgeRemoteUsageUnavailable("COREDGE_REMOTE_USAGE_UNAVAILABLE") from exc

		try:
			parsed = json.loads(body)
		except json.JSONDecodeError as exc:
			raise CoreEdgeRemoteUsageResponseInvalid(
				"COREDGE_REMOTE_USAGE_RESPONSE_INVALID"
			) from exc
		if not isinstance(parsed, dict):
			raise CoreEdgeRemoteUsageResponseInvalid("COREDGE_REMOTE_USAGE_RESPONSE_INVALID")
		return parsed
