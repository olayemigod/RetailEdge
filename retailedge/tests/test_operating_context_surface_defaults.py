from __future__ import annotations

from unittest.mock import patch

from retailedge import branch_performance_dashboard, daily_sales_audit_page


@patch("retailedge.branch_performance_dashboard.get_operating_context")
def test_branch_performance_uses_active_operating_company(operating_context):
	operating_context.return_value = {
		"company": "Assigned Company",
		"branch": "Assigned Branch",
	}

	assert branch_performance_dashboard._default_company() == "Assigned Company"


@patch("retailedge.daily_sales_audit_page.frappe.db.get_value", return_value="Branch Manager")
@patch("retailedge.daily_sales_audit_page.get_operating_context")
def test_daily_sales_audit_uses_active_operating_scope(operating_context, _full_name):
	operating_context.return_value = {
		"company": "Assigned Company",
		"branch": "Assigned Branch",
	}

	context = daily_sales_audit_page.get_daily_sales_audit_page_context()

	assert context["default_filters"]["company"] == "Assigned Company"
	assert context["default_filters"]["branch"] == "Assigned Branch"
