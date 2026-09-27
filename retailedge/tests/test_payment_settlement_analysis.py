from __future__ import annotations

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.payment_settlement_analysis import (
	SUPPORTED_GROUP_BY,
	_add_payment,
	_finalise_bucket,
	_new_bucket,
	_normalise_group_by,
	_period_group,
)

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "payment_settlement_analysis.py"
VIEW = ROOT / "public" / "js" / "payment_settlement_analysis" / "PaymentSettlementAnalysis.vue"
BUNDLE = ROOT / "public" / "js" / "payment_settlement_analysis.bundle.js"
PAGE_JSON = ROOT / "retailedge" / "page" / "payment_settlement_analysis" / "payment_settlement_analysis.json"
PAGE_JS = ROOT / "retailedge" / "page" / "payment_settlement_analysis" / "payment_settlement_analysis.js"
REPORT_CENTER = ROOT / "report_center.py"
CAPABILITIES = ROOT / "reporting_capabilities.py"
ACTIONS = ROOT / "reporting_actions.py"
SHELL_ACTIONS = ROOT / "public" / "js" / "retailedge_reporting_actions.js"
SORTING = ROOT / "report_sorting.py"
PAYMENT_PERMISSION_PATCH = ROOT / "patches" / "ensure_retailedge_manager_payment_entry_read.py"
PATCHES = ROOT / "patches.txt"
HOOKS = ROOT / "hooks.py"


class TestPaymentSettlementAnalysis(FrappeTestCase):
	def test_supported_dimensions_exclude_cashier_and_invoice_payment_mode_inference(self):
		self.assertEqual(
			SUPPORTED_GROUP_BY,
			(
				"Day",
				"Week",
				"Month",
				"Quarter",
				"Year",
				"Mode of Payment",
				"Branch",
				"Payment Type",
				"Party Type",
				"Party",
				"Settlement Account",
			),
		)
		self.assertNotIn("Cashier", SUPPORTED_GROUP_BY)
		self.assertEqual(_normalise_group_by("mode of payment"), "Mode of Payment")
		self.assertEqual(_normalise_group_by(""), "Mode of Payment")

	def test_period_grouping_is_stable(self):
		self.assertEqual(_period_group("2026-09-22", "Day"), ("2026-09-22", "2026-09-22"))
		self.assertEqual(_period_group("2026-09-22", "Week")[0], "2026-W39")
		self.assertEqual(_period_group("2026-09-22", "Month")[0], "2026-09")
		self.assertEqual(_period_group("2026-09-22", "Quarter"), ("2026-Q3", "Q3 2026"))
		self.assertEqual(_period_group("2026-09-22", "Year"), ("2026", "2026"))

	def test_external_receipts_payments_and_internal_transfers_remain_distinct(self):
		bucket = _new_bucket("All", "All")
		_add_payment(
			bucket,
			frappe._dict(
				payment_type="Receive",
				party_type="Customer",
				base_paid_amount=100,
				base_received_amount=100,
				unallocated_amount=30,
				paid_from_account_currency="NGN",
			),
			company_currency="NGN",
		)
		_add_payment(
			bucket,
			frappe._dict(
				payment_type="Pay",
				party_type="Supplier",
				base_paid_amount=60,
				base_received_amount=60,
				unallocated_amount=0,
			),
			company_currency="NGN",
		)
		_add_payment(
			bucket,
			frappe._dict(
				payment_type="Internal Transfer",
				base_paid_amount=50,
				base_received_amount=50,
			),
			company_currency="NGN",
		)
		row = _finalise_bucket(bucket)

		self.assertEqual(row["payment_count"], 3)
		self.assertEqual(row["receive_count"], 1)
		self.assertEqual(row["pay_count"], 1)
		self.assertEqual(row["transfer_count"], 1)
		self.assertEqual(row["money_in"], 100)
		self.assertEqual(row["money_out"], 60)
		self.assertEqual(row["net_external_settlement"], 40)
		self.assertEqual(row["transfer_amount"], 50)
		self.assertEqual(row["customer_receipts_allocated"], 70)
		self.assertEqual(row["customer_advance_available"], 30)
		self.assertEqual(row["average_external_payment"], 80)

	def test_customer_advance_metrics_fail_closed_for_unknown_or_foreign_party_currency(self):
		for party_currency in ("", "USD"):
			bucket = _new_bucket(party_currency or "blank", party_currency or "blank")
			_add_payment(
				bucket,
				frappe._dict(
					payment_type="Receive",
					party_type="Customer",
					base_paid_amount=100,
					base_received_amount=100,
					unallocated_amount=50,
					paid_from_account_currency=party_currency,
				),
				company_currency="NGN",
			)
			row = _finalise_bucket(bucket)
			self.assertEqual(row["money_in"], 100)
			self.assertEqual(row["customer_receipts_allocated"], 0)
			self.assertEqual(row["customer_advance_available"], 0)
			self.assertEqual(row["multi_currency_exception_count"], 1)

	def test_backend_is_payment_entry_owned_and_does_not_infer_cashier_or_invoice_payment_mode(self):
		source = BACKEND.read_text(encoding="utf-8")
		for token in (
			'"docstatus": 1',
			'"Payment Entry"',
			"base_paid_amount",
			"base_received_amount",
			"unallocated_amount",
			"constrain_report_filters",
			"_payment_branch_field",
			'"cashier_dimension": "Not exposed; Payment Entry owner is not treated as cashier"',
			'"invoice_payment_mode_policy": "Payment Mode is not inferred from Sales Invoice"',
		):
			self.assertIn(token, source)
		for forbidden in (
			"frappe.db.sql",
			"frappe.db.commit",
			"ignore_permissions",
			'"owner"',
			"Sales Invoice.owner",
		):
			self.assertNotIn(forbidden, source)

	def test_manager_payment_entry_read_patch_is_minimal_and_registered(self):
		patch = PAYMENT_PERMISSION_PATCH.read_text(encoding="utf-8")
		patches = PATCHES.read_text(encoding="utf-8")
		for role in (
			"RetailEdgeManager",
			"RetailEdge Manager",
			"RetailEdgeBranchManager",
			"RetailEdge Branch Manager",
		):
			self.assertIn(role, patch)
		for allowed in (
			'update_permission_property(DOCTYPE, role, PERMLEVEL, "read", 1)',
			'update_permission_property(DOCTYPE, role, PERMLEVEL, "select", 1)',
			'update_permission_property(DOCTYPE, role, PERMLEVEL, "report", 1)',
		):
			self.assertIn(allowed, patch)
		for forbidden in (
			'"write", 1',
			'"create", 1',
			'"submit", 1',
			'"cancel", 1',
			'"amend", 1',
		):
			self.assertNotIn(forbidden, patch)
		self.assertIn("retailedge.patches.ensure_retailedge_manager_payment_entry_read", patches)
		hooks = HOOKS.read_text(encoding="utf-8")
		self.assertIn('"retailedge.patches.ensure_retailedge_manager_payment_entry_read.execute"', hooks)

	def test_page_provider_catalogue_and_governance_are_wired(self):
		for path in (VIEW, BUNDLE, PAGE_JSON, PAGE_JS):
			self.assertTrue(path.exists(), f"Missing Payment & Settlement Analysis artifact: {path}")

		view = VIEW.read_text(encoding="utf-8")
		bundle = BUNDLE.read_text(encoding="utf-8")
		report_center = REPORT_CENTER.read_text(encoding="utf-8")
		capabilities = CAPABILITIES.read_text(encoding="utf-8")
		actions = ACTIONS.read_text(encoding="utf-8")
		shell = SHELL_ACTIONS.read_text(encoding="utf-8")
		sorting = SORTING.read_text(encoding="utf-8")

		for token in (
			"Payment Methods",
			"Customer Receipts",
			"Supplier Payments",
			"Payments by Branch",
			"Settlement Accounts",
			"Customer Advances",
			':sort="reportSort"',
			'@sort-change="handleSortChange"',
		):
			self.assertIn(token, view)
		self.assertIn('const REPORT_KEY = "payment-settlement-analysis"', bundle)
		self.assertIn('"target": "payment-settlement-analysis"', report_center)
		self.assertIn('"payment-settlement-analysis": ReportCapabilitySpec', capabilities)
		self.assertIn('if key == "payment-settlement-analysis"', actions)
		self.assertIn('"/app/payment-settlement-analysis": "payment-settlement-analysis"', shell)
		self.assertIn('"payment-settlement-analysis": frozenset', sorting)
