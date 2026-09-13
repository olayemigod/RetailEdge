from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from retailedge import edgesuite_ui, master_experience


ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"
BASE = ROOT / "edgesuite_ui.py"
MASTER = ROOT / "master_experience.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _sample_registry():
	return (
		{
			"key": "sample",
			"label": "Sample",
			"items": (
				{"label": "Owned Page", "target_type": "Page", "target": "owned-page"},
				{"label": "Approved URL", "target_type": "URL", "target": "/app/approved"},
				{"label": "Native Doc", "target_type": "DocType", "target": "Customer"},
				{"label": "Native Report", "target_type": "Report", "target": "General Ledger"},
			),
		},
	)


def test_base_navigation_contains_resolved_doctype_and_report_for_edgesuite_only():
	with (
		patch.object(edgesuite_ui, "NAVIGATION_GROUPS", _sample_registry()),
		patch.object(edgesuite_ui, "_can_open_target", return_value=True),
	):
		groups = edgesuite_ui._get_permitted_navigation_groups(
			roles=set(),
			native_desk_enabled=False,
			pos_capabilities=object(),
		)
	items = groups[0]["items"]
	assert [item["target_type"] for item in items] == ["Page", "URL"]
	assert {item["label"] for item in items} == {"Owned Page", "Approved URL"}


def test_base_navigation_preserves_native_items_for_native_desk_users():
	with (
		patch.object(edgesuite_ui, "NAVIGATION_GROUPS", _sample_registry()),
		patch.object(edgesuite_ui, "_can_open_target", return_value=True),
	):
		groups = edgesuite_ui._get_permitted_navigation_groups(
			roles=set(),
			native_desk_enabled=True,
			pos_capabilities=object(),
		)
	assert {item["target_type"] for item in groups[0]["items"]} == {
		"Page",
		"URL",
		"DocType",
		"Report",
	}


def test_runtime_resolved_native_target_is_contained_after_resolution():
	registry = (
		{
			"key": "pos",
			"label": "POS",
			"items": (
				{
					"label": "POS Closing",
					"target_type": "URL",
					"target": "/placeholder",
					"runtime_target": "pos_closing",
				},
			),
		},
	)
	resolved = {
		"label": "POS Closing Shift",
		"target_type": "DocType",
		"target": "POS Closing Shift",
	}
	with (
		patch.object(edgesuite_ui, "NAVIGATION_GROUPS", registry),
		patch.object(edgesuite_ui, "_resolve_navigation_item", return_value=resolved),
		patch.object(edgesuite_ui, "_can_open_target", return_value=True),
	):
		groups = edgesuite_ui._get_permitted_navigation_groups(
			roles=set(),
			native_desk_enabled=False,
			pos_capabilities=object(),
		)
	assert groups == []


def test_final_master_composition_contains_post_filter_native_items():
	context = {
		"access": {"can_use_native_desk": False},
		"navigation_groups": [
			{
				"key": "projects",
				"items": [
					{"label": "Project Operations", "target_type": "Page", "target": "project-operations"},
					{"label": "Projects", "target_type": "DocType", "target": "Project"},
					{"label": "Project Financial Control", "target_type": "Report", "target": "RetailEdge Project Financial Control"},
				],
			},
			{
				"key": "native-only",
				"items": [{"label": "Trial Balance", "target_type": "Report", "target": "Trial Balance"}],
			},
		],
	}
	master_experience._contain_native_navigation_for_edgesuite_only(context)
	assert context["navigation_groups"] == [
		{
			"key": "projects",
			"items": [
				{"label": "Project Operations", "target_type": "Page", "target": "project-operations"}
			],
		}
	]


def test_final_master_composition_preserves_native_items_for_native_desk():
	context = {
		"access": {"can_use_native_desk": True},
		"navigation_groups": [
			{
				"key": "accounting",
				"items": [{"label": "General Ledger", "target_type": "Report", "target": "General Ledger"}],
			}
		],
	}
	before = context["navigation_groups"]
	master_experience._contain_native_navigation_for_edgesuite_only(context)
	assert context["navigation_groups"] == before


def test_master_context_runs_final_containment_after_promotions():
	source = _read(MASTER)
	call = "_contain_native_navigation_for_edgesuite_only(context)"
	assert call in source
	assert source.index(call) > source.index("_consolidate_setup_navigation(navigation_groups)")


def test_business_hub_filters_and_blocks_native_navigation_without_capability():
	source = _read(HUB)
	assert '["DocType", "Report"].includes(item.target_type)' in source
	assert '["DocType", "Report"].includes(item?.target_type)' in source
	assert "!this.nativeFallbackEnabled" in source
	assert "routeForTarget(item)" in source
	assert "openTarget(item)" in source


def test_all_business_hub_open_native_handlers_fail_closed():
	source = _read(HUB)
	methods = (
		"openNativeSalesInvoice",
		"openNativePayment",
		"openNativeCashDeposit",
		"openNativeCashTransfer",
		"openNativePurchaseInvoice",
		"openNativeCashierExpense",
		"openNativeStockTransfer",
		"openNativeStockAdjustment",
	)
	for index, method in enumerate(methods):
		start = source.index(f"\t\t{method}(")
		next_starts = [
			source.find(f"\t\t{candidate}(", start + 1)
			for candidate in methods[index + 1 :]
		]
		next_starts = [value for value in next_starts if value >= 0]
		end = min(next_starts) if next_starts else source.index("\t\tnavigateFromShell(", start)
		block = source[start:end]
		assert "if (!this.nativeFallbackEnabled) return;" in block, method


def test_containment_does_not_change_native_permission_gate():
	base = _read(BASE)
	assert "_can_open_target(resolved" in base
	assert "_can_open_report_cached" in base
	assert "_has_permission_cached" in base
	assert "ignore_permissions" not in master_experience._contain_native_navigation_for_edgesuite_only.__doc__ if master_experience._contain_native_navigation_for_edgesuite_only.__doc__ else True
