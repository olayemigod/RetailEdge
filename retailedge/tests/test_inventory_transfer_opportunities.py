from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import inventory_transfer_opportunities as transfers


def _item(item_code="ITEM-1", *, serial=False, batch=False):
	return frappe._dict(
		{
			"name": item_code,
			"item_name": item_code,
			"item_group": "Products",
			"stock_uom": "Nos",
			"has_serial_no": int(serial),
			"has_batch_no": int(batch),
		}
	)


def _rule(warehouse, status, *, projected, level, reorder_qty=0, item_code="ITEM-1"):
	return {
		"item_code": item_code,
		"warehouse": warehouse,
		"warehouse_group": "",
		"evaluation_status": status,
		"projected_qty": projected,
		"reorder_level": level,
		"configured_reorder_qty": reorder_qty,
		"recommended_reorder_qty": max(reorder_qty, max(level - projected, 0)) if status == "Reorder Now" else 0,
	}


def test_allocation_never_overpromises_one_source_across_multiple_targets():
	rules = [
		_rule("SOURCE", "Healthy", projected=25, level=10, reorder_qty=5),
		_rule("TARGET-A", "Reorder Now", projected=0, level=10, reorder_qty=10),
		_rule("TARGET-B", "Reorder Now", projected=0, level=10, reorder_qty=10),
	]
	rows = transfers._allocate_transfer_opportunities(
		rules=rules,
		bin_map={
			("ITEM-1", "SOURCE"): {"available_qty": 100},
			("ITEM-1", "TARGET-A"): {"available_qty": 0},
			("ITEM-1", "TARGET-B"): {"available_qty": 0},
		},
		item_map={"ITEM-1": _item()},
		can_create_stock_entry=True,
	)

	assert sum(row["suggested_transfer_qty"] for row in rows) == 15
	assert rows[0]["suggested_transfer_qty"] == 10
	assert rows[1]["suggested_transfer_qty"] == 5


def test_source_capacity_respects_available_stock_and_its_own_reorder_level():
	rules = [
		_rule("SOURCE", "Healthy", projected=20, level=15, reorder_qty=5),
		_rule("TARGET", "Reorder Now", projected=0, level=20, reorder_qty=20),
	]
	rows = transfers._allocate_transfer_opportunities(
		rules=rules,
		bin_map={
			("ITEM-1", "SOURCE"): {"available_qty": 100},
			("ITEM-1", "TARGET"): {"available_qty": 0},
		},
		item_map={"ITEM-1": _item()},
		can_create_stock_entry=True,
	)
	assert len(rows) == 1
	assert rows[0]["suggested_transfer_qty"] == 5
	assert rows[0]["source_reorder_level"] == 15


def test_inactive_zero_rule_is_not_used_as_a_source_that_can_be_drained_to_zero():
	rules = [
		_rule("SOURCE", "Healthy", projected=50, level=0, reorder_qty=0),
		_rule("TARGET", "Reorder Now", projected=0, level=10, reorder_qty=10),
	]
	rows = transfers._allocate_transfer_opportunities(
		rules=rules,
		bin_map={
			("ITEM-1", "SOURCE"): {"available_qty": 50},
			("ITEM-1", "TARGET"): {"available_qty": 0},
		},
		item_map={"ITEM-1": _item()},
		can_create_stock_entry=True,
	)
	assert rows == []


def test_serial_or_batch_item_requires_full_stock_entry_instead_of_guided_transfer():
	rules = [
		_rule("SOURCE", "Healthy", projected=20, level=10, reorder_qty=5),
		_rule("TARGET", "Reorder Now", projected=0, level=10, reorder_qty=5),
	]
	rows = transfers._allocate_transfer_opportunities(
		rules=rules,
		bin_map={
			("ITEM-1", "SOURCE"): {"available_qty": 10},
			("ITEM-1", "TARGET"): {"available_qty": 0},
		},
		item_map={"ITEM-1": _item(serial=True)},
		can_create_stock_entry=True,
	)
	assert rows[0]["guided_transfer_available"] is False
	assert rows[0]["requires_full_stock_entry"] is True
	assert rows[0]["can_create_transfer"] is True


@patch("retailedge.inventory_transfer_opportunities._assert_report_access")
@patch("retailedge.inventory_transfer_opportunities._active_warehouse_scope")
@patch("retailedge.inventory_transfer_opportunities.get_inventory_replenishment")
@patch("retailedge.inventory_transfer_opportunities._get_available_stock")
@patch("retailedge.inventory_transfer_opportunities._get_item_transfer_metadata")
@patch("retailedge.inventory_transfer_opportunities.frappe.has_permission")
def test_public_service_composes_replenishment_and_current_bin_truth_without_mutation(
	has_permission,
	item_metadata,
	available_stock,
	replenishment,
	warehouse_scope,
	_assert_access,
):
	warehouse_scope.return_value = ["SOURCE", "TARGET"]
	replenishment.return_value = {
		"rows": [
			_rule("SOURCE", "Healthy", projected=20, level=10, reorder_qty=5),
			_rule("TARGET", "Reorder Now", projected=0, level=10, reorder_qty=5),
		]
	}
	available_stock.return_value = {
		("ITEM-1", "SOURCE"): {"available_qty": 10},
		("ITEM-1", "TARGET"): {"available_qty": 0},
	}
	item_metadata.return_value = {"ITEM-1": _item()}
	has_permission.return_value = True

	result = transfers.get_inventory_transfer_opportunities({"company": "Test Company"})

	assert result["rows"][0]["suggested_transfer_qty"] == 5
	assert result["metadata"]["creates_stock_entry"] is False
	assert result["metadata"]["same_company_only"] is True
	replenishment.assert_called_once()
	available_stock.assert_called_once()


def test_source_contract_is_bounded_permission_aware_and_read_only():
	text = Path(transfers.__file__).read_text(encoding="utf-8")
	assert "frappe.get_list" in text
	assert '"disabled": 0' in text
	assert "MAX_BIN_SCAN_ROWS + 1" in text
	assert "MAX_TRANSFER_OPPORTUNITIES" in text
	assert "get_inventory_replenishment" in text
	assert "_resolve_warehouse_scope" in text
	assert "ignore_permissions=True" not in text
	assert "frappe.get_all" not in text
	assert "frappe.db.commit" not in text
	assert ".submit(" not in text
	assert ".insert(" not in text
