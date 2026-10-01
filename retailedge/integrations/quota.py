from __future__ import annotations

import re

import frappe

from retailedge.integrations.coreedge_remote import (
	CoreEdgeRemoteNotConfigured,
	RemoteCoreEdgeClient,
	get_remote_service_status,
)


_STATUS_METHOD = "coreedge.api.v1.service_entitlement_usage.get_usage_status"
_RESERVE_METHOD = "coreedge.api.v1.service_entitlement_usage.reserve_usage"
_FINALIZE_METHOD = "coreedge.api.v1.service_entitlement_usage.finalize_usage"
_RELEASE_METHOD = "coreedge.api.v1.service_entitlement_usage.release_usage"
_SNAPSHOT_METHOD = "coreedge.api.v1.service_entitlement_usage.submit_usage_snapshot"
_SAFE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")


def is_quota_integration_enabled() -> bool:
	return bool(get_remote_service_status().get("quota_enabled"))


def require_quota_client(
	client: RemoteCoreEdgeClient | None = None,
) -> RemoteCoreEdgeClient:
	status = get_remote_service_status()
	if not status.get("enabled"):
		raise CoreEdgeRemoteNotConfigured(
			"CoreEdge remote services are disabled in RetailEdge Settings."
		)
	if not status.get("quota_enabled"):
		raise CoreEdgeRemoteNotConfigured(
			"CoreEdge quota integration is disabled in RetailEdge Settings."
		)
	if not status.get("configured"):
		raise CoreEdgeRemoteNotConfigured(
			"CoreEdge remote service credentials are not fully configured."
		)
	return client or RemoteCoreEdgeClient()


def get_usage_status(
	entitlement_key: str,
	requested_units: int = 0,
	*,
	request_id: str | None = None,
	correlation_id: str | None = None,
	client: RemoteCoreEdgeClient | None = None,
) -> dict:
	return require_quota_client(client).call(
		_STATUS_METHOD,
		{
			"entitlement_key": _entitlement_key(entitlement_key),
			"requested_units": _non_negative_int(requested_units, "Requested Units"),
			"request_id": request_id,
			"correlation_id": correlation_id,
			"source_path": "retailedge.integrations.quota.get_usage_status",
		},
	)


def reserve_usage(
	entitlement_key: str,
	units: int,
	*,
	idempotency_key: str,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	expires_in_seconds: int = 900,
	request_id: str | None = None,
	correlation_id: str | None = None,
	client: RemoteCoreEdgeClient | None = None,
) -> dict:
	return require_quota_client(client).call(
		_RESERVE_METHOD,
		{
			"entitlement_key": _entitlement_key(entitlement_key),
			"units": _positive_int(units, "Units"),
			"idempotency_key": _idempotency_key(idempotency_key),
			"expires_in_seconds": _reservation_ttl(expires_in_seconds),
			"reference_doctype": _safe_reference(reference_doctype),
			"reference_name": _safe_reference(reference_name),
			"request_id": request_id,
			"correlation_id": correlation_id,
			"source_path": "retailedge.integrations.quota.reserve_usage",
		},
	)


def finalize_usage(
	reservation_reference: str,
	*,
	idempotency_key: str,
	request_id: str | None = None,
	correlation_id: str | None = None,
	client: RemoteCoreEdgeClient | None = None,
) -> dict:
	return require_quota_client(client).call(
		_FINALIZE_METHOD,
		{
			"reservation_reference": _reservation_reference(
				reservation_reference
			),
			"idempotency_key": _idempotency_key(idempotency_key),
			"request_id": request_id,
			"correlation_id": correlation_id,
			"source_path": "retailedge.integrations.quota.finalize_usage",
		},
	)


def release_usage(
	reservation_reference: str,
	*,
	idempotency_key: str,
	reason: str,
	request_id: str | None = None,
	correlation_id: str | None = None,
	client: RemoteCoreEdgeClient | None = None,
) -> dict:
	return require_quota_client(client).call(
		_RELEASE_METHOD,
		{
			"reservation_reference": _reservation_reference(
				reservation_reference
			),
			"idempotency_key": _idempotency_key(idempotency_key),
			"reason": _release_reason(reason),
			"request_id": request_id,
			"correlation_id": correlation_id,
			"source_path": "retailedge.integrations.quota.release_usage",
		},
	)


def submit_usage_snapshot(
	entitlement_key: str,
	usage_value: int,
	*,
	idempotency_key: str,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	request_id: str | None = None,
	correlation_id: str | None = None,
	client: RemoteCoreEdgeClient | None = None,
) -> dict:
	return require_quota_client(client).call(
		_SNAPSHOT_METHOD,
		{
			"entitlement_key": _entitlement_key(entitlement_key),
			"usage_value": _non_negative_int(usage_value, "Usage Value"),
			"idempotency_key": _idempotency_key(idempotency_key),
			"reference_doctype": _safe_reference(reference_doctype),
			"reference_name": _safe_reference(reference_name),
			"request_id": request_id,
			"correlation_id": correlation_id,
			"source_path": "retailedge.integrations.quota.submit_usage_snapshot",
		},
	)


def _entitlement_key(value: str) -> str:
	resolved = str(value or "").strip()
	if not resolved or len(resolved) > 140:
		raise frappe.ValidationError(
			"CoreEdge Entitlement Key must contain between 1 and 140 characters."
		)
	return resolved


def _idempotency_key(value: str) -> str:
	resolved = str(value or "").strip()
	if not resolved or len(resolved) > 140:
		raise frappe.ValidationError(
			"CoreEdge quota idempotency key must contain between 1 and 140 characters."
		)
	if not _SAFE_KEY_PATTERN.match(resolved):
		raise frappe.ValidationError(
			"CoreEdge quota idempotency key may contain only letters, numbers, "
			"dots, underscores, colons and hyphens."
		)
	return resolved


def _positive_int(value, label: str) -> int:
	resolved = _non_negative_int(value, label)
	if resolved <= 0:
		raise frappe.ValidationError(f"{label} must be greater than zero.")
	return resolved


def _non_negative_int(value, label: str) -> int:
	try:
		resolved = int(value or 0)
	except (TypeError, ValueError) as exc:
		raise frappe.ValidationError(f"{label} must be a whole number.") from exc
	if resolved < 0:
		raise frappe.ValidationError(f"{label} cannot be negative.")
	return resolved


def _reservation_ttl(value) -> int:
	try:
		resolved = int(value or 900)
	except (TypeError, ValueError) as exc:
		raise frappe.ValidationError(
			"CoreEdge quota reservation expiry must be a whole number of seconds."
		) from exc
	if resolved < 60 or resolved > 3600:
		raise frappe.ValidationError(
			"CoreEdge quota reservation expiry must be between 60 and 3600 seconds."
		)
	return resolved


def _reservation_reference(value: str) -> str:
	resolved = str(value or "").strip()
	if not resolved or len(resolved) > 140:
		raise frappe.ValidationError(
			"CoreEdge quota reservation reference is invalid."
		)
	return resolved


def _release_reason(value: str) -> str:
	resolved = str(value or "").strip()
	if len(resolved) < 5 or len(resolved) > 500:
		raise frappe.ValidationError(
			"CoreEdge quota release reason must contain 5 to 500 characters."
		)
	return resolved


def _safe_reference(value: str | None) -> str | None:
	if value in (None, ""):
		return None
	return str(value).strip()[:140]
