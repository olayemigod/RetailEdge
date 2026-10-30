from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.cashier_self_service import _normalize_activity, _today_invoices
from retailedge.navigation_consolidation import (
	CASHIER_MY_WORK_TARGET,
	_add_cashier_self_service_navigation,
)


APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JSON = APP_ROOT / "retailedge" / "page" / "cashier_my_work" / "cashier_my_work.json"
PAGE_JS = APP_ROOT / "retailedge" / "page" / "cashier_my_work" / "cashier_my_work.js"
COMPONENT = APP_ROOT / "public" / "js" / "cashier_my_work" / "CashierMyWork.vue"
BUSINESS_HUB_PAGE_JS = APP_ROOT / "retailedge" / "page" / "retailedge_business_hub" / "retailedge_business_hub.js"


class TestCashierMyWork(unittest.TestCase):
	@patch("retailedge.cashier_self_service.frappe.get_all")
	@patch("retailedge.cashier_self_service._has_field", return_value=True)
	@patch("retailedge.cashier_self_service.frappe.db.exists", return_value=True)
	@patch("retailedge.cashier_self_service.nowdate", return_value="2026-10-30")
	def test_today_activity_query_is_hard_scoped_to_current_owner_and_date(
		self,
		_nowdate,
		_exists,
		_has_field,
		get_all,
	):
		get_all.return_value = []

		_today_invoices(
			user="browser-cashier@example.com",
			company="Retail Co",
			branch="Main",
		)

		filters = get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["docstatus"], 1)
		self.assertEqual(filters["owner"], "browser-cashier@example.com")
		self.assertEqual(filters["posting_date"], "2026-10-30")
		self.assertEqual(filters["company"], "Retail Co")
		self.assertEqual(filters["retailedge_branch"], "Main")

	def test_activity_summary_separates_sales_and_returns(self):
		summary, activity = _normalize_activity(
			[
				{"name": "SI-1", "grand_total": 1200, "paid_amount": 1200, "status": "Paid"},
				{"name": "SI-2", "grand_total": -250, "is_return": 1, "status": "Return"},
			]
		)

		self.assertEqual(summary["sales_count"], 1)
		self.assertEqual(summary["returns_count"], 1)
		self.assertEqual(summary["gross_sales"], 1200)
		self.assertEqual(summary["returns_total"], 250)
		self.assertEqual(summary["net_sales"], 950)
		self.assertEqual([row["type"] for row in activity], ["Sale", "Return"])

	@patch("retailedge.navigation_consolidation.user_has_retailedge_role", return_value=True)
	def test_ready_cashier_gets_my_work_as_first_sales_navigation(self, _cashier_role):
		context = {
			"readiness": {"applicable": True, "ready": True},
			"context": {},
			"navigation_groups": [
				{
					"key": "sales",
					"label": "Sales & POS",
					"items": [{"label": "Start POS", "target_type": "URL", "target": "/pos/"}],
				}
			],
		}

		_add_cashier_self_service_navigation(context)

		self.assertEqual(context["navigation_groups"][0]["items"][0]["target"], CASHIER_MY_WORK_TARGET)
		self.assertEqual(context["context"]["home_experience"], "cashier")
		self.assertEqual(context["context"]["home_route"], CASHIER_MY_WORK_TARGET)

	@patch("retailedge.navigation_consolidation.user_has_retailedge_role", return_value=True)
	def test_unready_cashier_does_not_get_transaction_self_service(self, _cashier_role):
		context = {
			"readiness": {"applicable": True, "ready": False},
			"context": {},
			"navigation_groups": [],
		}

		_add_cashier_self_service_navigation(context)

		self.assertFalse(context["navigation_groups"])
		self.assertNotIn("home_route", context["context"])

	def test_page_contract_uses_edge_suite_company_logo_and_real_empty_state(self):
		page_json = PAGE_JSON.read_text(encoding="utf-8")
		page_js = PAGE_JS.read_text(encoding="utf-8")
		component = COMPONENT.read_text(encoding="utf-8")
		business_hub = BUSINESS_HUB_PAGE_JS.read_text(encoding="utf-8")

		self.assertIn('"RetailEdgeCashier"', page_json)
		self.assertIn('"RetailEdge Cashier"', page_json)
		self.assertIn('cashier_my_work.bundle.js', page_js)
		self.assertIn('<EdgeAppShell', component)
		self.assertIn('template #brand', component)
		self.assertIn('companyLogo', component)
		self.assertIn('No activity yet today.', component)
		self.assertIn('Start POS', component)
		self.assertIn('CASHIER_HOME = "cashier-my-work"', business_hub)


if __name__ == "__main__":
	unittest.main()
