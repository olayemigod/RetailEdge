from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.cashier_self_service import (
	_current_shift_payload,
	_invoices_for_date,
	_normalize_activity,
	_payment_breakdown,
	_shift_outstanding,
	_resolve_work_date,
)
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
	def test_activity_query_is_hard_scoped_to_current_owner_and_selected_date(
		self,
		_exists,
		_has_field,
		get_all,
	):
		get_all.return_value = []

		_invoices_for_date(
			user="browser-cashier@example.com",
			work_date="2026-10-24",
			company="Retail Co",
			branch="Main",
		)

		filters = get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["docstatus"], 1)
		self.assertEqual(filters["owner"], "browser-cashier@example.com")
		self.assertEqual(filters["posting_date"], "2026-10-24")
		self.assertEqual(filters["company"], "Retail Co")
		self.assertEqual(filters["retailedge_branch"], "Main")
		self.assertEqual(get_all.call_args.kwargs["limit_page_length"], 0)

	@patch("retailedge.cashier_self_service.nowdate", return_value="2026-10-30")
	def test_work_date_defaults_to_today_and_rejects_future_dates(self, _nowdate):
		self.assertEqual(_resolve_work_date(""), "2026-10-30")
		self.assertEqual(_resolve_work_date("2026-10-01"), "2026-10-01")
		with self.assertRaises(frappe.ValidationError):
			_resolve_work_date("2026-10-31")


	@patch("retailedge.cashier_self_service.get_cash_custody_snapshot")
	def test_current_shift_uses_submitted_deposits_once(self, custody):
		custody.return_value = {
			"opening_cash": 10000,
			"cash_sales": 3000,
			"cashier_expenses": 1000,
			"submitted_deposits": 2000,
			"available_cash": 10000,
			"available_before_deposits": 12000,
		}
		context = {"linked_pos_opening_shift": "POSA-OS-26-0000009", "pos_profile": "POS-1"}
		first = _current_shift_payload(cashier_context=context, company="Test", user="cashier@example.com")
		second = _current_shift_payload(cashier_context=context, company="Test", user="cashier@example.com")
		for row in (first, second):
			self.assertTrue(row["open"])
			self.assertEqual(row["cash_deposits"], 2000)
			self.assertEqual(row["available_cash"], 10000)
			self.assertEqual(row["prior_expenses"], 1000)
		custody.assert_called_with(
			opening_shift="POSA-OS-26-0000009",
			company="Test",
			pos_profile="POS-1",
			cashier="cashier@example.com",
		)

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


	@patch("retailedge.cashier_self_service.frappe.get_all")
	@patch("retailedge.cashier_self_service.frappe.db.exists", return_value=True)
	def test_subsequent_payment_allocations_update_paid_and_payment_mix(self, _exists, get_all):
		invoices = [
			{"name": "SI-1", "company": "Co", "customer": "C", "debit_to": "Debtors",
			 "grand_total": 10000, "paid_amount": 5000, "outstanding_amount": 0,
			 "currency": "NGN", "party_account_currency": "NGN"},
			{"name": "SI-2", "company": "Co", "customer": "C", "debit_to": "Debtors",
			 "grand_total": 10000, "paid_amount": 5000, "outstanding_amount": 5000,
			 "currency": "NGN", "party_account_currency": "NGN"},
		]
		get_all.side_effect = [
			[{"parent": "SI-1", "mode_of_payment": "Cash", "amount": 5000, "account": "Till"},
			 {"parent": "SI-2", "mode_of_payment": "Cash", "amount": 5000, "account": "Till"}],
			[{"voucher_no": "PE-1", "against_voucher_no": "SI-1", "company": "Co",
			  "party": "C", "account": "Debtors", "amount": -5000,
			  "account_currency": "NGN", "amount_in_account_currency": -5000}],
			[{"name": "PE-1", "company": "Co", "party": "C", "mode_of_payment": "Bank"}],
		]
		total, mix, by_invoice = _payment_breakdown(invoices)
		summary, activity = _normalize_activity(invoices, by_invoice)
		self.assertEqual(total, 15000)
		self.assertEqual(dict((r["mode_of_payment"], r["amount"]) for r in mix), {"Bank": 5000, "Cash": 10000})
		self.assertEqual([r["paid_amount"] for r in activity], [10000, 5000])
		self.assertEqual(summary["outstanding_total"], 5000)
		self.assertEqual(summary["outstanding_count"], 1)
		ledger_filters = get_all.call_args_list[1].kwargs["filters"]
		self.assertEqual(ledger_filters["against_voucher_no"], ["in", ["SI-1", "SI-2"]])
		self.assertEqual(ledger_filters["voucher_type"], "Payment Entry")
		self.assertEqual(ledger_filters["delinked"], 0)
		self.assertEqual(get_all.call_args_list[2].kwargs["filters"]["docstatus"], 1)

	@patch("retailedge.cashier_self_service.frappe.get_all")
	@patch("retailedge.cashier_self_service.frappe.db.exists", return_value=True)
	def test_payment_aggregation_nets_change_without_counting_credit_notes_as_cash(self, _exists, get_all):
		invoices = [{"name": "SI-1", "company": "Co", "customer": "C", "debit_to": "Debtors",
			"grand_total": 100, "paid_amount": 120, "outstanding_amount": 0,
			"change_amount": 20, "account_for_change_amount": "Till", "currency": "NGN"}]
		get_all.side_effect = [
			[{"parent": "SI-1", "mode_of_payment": "Cash", "amount": 120, "account": "Till"}],
			[],
		]
		total, mix, by_invoice = _payment_breakdown(invoices)
		self.assertEqual(total, 100)
		self.assertEqual(by_invoice["SI-1"], 100)
		self.assertEqual(mix, [{"mode_of_payment": "Cash", "amount": 100}])

	@patch("retailedge.cashier_self_service._has_field", return_value=True)
	@patch("retailedge.cashier_self_service.frappe.get_all")
	def test_shift_outstanding_has_exact_shift_owner_company_branch_and_no_date_cap(self, get_all, _has_field):
		get_all.return_value = [
			{"name": "SI-1", "outstanding_amount": 5000},
			{"name": "SI-2", "outstanding_amount": -1000, "is_return": 1},
		]
		self.assertEqual(_shift_outstanding(user="cashier", company="Co", branch="Main", opening_shift="SHIFT-1"),
			{"outstanding_total": 5000, "outstanding_count": 1})
		filters = get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["posa_pos_opening_shift"], "SHIFT-1")
		self.assertEqual(filters["owner"], "cashier")
		self.assertEqual(filters["company"], "Co")
		self.assertEqual(filters["retailedge_branch"], "Main")
		self.assertNotIn("posting_date", filters)
		self.assertEqual(get_all.call_args.kwargs["limit_page_length"], 0)

	@patch("retailedge.navigation_consolidation.user_has_retailedge_role", return_value=True)
	def test_ready_cashier_gets_my_work_as_first_home_navigation(self, _cashier_role):
		context = {
			"readiness": {"applicable": True, "ready": True},
			"context": {},
			"navigation_groups": [
				{
					"key": "home",
					"label": "Home",
					"items": [],
				},
				{
					"key": "sales",
					"label": "Sales & POS",
					"items": [{"label": "Start POS", "target_type": "URL", "target": "/pos/"}],
				},
			],
		}

		_add_cashier_self_service_navigation(context)

		home = next(group for group in context["navigation_groups"] if group["key"] == "home")
		sales = next(group for group in context["navigation_groups"] if group["key"] == "sales")
		self.assertEqual(home["items"][0]["target"], CASHIER_MY_WORK_TARGET)
		self.assertFalse(any(item.get("target") == CASHIER_MY_WORK_TARGET for item in sales["items"]))
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

	def test_cashier_page_is_present_in_installed_app_before_frappe_getpage(self):
		"""A database Page row must never point at a missing standard Page directory.

		Switching to a RetailEdge checkout that lacks this feature while keeping
		the existing site database produces FileNotFoundError in Frappe's
		Page.load_assets() before the cashier UI is even initialized.
		"""
		from frappe.desk.desk_page import get

		folder = PAGE_JSON.parent
		for asset in ("cashier_my_work.json", "cashier_my_work.js", "cashier_my_work.py"):
			self.assertTrue((folder / asset).is_file(), asset)
		previous_user = frappe.session.user
		try:
			frappe.set_user("Administrator")
			page = frappe.get_doc("Page", "cashier-my-work")
			self.assertEqual(page.module, "RetailEdge")
			self.assertEqual(page.standard, "Yes")
			self.assertTrue(page.is_permitted())
			# Same backend path: getpage -> get -> Page.load_assets -> os.listdir.
			self.assertIsNotNone(get("cashier-my-work"))
		finally:
			frappe.set_user(previous_user)

	def test_page_contract_uses_product_brand_historical_date_and_real_empty_state(self):
		page_json = PAGE_JSON.read_text(encoding="utf-8")
		page_js = PAGE_JS.read_text(encoding="utf-8")
		component = COMPONENT.read_text(encoding="utf-8")
		business_hub = BUSINESS_HUB_PAGE_JS.read_text(encoding="utf-8")

		self.assertIn('"RetailEdgeCashier"', page_json)
		self.assertNotIn('"RetailEdge Cashier"', page_json)
		self.assertIn('cashier_my_work.bundle.js', page_js)
		self.assertIn('<EdgeAppShell', component)
		self.assertIn('template #brand', component)
		self.assertIn('productLogo', component)
		self.assertIn('EdgeInput', component)
		self.assertIn('label="Work date"', component)
		self.assertIn('shift.cash_deposits', component)
		self.assertIn('work_date: this.selectedDate', component)
		self.assertIn('No activity for this day.', component)
		self.assertIn('window.open(item.target, "_blank", "noopener,noreferrer")', component)
		self.assertIn('CASHIER_HOME = "cashier-my-work"', business_hub)


if __name__ == "__main__":
	unittest.main()
