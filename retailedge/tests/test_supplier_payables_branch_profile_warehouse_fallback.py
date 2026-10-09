from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge import supplier_payables_branch_fallback as fallback


def _invoice(*warehouses: str):
	return SimpleNamespace(
		company="RetailEdge Consulting",
		set_warehouse=None,
		items=[frappe._dict(warehouse=warehouse) for warehouse in warehouses],
	)


def test_branch_profile_mapping_resolves_unique_invoice_warehouse_branch():
	rows = [
		frappe._dict(
			branch="Ketu",
			default_warehouse="Stores - RC",
			default_source_warehouse=None,
			default_target_warehouse="Stores - RC",
			default_returns_warehouse=None,
		),
		frappe._dict(
			branch="Lagos Island",
			default_warehouse="Goods In Transit - RC",
			default_source_warehouse="Lagos Island - RC",
			default_target_warehouse=None,
			default_returns_warehouse=None,
		),
	]
	with (
		patch.object(fallback.frappe.db, "exists", return_value=True),
		patch.object(fallback.frappe, "get_all", return_value=rows),
	):
		assert fallback._resolve_branch_profile_from_invoice_warehouses(_invoice("Stores - RC")) == "Ketu"


def test_branch_profile_mapping_fails_closed_when_warehouse_maps_to_multiple_branches():
	rows = [
		frappe._dict(
			branch="Ketu",
			default_warehouse="Stores - RC",
			default_source_warehouse=None,
			default_target_warehouse=None,
			default_returns_warehouse=None,
		),
		frappe._dict(
			branch="Lagos Island",
			default_warehouse=None,
			default_source_warehouse="Stores - RC",
			default_target_warehouse=None,
			default_returns_warehouse=None,
		),
	]
	with (
		patch.object(fallback.frappe.db, "exists", return_value=True),
		patch.object(fallback.frappe, "get_all", return_value=rows),
	):
		assert fallback._resolve_branch_profile_from_invoice_warehouses(_invoice("Stores - RC")) == ""


def test_branch_profile_mapping_fails_closed_when_any_invoice_warehouse_is_unmapped():
	rows = [
		frappe._dict(
			branch="Ketu",
			default_warehouse="Stores - RC",
			default_source_warehouse=None,
			default_target_warehouse=None,
			default_returns_warehouse=None,
		),
	]
	with (
		patch.object(fallback.frappe.db, "exists", return_value=True),
		patch.object(fallback.frappe, "get_all", return_value=rows),
	):
		assert fallback._resolve_branch_profile_from_invoice_warehouses(
			_invoice("Stores - RC", "Unmapped - RC")
		) == ""


def test_legacy_branch_resolution_prefers_existing_transaction_attribution():
	doc = _invoice("Stores - RC")
	with (
		patch.object(fallback.frappe, "get_doc", return_value=doc),
		patch.object(fallback.frappe, "has_permission", return_value=True),
		patch.object(fallback, "resolve_transaction_branch", return_value={"branch": "Lagos Island"}),
		patch.object(fallback, "_resolve_branch_profile_from_invoice_warehouses") as profile_resolution,
	):
		assert fallback._resolve_legacy_branch("ACC-PINV-1") == "Lagos Island"
	profile_resolution.assert_not_called()


def test_legacy_branch_resolution_uses_profile_mapping_only_after_transaction_resolution_fails():
	doc = _invoice("Stores - RC")
	with (
		patch.object(fallback.frappe, "get_doc", return_value=doc),
		patch.object(fallback.frappe, "has_permission", return_value=True),
		patch.object(fallback, "resolve_transaction_branch", return_value={"branch": None}),
		patch.object(fallback, "_resolve_branch_profile_from_invoice_warehouses", return_value="Ketu"),
	):
		assert fallback._resolve_legacy_branch("ACC-PINV-1") == "Ketu"
