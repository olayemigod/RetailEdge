from __future__ import annotations

from typing import Any

_SEVERITY_RANK = {"danger": 0, "warning": 1, "info": 2}
_FINANCIAL_KINDS = {"overdue_receivables", "overdue_payables"}


def prioritise_action_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Order decorated Action Centre items without inventing a cross-domain score."""
	result = [dict(item) for item in items]
	for item in result:
		item["priority_reason"] = _priority_reason(item)
	result.sort(key=_sort_key)
	return result


def _sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
	follow_up = item.get("follow_up") or {}
	is_due = bool(follow_up.get("is_due"))
	age_days = max(int(item.get("age_days") or 0), 0)
	kind = str(item.get("kind") or "")
	financial_exposure = float(item.get("exposure") or 0) if kind in _FINANCIAL_KINDS else 0.0
	return (
		_SEVERITY_RANK.get(str(item.get("severity") or ""), 9),
		0 if is_due else 1,
		-age_days,
		-financial_exposure,
		str(item.get("source") or ""),
		str(item.get("label") or ""),
	)


def _priority_reason(item: dict[str, Any]) -> str:
	parts: list[str] = []
	severity = str(item.get("severity") or "")
	if severity == "danger":
		parts.append("Critical exception")
	elif severity == "warning":
		parts.append("Needs attention")
	else:
		parts.append("Informational")

	follow_up = item.get("follow_up") or {}
	if follow_up.get("is_due"):
		parts.append("follow-up due or overdue")

	age_days = max(int(item.get("age_days") or 0), 0)
	if age_days:
		parts.append(f"{age_days} days old")

	kind = str(item.get("kind") or "")
	if kind in _FINANCIAL_KINDS and float(item.get("exposure") or 0) > 0:
		parts.append("financial exposure present")

	return "; ".join(parts)
