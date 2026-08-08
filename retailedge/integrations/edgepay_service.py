from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import frappe
import requests


DEFAULT_TIMEOUT_SECONDS = 10
EDGE_PAY_API_PREFIX = "api/method/edgepayv1.edgepay.services.api."


class EdgePayServiceError(RuntimeError):
	"""Raised when the remote EdgePay service cannot satisfy a request safely."""


class EdgePayServiceNotConfigured(EdgePayServiceError):
	"""Raised when this site has no usable EdgePay service configuration."""


def get_edgepay_service_config() -> dict[str, Any]:
	"""Resolve EdgePay service settings from site_config/common_site_config.

	Secrets deliberately live outside RetailEdge business DocTypes. CoreEdge can
	later provision the same runtime values without changing the consumer API.
	"""
	base_url = str(frappe.conf.get("edgepay_service_url") or "").strip().rstrip("/")
	api_key = str(frappe.conf.get("edgepay_service_api_key") or "").strip()
	api_secret = str(frappe.conf.get("edgepay_service_api_secret") or "").strip()
	bearer_token = str(frappe.conf.get("edgepay_service_bearer_token") or "").strip()

	try:
		timeout = int(frappe.conf.get("edgepay_service_timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
	except (TypeError, ValueError):
		timeout = DEFAULT_TIMEOUT_SECONDS

	verify_ssl_value = frappe.conf.get("edgepay_service_verify_ssl")
	verify_ssl = verify_ssl_value not in (0, False, "0", "false", "False")

	return {
		"base_url": base_url,
		"api_key": api_key,
		"api_secret": api_secret,
		"bearer_token": bearer_token,
		"timeout": max(1, min(timeout, 60)),
		"verify_ssl": verify_ssl,
	}


def is_edgepay_service_configured() -> bool:
	config = get_edgepay_service_config()
	return bool(
		config["base_url"]
		and (config["bearer_token"] or (config["api_key"] and config["api_secret"]))
	)


def redact_edgepay_error(value: Any) -> str:
	"""Redact site-configured EdgePay credentials from messages before logging."""
	text = str(value or "")
	config = get_edgepay_service_config()
	for secret in (config["api_secret"], config["bearer_token"], config["api_key"]):
		if secret:
			text = text.replace(secret, "[REDACTED]")
	return text


def _get_authorization_header(config: dict[str, Any]) -> str:
	if config["bearer_token"]:
		return f"Bearer {config['bearer_token']}"
	if config["api_key"] and config["api_secret"]:
		return f"token {config['api_key']}:{config['api_secret']}"
	raise EdgePayServiceNotConfigured("EdgePay service authentication is not configured")


def _get_endpoint(method_name: str, config: dict[str, Any]) -> str:
	if not config["base_url"]:
		raise EdgePayServiceNotConfigured("EdgePay service URL is not configured")
	return urljoin(f"{config['base_url']}/", f"{EDGE_PAY_API_PREFIX}{method_name}")


def _normalize_response(response: requests.Response) -> dict[str, Any]:
	try:
		payload = response.json()
	except ValueError as exc:
		raise EdgePayServiceError(
			f"EdgePay returned an invalid response (HTTP {response.status_code})"
		) from exc

	if response.status_code < 200 or response.status_code >= 300:
		message = payload.get("message") if isinstance(payload, dict) else None
		if isinstance(message, dict):
			message = message.get("message")
		raise EdgePayServiceError(
			redact_edgepay_error(message or f"EdgePay request failed with HTTP {response.status_code}")
		)

	if isinstance(payload, dict) and isinstance(payload.get("message"), dict):
		payload = payload["message"]

	if not isinstance(payload, dict):
		raise EdgePayServiceError("EdgePay returned an unsupported response format")

	if payload.get("ok") is False or payload.get("status") == "error":
		raise EdgePayServiceError(redact_edgepay_error(payload.get("message") or "EdgePay request failed"))

	return payload


def _request(method_name: str, *, http_method: str = "POST", payload: dict[str, Any] | None = None) -> dict[str, Any]:
	config = get_edgepay_service_config()
	endpoint = _get_endpoint(method_name, config)
	headers = {
		"Accept": "application/json",
		"Authorization": _get_authorization_header(config),
	}

	try:
		response = requests.request(
			http_method,
			endpoint,
			headers=headers,
			params=payload if http_method == "GET" else None,
			data=payload if http_method != "GET" else None,
			timeout=config["timeout"],
			verify=config["verify_ssl"],
		)
	except requests.RequestException as exc:
		raise EdgePayServiceError(
			redact_edgepay_error(f"Unable to reach EdgePay service: {exc}")
		) from exc

	return _normalize_response(response)


def get_pending_payment_handoffs(*, source_app: str = "RetailEdge", limit: int = 50) -> dict[str, Any]:
	return _request(
		"get_pending_payment_handoffs",
		http_method="GET",
		payload={"source_app": source_app, "limit": max(1, min(int(limit), 500))},
	)


def mark_payment_handoff_delivered(event_name: str) -> dict[str, Any]:
	if not event_name:
		raise EdgePayServiceError("EdgePay handoff event name is required")
	return _request("mark_payment_handoff_delivered", payload={"event_name": event_name})


def mark_payment_handoff_failed(event_name: str, *, error_message: str | None = None) -> dict[str, Any]:
	if not event_name:
		raise EdgePayServiceError("EdgePay handoff event name is required")
	return _request(
		"mark_payment_handoff_failed",
		payload={
			"event_name": event_name,
			"error_message": redact_edgepay_error(error_message or ""),
		},
	)
