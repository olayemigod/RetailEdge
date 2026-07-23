from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from frappe import _


EDGESUITE_METADATA_FLAG = "is_edgesuite_metadata"


def _clean(value) -> str:
	return str(value or "").strip()


def _is_enabled(value) -> bool:
	return value is True or _clean(value).lower() in {"1", "true", "yes"}


def build_filter_summary(
	filters: Mapping | None,
	field_labels: Sequence[tuple[str, str]],
	*,
	maximum_items: int = 5,
) -> str:
	filters = filters or {}
	parts: list[str] = []
	from_date = _clean(filters.get("from_date"))
	to_date = _clean(filters.get("to_date"))
	if from_date and to_date:
		parts.append(_("{0} to {1}").format(from_date, to_date))
	elif from_date:
		parts.append(_("From {0}").format(from_date))
	elif to_date:
		parts.append(_("Up to {0}").format(to_date))

	for fieldname, label in field_labels:
		if fieldname in {"from_date", "to_date"}:
			continue
		value = filters.get(fieldname)
		if value in (None, "", False, 0, "0"):
			continue
		if isinstance(value, bool) or _clean(value).lower() in {"1", "true", "yes"}:
			parts.append(_clean(label))
		else:
			parts.append(_("{0}: {1}").format(label, value))
		if len(parts) >= maximum_items:
			break

	return " · ".join(parts) or _("All permitted records")


def recommendation(title: str, description: str, severity: str = "warning") -> dict:
	return {
		"title": title,
		"description": description,
		"severity": severity,
	}


def build_report_metadata(
	*,
	title: str,
	icon: str,
	filters: Mapping | None,
	filter_fields: Sequence[tuple[str, str]],
	row_count: int,
	empty_message: str,
	empty_suggestions: Iterable[str] | None = None,
	recommendations: Iterable[dict] | None = None,
	visible_card_labels: Iterable[str] | None = None,
	status_label: str | None = None,
	status_tone: str = "neutral",
) -> dict:
	return {
		EDGESUITE_METADATA_FLAG: 1,
		"title": title,
		"icon": icon,
		"row_count": max(0, int(row_count or 0)),
		"filter_summary": build_filter_summary(filters, filter_fields),
		"visible_card_labels": list(visible_card_labels or []),
		"status": {
			"label": status_label or _("Current view"),
			"tone": status_tone or "neutral",
		},
		"recommendations": list(recommendations or []),
		"empty_state": {
			"message": empty_message,
			"suggestions": list(empty_suggestions or []),
		},
		"capabilities": {
			"supports_export": True,
			"supports_print": True,
			"supports_share": True,
		},
	}


def append_report_metadata(summary: list[dict] | None, metadata: dict) -> list[dict]:
	cards = list(summary or [])
	cards.append(metadata)
	return cards
