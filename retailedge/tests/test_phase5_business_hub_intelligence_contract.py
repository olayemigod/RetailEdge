from __future__ import annotations

from pathlib import Path

from retailedge.business_hub_home import _business_indices, _prioritized_attention


ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"
PATCHES = ROOT / "patches.txt"
SETTING_PATCH = ROOT / "patches/add_business_hub_intelligence_settings.py"
DESTINATIONS = (
	ROOT / "public/js/sales_reporting/SalesReportingReport.vue",
	ROOT / "public/js/purchase_reporting/PurchaseReportingReport.vue",
	ROOT / "public/js/cash_movement/CashMovementReport.vue",
	ROOT / "public/js/expense_register/ExpenseRegisterReport.vue",
	ROOT / "public/js/customer_receivables/CustomerReceivablesReport.vue",
	ROOT / "public/js/stock_position/StockPositionReport.vue",
	ROOT / "public/js/branch_performance_dashboard/BranchPerformanceDashboard.vue",
	ROOT / "public/js/bank_matching_edgesuite_workspace.js",
)


def _section(summary):
	return {"available": True, "summary": summary, "route": ""}


def _owner():
	return {
		"available": True,
		"payload": {
			"sections": {
				"sales": _section(
					[
						{"label": "Net Invoiced", "value": 1_000_000, "datatype": "Currency"},
						{"label": "Invoices", "value": 20, "datatype": "Int"},
						{"label": "Returns", "value": 0, "datatype": "Currency"},
					]
				),
				"cash": _section(
					[
						{"label": "Net Change", "value": 300_000, "type": "Currency"},
						{"label": "Movements", "value": 18, "type": "Int"},
					]
				),
				"stock": _section(
					[
						{"label": "Stock Value", "value": 2_000_000, "datatype": "Currency"},
						{"label": "Items in Scope", "value": 30, "datatype": "Int"},
						{"label": "Negative Stock", "value": 0, "datatype": "Int"},
						{"label": "Reorder Due", "value": 2, "datatype": "Int"},
						{"label": "Out of Stock", "value": 1, "datatype": "Int"},
						{"label": "Fully Reserved", "value": 0, "datatype": "Int"},
					]
				),
				"expenses": _section(
					[
						{"label": "Total Expenses", "value": 120_000, "type": "Currency"},
						{"label": "Expense Count", "value": 7, "type": "Int"},
						{"label": "Posting Blocked", "value": 1, "type": "Int"},
						{"label": "Submitted for Review", "value": 0, "type": "Int"},
					]
				),
				"receivables": _section(
					[
						{"label": "Total Receivables", "value": 400_000, "datatype": "Currency"},
						{"label": "Open Invoices", "value": 4, "datatype": "Int"},
						{"label": "Overdue", "value": 150_000, "datatype": "Currency"},
						{"label": "Over 90 Days", "value": 0, "datatype": "Currency"},
					]
				),
				"payables": _section(
					[
						{"label": "Total Payables", "value": 250_000, "datatype": "Currency"},
						{"label": "Open Invoices", "value": 3, "datatype": "Int"},
						{"label": "Overdue", "value": 0, "datatype": "Currency"},
						{"label": "Over 90 Days", "value": 0, "datatype": "Currency"},
					]
				),
				"branches": _section(
					[
						{"label": "Gross Sales", "value": 1_050_000, "datatype": "Currency"},
						{"label": "Cash Sales", "value": 500_000, "datatype": "Currency"},
						{"label": "Audit Variance", "value": 2_000, "datatype": "Currency"},
						{"label": "Payment Issues", "value": 0, "datatype": "Int"},
					]
				),
			},
			"attention": [
				{
					"section": "profitability",
					"label": "Items are selling at negative margin",
					"metric": "Negative Margin Items",
					"value": 2,
					"datatype": "Int",
					"tone": "danger",
					"route": "/app/profitability-intelligence",
				}
			],
		},
	}


def _banking():
	return {
		"available": True,
		"payload": {
			"summary": [
				{"label": "Bank Matches Need Review", "value": 2, "datatype": "Int"},
				{"label": "Ready for Reconciliation", "value": 4, "datatype": "Int"},
				{"label": "Reconciliation Exceptions", "value": 1, "datatype": "Int"},
			]
		},
	}


def _cash_shift():
	return {
		"available": True,
		"payload": {
			"summary": [
				{"label": "Cash Variance", "value": 2_500, "datatype": "Currency"},
				{"label": "Exceptions", "value": 0, "datatype": "Int"},
			]
		},
	}


def test_phase5_exposes_all_eight_business_indices_with_scoped_routes():
	period = {"from_date": "2026-09-01", "to_date": "2026-09-14"}
	indices = _business_indices(
		_owner(),
		_banking(),
		_cash_shift(),
		company="Demo Company",
		branch="Lagos",
		period=period,
		action_settings={"variance_tolerance": 1_000},
	)

	assert [row["key"] for row in indices] == [
		"sales",
		"cash",
		"stock",
		"expenses",
		"receivables",
		"payables",
		"branch",
		"banking",
	]
	by_key = {row["key"]: row for row in indices}
	assert by_key["sales"]["route_filters"] == {
		"company": "Demo Company",
		"branch": "Lagos",
		"from_date": "2026-09-01",
		"to_date": "2026-09-14",
	}
	assert by_key["stock"]["route_filters"] == {"company": "Demo Company", "branch": "Lagos"}
	assert by_key["receivables"]["route_filters"] == {"company": "Demo Company", "branch": "Lagos"}
	assert by_key["payables"]["route_filters"] == {"company": "Demo Company", "branch": "Lagos"}


def test_phase5_variance_tolerance_controls_cash_and_branch_priority_only():
	period = {"from_date": "2026-09-01", "to_date": "2026-09-14"}
	low_tolerance = {
		row["key"]: row
		for row in _business_indices(
			_owner(),
			_banking(),
			_cash_shift(),
			company="Demo Company",
			branch="Lagos",
			period=period,
			action_settings={"variance_tolerance": 1_000},
		)
	}
	high_tolerance = {
		row["key"]: row
		for row in _business_indices(
			_owner(),
			_banking(),
			_cash_shift(),
			company="Demo Company",
			branch="Lagos",
			period=period,
			action_settings={"variance_tolerance": 5_000},
		)
	}

	assert low_tolerance["cash"]["requires_action"]
	assert low_tolerance["branch"]["requires_action"]
	assert not high_tolerance["cash"]["requires_action"]
	assert not high_tolerance["branch"]["requires_action"]
	assert high_tolerance["stock"]["requires_action"]
	assert high_tolerance["expenses"]["requires_action"]


def test_phase5_attention_is_prioritized_and_keeps_profitability_exceptions():
	period = {"from_date": "2026-09-01", "to_date": "2026-09-14"}
	owner = _owner()
	indices = _business_indices(
		owner,
		_banking(),
		_cash_shift(),
		company="Demo Company",
		branch="Lagos",
		period=period,
		action_settings={"variance_tolerance": 1_000},
	)
	items = _prioritized_attention(
		owner,
		indices,
		company="Demo Company",
		branch="Lagos",
		period=period,
	)

	assert items
	assert [item["priority"] for item in items] == sorted(item["priority"] for item in items)
	assert any(item["section"] == "profitability" for item in items)
	assert any(item["section"] == "banking" and item["tone"] == "danger" for item in items)
	assert all(item.get("action_label") for item in items)
	assert all("route_filters" in item for item in items)


def test_phase5_frontend_renders_intelligence_and_targeted_route_handoff():
	source = HUB.read_text(encoding="utf-8")
	for token in (
		"Business indices",
		"homeSnapshot.indices",
		"indexStatusLabel",
		"openHomeItem",
		"setBusinessHubRouteHandoff",
		"retailedgeConsumeBusinessHubRouteOptions",
		"route_filters",
	):
		assert token in source

	for destination in DESTINATIONS:
		text = destination.read_text(encoding="utf-8")
		assert "retailedgeConsumeBusinessHubRouteOptions" in text


def test_phase5_variance_setting_is_migration_safe_and_non_posting():
	patch = SETTING_PATCH.read_text(encoding="utf-8")
	patches = PATCHES.read_text(encoding="utf-8")
	assert "business_hub_variance_tolerance" in patch
	assert "affects prioritisation only" in patch
	assert "retailedge.patches.add_business_hub_intelligence_settings" in patches
	assert "ignore_permissions=True" not in patch
	assert "frappe.db.commit" not in patch
