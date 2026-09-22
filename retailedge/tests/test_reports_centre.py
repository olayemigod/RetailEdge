from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from retailedge.report_center import get_reports_centre_context


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "report_center.py"
MASTER = ROOT / "master_experience.py"
FRONTEND = ROOT / "public" / "js" / "reports_centre" / "ReportsCentre.vue"
BUNDLE = ROOT / "public" / "js" / "reports_centre.bundle.js"
PAGE_JSON = ROOT / "retailedge" / "page" / "reports_centre" / "reports_centre.json"
PAGE_JS = ROOT / "retailedge" / "page" / "reports_centre" / "reports_centre.js"
REPORTING_ACTIONS = ROOT / "public" / "js" / "retailedge_reporting_actions.js"


def _master_context(*, native_desk: bool):
	return {
		"access": {"can_use_native_desk": native_desk},
		"context": {
			"company": "Demo Company",
			"company_label": "Demo Company",
			"branch": "Lagos",
			"user_name": "Demo User",
		},
		"navigation_groups": [
			{
				"key": "insights",
				"label": "Insights",
				"items": [
					{
						"label": "Reports Centre",
						"target_type": "Page",
						"target": "reports-centre",
					}
				],
			}
		],
	}


@patch("retailedge.report_center._can_open_report", return_value=True)
@patch("retailedge.report_center._can_open_page", return_value=True)
@patch("retailedge.report_center.get_retailedge_business_hub_context")
def test_reports_centre_exposes_permission_filtered_catalogue(
	master,
	page_available,
	report_available,
):
	master.return_value = _master_context(native_desk=True)

	result = get_reports_centre_context()

	assert result["context"]["company"] == "Demo Company"
	assert result["context"]["branch"] == "Lagos"
	assert result["access"]["can_use_native_desk"]
	assert result["metadata"]["catalogue_only"] == 1
	assert result["metadata"]["report_count"] > 0
	assert result["metadata"]["category_count"] > 0
	keys = [group["key"] for group in result["groups"]]
	assert keys == [
		"sales",
		"purchases",
		"stock",
		"money",
		"expenses",
		"profitability",
		"controls",
		"financial",
	]
	financial = next(group for group in result["groups"] if group["key"] == "financial")
	assert any(item["target"] == "Profit and Loss Statement" for item in financial["items"])
	assert page_available.called
	assert report_available.called


@patch("retailedge.report_center._can_open_report", return_value=True)
@patch("retailedge.report_center._can_open_page", return_value=True)
@patch("retailedge.report_center.get_retailedge_business_hub_context")
def test_reports_centre_hides_native_financial_reports_from_edgesuite_only_users(
	master,
	page_available,
	report_available,
):
	master.return_value = _master_context(native_desk=False)

	result = get_reports_centre_context()

	assert not result["access"]["can_use_native_desk"]
	assert "financial" not in [group["key"] for group in result["groups"]]
	assert page_available.called
	assert not report_available.called


@patch("retailedge.report_center._can_open_report", return_value=False)
@patch("retailedge.report_center._can_open_page")
@patch("retailedge.report_center.get_retailedge_business_hub_context")
def test_reports_centre_omits_pages_user_cannot_open(
	master,
	page_available,
	report_available,
):
	master.return_value = _master_context(native_desk=False)
	page_available.side_effect = lambda target: target in {
		"sales-invoice-register",
		"stock-position",
		"cash-movement",
	}

	result = get_reports_centre_context()
	targets = {
		item["target"]
		for group in result["groups"]
		for item in group["items"]
	}

	assert targets == {"sales-invoice-register", "stock-position", "cash-movement"}
	assert report_available.call_count == 0


def test_reports_centre_uses_native_non_throwing_access_contracts():
	backend = BACKEND.read_text(encoding="utf-8")
	master = MASTER.read_text(encoding="utf-8")

	assert 'frappe.get_doc("Page", target).is_permitted()' in backend
	assert 'frappe.get_doc("Page", target).is_permitted()' in master
	assert 'doc.is_permitted()' in backend
	assert 'frappe.has_permission(doc.ref_doctype, "report")' in backend
	assert "get_report_doc" not in backend


def test_reports_centre_backend_is_catalogue_only():
	source = BACKEND.read_text(encoding="utf-8")

	for prohibited in (
		"frappe.db.sql",
		"frappe.get_list",
		"frappe.get_all",
		"ignore_permissions",
		"frappe.db.commit",
	):
		assert prohibited not in source

	for token in (
		"REPORT_GROUPS",
		"get_reports_centre_context",
		"_can_open_page",
		"_can_open_report",
		"can_use_native_desk",
	):
		assert token in source


def test_reports_centre_is_promoted_into_insights_navigation():
	source = MASTER.read_text(encoding="utf-8")

	for token in (
		"REPORTS_CENTRE_ITEM",
		'"target": "reports-centre"',
		"def _promote_reports_centre",
		'_promote_reports_centre(navigation_groups)',
		'feature_flags["reports_centre"] = "permission_filtered_catalogue"',
	):
		assert token in source


def test_reports_centre_frontend_supports_search_context_and_safe_navigation():
	source = FRONTEND.read_text(encoding="utf-8")

	for token in (
		"Reports Centre",
		"Find a report",
		"filteredGroups",
		"totalReports",
		"retailedge.report_center.get_reports_centre_context",
		"retailedgeSetReportRouteHandoff",
		"company: this.context.company",
		"branch: this.context.branch",
		"canUseNativeDesk",
		"ERPNext financial report",
		"reports-centre-grid",
		"data-edge-appearance",
	):
		assert token in source

	assert "fetch(" not in source
	assert "innerHTML" not in source


def test_reports_centre_page_and_bundle_contracts_exist():
	assert FRONTEND.exists()
	assert BUNDLE.exists()
	assert PAGE_JSON.exists()
	assert PAGE_JS.exists()

	bundle = BUNDLE.read_text(encoding="utf-8")
	page_js = PAGE_JS.read_text(encoding="utf-8")
	page_json = PAGE_JSON.read_text(encoding="utf-8")

	assert "mountReportsCentre" in bundle
	assert 'const PAGE_ROUTE = "reports-centre"' in page_js
	assert '"name": "reports-centre"' in page_json
	assert '"title": "Reports Centre"' in page_json


def test_global_reporting_actions_expose_context_handoff_for_reports_centre():
	source = REPORTING_ACTIONS.read_text(encoding="utf-8")

	for token in (
		"setReportRouteHandoff",
		"consumeReportRouteHandoff",
		"retailedgeSetReportRouteHandoff",
		"retailedgeConsumeBusinessHubRouteOptions",
		"__retailedgeBusinessHubRouteHandoff",
	):
		assert token in source
