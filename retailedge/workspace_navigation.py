from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy


HIDDEN_NAVIGATION_TARGETS = frozenset(
	{
		("DocType", "RetailEdge Branch Profile User"),
	}
)


def navigation_target_key(row: Mapping | None) -> tuple[str, str] | None:
	row = row or {}
	if row.get("type") != "Link":
		return None
	link_type = str(row.get("link_type") or "").strip()
	target = str(row.get("link_to") or row.get("route") or row.get("url") or "").strip()
	if not link_type or not target:
		return None
	return link_type, target


def _section_with_count(section: Mapping, count: int) -> dict:
	row = dict(section)
	if "link_count" in row:
		row["link_count"] = count
	return row


def normalize_grouped_navigation(
	rows: Iterable[Mapping] | None,
	*,
	section_types: frozenset[str],
	hidden_targets: frozenset[tuple[str, str]] = HIDDEN_NAVIGATION_TARGETS,
) -> list[dict]:
	result: list[dict] = []
	seen_targets: set[tuple[str, str]] = set()
	pending_section: dict | None = None
	pending_rows: list[dict] = []

	def flush_section() -> None:
		nonlocal pending_section, pending_rows
		if pending_section is not None and pending_rows:
			result.append(_section_with_count(pending_section, len(pending_rows)))
			result.extend(pending_rows)
		pending_section = None
		pending_rows = []

	for source_row in rows or []:
		row = dict(source_row)
		if row.get("type") in section_types:
			flush_section()
			pending_section = row
			continue

		key = navigation_target_key(row)
		if key:
			if key in hidden_targets or key in seen_targets:
				continue
			seen_targets.add(key)

		if pending_section is not None:
			pending_rows.append(row)
		else:
			result.append(row)

	flush_section()
	return result


def normalize_workspace_data(workspace_data: Mapping | None) -> dict:
	data = deepcopy(dict(workspace_data or {}))
	data["links"] = normalize_grouped_navigation(
		data.get("links"),
		section_types=frozenset({"Card Break"}),
	)
	return data


def normalize_sidebar_data(sidebar_data: Mapping | None) -> dict:
	data = deepcopy(dict(sidebar_data or {}))
	data["items"] = normalize_grouped_navigation(
		data.get("items"),
		section_types=frozenset({"Section Break"}),
	)
	return data
