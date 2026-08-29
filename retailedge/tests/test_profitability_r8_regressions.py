from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.accounting_profitability import (
	_named_total,
	_summary_value,
	build_profit_reconciliation,
	get_accounting_profitability,
)
from retailedge.profitability_leakage import _aggregate_invoice_evidence


class TestProfitabilityR8Regressions(FrappeTestCase):
	def test_duplicate_item_lines_are_one_invoice_evidence_row(self):
		rows = [
			frappe._dict(parent="SINV-1", stock_qty=1, base_net_amount=90, incoming_rate=60, base_price_list_rate=100),
			frappe._dict(parent="SINV-1", stock_qty=2, base_net_amount=180, incoming_rate=50, base_price_list_rate=100),
		]
		headers = {"SINV-1": frappe._dict(posting_date="2026-08-20", customer_name="Alpha", branch="Lagos")}
		evidence = _aggregate_invoice_evidence(rows, headers)
		self.assertEqual(len(evidence), 1)
		self.assertEqual(evidence[0]["line_count"], 2)
		self.assertEqual(evidence[0]["qty"], 3)
		self.assertEqual(evidence[0]["net_sales"], 270)
		self.assertEqual(evidence[0]["cost_of_sales"], 160)
		self.assertEqual(evidence[0]["gross_profit"], 110)
		self.assertAlmostEqual(evidence[0]["effective_discount_percent"], 10.0)

	def test_missing_cost_survives_invoice_evidence_aggregation(self):
		rows = [
			frappe._dict(parent="SINV-1", stock_qty=1, base_net_amount=100, incoming_rate=0, base_price_list_rate=100),
			frappe._dict(parent="SINV-1", stock_qty=1, base_net_amount=100, incoming_rate=70, base_price_list_rate=100),
		]
		evidence = _aggregate_invoice_evidence(rows, {"SINV-1": frappe._dict()})
		self.assertTrue(evidence[0]["missing_recorded_cost"])

	def test_branch_scope_does_not_claim_company_pl_reconciliation(self):
		accounting = get_accounting_profitability(
			frappe._dict(company="Test Company", branch="Lagos", from_date="2026-08-01", to_date="2026-08-31")
		)
		self.assertFalse(accounting["available"])
		self.assertEqual(accounting["scope"], "company")
		self.assertIn("accounting dimension", accounting["reason"])

	@patch("retailedge.accounting_profitability.frappe.has_permission", return_value=False)
	def test_company_pl_reconciliation_fails_closed_on_company_permission(self, _mock_permission):
		with self.assertRaises(frappe.PermissionError):
			get_accounting_profitability(
				frappe._dict(company="Restricted Company", branch="", from_date="2026-08-01", to_date="2026-08-31")
			)

	def test_reconciliation_keeps_erpnext_accounting_as_authoritative_comparator(self):
		reconciliation = build_profit_reconciliation(
			{"available": True, "gross_profit": 95},
			{"gross_profit": 100},
		)
		self.assertTrue(reconciliation["available"])
		self.assertEqual(reconciliation["transaction_gross_profit"], 100)
		self.assertEqual(reconciliation["accounting_gross_profit"], 95)
		self.assertEqual(reconciliation["difference"], 5)
		self.assertFalse(reconciliation["matches"])

	@patch(
		"retailedge.accounting_profitability._",
		side_effect=lambda value: {
			"Total Income": "Ingresos Totales",
			"Total Income This Year": "Ingresos Totales Este Año",
			"Gross Profit": "Beneficio Bruto",
		}.get(value, value),
	)
	def test_accounting_report_totals_match_translated_erpnext_labels(self, _mock_translate):
		self.assertEqual(
			_summary_value([{"label": "Ingresos Totales", "value": 250}], ("Total Income", "Total Income This Year")),
			250,
		)
		self.assertEqual(
			_named_total([{"account_name": "'Beneficio Bruto'", "total": 75}], "Gross Profit"),
			75,
		)
