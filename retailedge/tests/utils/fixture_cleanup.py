from __future__ import annotations

from collections.abc import Iterable

import frappe


def collect_fixture_names(
	doctype: str,
	*,
	prefixes: Iterable[str] = (),
	names: Iterable[str] = (),
	filters: Iterable[dict] = (),
) -> set[str]:
	"""Resolve only explicitly marked test fixtures for deterministic cleanup."""
	fixture_names = {name for name in names if name}
	for prefix in prefixes:
		if not prefix:
			continue
		fixture_names.update(
			frappe.get_all(
				doctype,
				filters={"name": ["like", f"{prefix}%"]},
				pluck="name",
				limit=0,
			)
		)
	for fixture_filters in filters:
		if not fixture_filters:
			continue
		fixture_names.update(
			frappe.get_all(
				doctype,
				filters=fixture_filters,
				pluck="name",
				limit=0,
			)
		)
	return fixture_names


def delete_fixture_records(doctype: str, names: Iterable[str]) -> None:
	"""Delete named fixtures and their child rows without touching unrelated records."""
	fixture_names = sorted({name for name in names if name})
	if not fixture_names:
		return

	for table_field in frappe.get_meta(doctype).get_table_fields():
		if table_field.options:
			frappe.db.delete(table_field.options, {"parent": ["in", fixture_names]})
	frappe.db.delete(doctype, {"name": ["in", fixture_names]})
