from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.business_control_center import (
	_build_business_control_center,
	_safe_early_warning,
	build_business_control_export_dataset,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeBusinessControlCenterTests(unittest.TestCase):
	def test_existing_action_items_and_net_new_r9_warnings_are_combined_without_duplicate_ar_ap(self):
		action_center = {
			"filters": {"company": "Demo Co", "branch": ""},
			"summary": [],
			"items": [
				{"source": "receivables", "semantic_key": "overdue_receivables", "label": "Customer receivables are overdue", "severity": "warning", "follow_up": {"is_due": False}},
				{"source": "payables", "semantic_key": "overdue_payables", "label": "Supplier payables are overdue", "severity": "warning", "follow_up": {"is_due": False}},
			],
			"sources": {},
			"metadata": {},
		}
		warnings = {
			"warnings": [
				{"severity": "warning", "family": "Collections", "label": "Overdue customer receivables require collection attention", "value": 1000, "datatype": "Currency", "route": "/app/customer-receivables"},
				{"severity": "warning", "family": "Supplier Obligations", "label": "Overdue supplier obligations require payment attention", "value": 800, "datatype": "Currency", "route": "/app/supplier-payables"},
				{"severity": "critical", "family": "Liquidity", "label": "Cash coverage is weak", "value": 0.7, "datatype": "Float", "route": "/app/supplier-payables"},
				{"severity": "warning", "family": "Profitability", "label": "Accounting net profit declined", "value": -30, "datatype": "Percent", "route": "/app/query-report/Profit%20and%20Loss%20Statement"},
			],
			"critical_count": 1,
			"warning_count": 3,
		}

		result = _build_business_control_center(action_center=action_center, warnings=warnings)
		self.assertEqual(len(result["items"]), 4)
		self.assertEqual(result["items"][0]["family"], "Liquidity")
		self.assertEqual(sum(1 for row in result["items"] if row.get("source") == "receivables"), 1)
		self.assertEqual(sum(1 for row in result["items"] if row.get("source") == "payables"), 1)
		r9 = [row for row in result["items"] if row.get("source") == "r9_early_warning"]
		self.assertTrue(all(row["follow_up_supported"] is False for row in r9))
		profit = next(row for row in r9 if row.get("family") == "Profitability")
		self.assertEqual(profit["open_mode"], "new_tab")

	@patch("retailedge.business_control_center.get_business_control_center")
	def test_export_dataset_contains_only_permission_resolved_combined_controls(self, center_loader):
		center_loader.return_value = {
			"filters": {"company": "Demo Co", "branch": "Main"},
			"summary": {"critical": 1, "warning": 1, "total": 2},
			"items": [
				{
					"severity": "danger",
					"family": "Liquidity",
					"label": "Cash coverage is weak",
					"value": 0.7,
					"datatype": "Float",
					"time_basis": "control",
					"route": "/app/supplier-payables",
					"follow_up": {"effective_status": "Acknowledged", "assigned_to": "owner@example.com"},
				},
				{
					"severity": "warning",
					"family": "Stock",
					"label": "Negative stock requires attention",
					"value": 2,
					"datatype": "Int",
					"time_basis": "current",
					"route": "/app/stock-position",
					"follow_up": {"effective_status": "Open"},
				},
			],
		}
		dataset = build_business_control_export_dataset({"company": "Demo Co", "branch": "Main"})
		self.assertEqual(dataset["title"], "Business Control Centre")
		self.assertEqual(len(dataset["rows"]), 2)
		self.assertEqual(dataset["rows"][0]["severity"], "Critical")
		self.assertEqual(dataset["rows"][0]["follow_up_status"], "Acknowledged")
		self.assertEqual(dataset["rows"][1]["time_basis"], "Current Position")
		self.assertEqual(dataset["summary"][0]["value"], 1)
		center_loader.assert_called_once()

	@patch("retailedge.business_control_center.get_control_early_warning")
	def test_validation_failure_isolated_from_operational_action_center(self, warning_loader):
		warning_loader.side_effect = frappe.ValidationError("Too many invoices in scope")
		result = _safe_early_warning(frappe._dict(company="Demo Co", branch="Main"))
		self.assertFalse(result["available"])
		self.assertEqual(result["warnings"], [])
		self.assertTrue(result["metadata"]["failure_isolated"])
		self.assertIn("Too many invoices", result["metadata"]["reason"])

	@patch("retailedge.business_control_center.get_control_early_warning")
	def test_permission_failure_isolated_from_operational_action_center(self, warning_loader):
		warning_loader.side_effect = frappe.PermissionError("Owner intelligence denied")
		result = _safe_early_warning(frappe._dict(company="Demo Co", branch="Main"))
		self.assertFalse(result["available"])
		self.assertTrue(result["metadata"]["permission_isolated"])
		self.assertTrue(result["metadata"]["failure_isolated"])

	def test_service_preserves_existing_action_center_and_uses_shared_follow_up_store(self):
		source = (APP_ROOT / "business_control_center.py").read_text()
		self.assertIn("get_action_center_data", source)
		self.assertIn("get_control_early_warning", source)
		self.assertIn("decorate_action_items", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("save(", source)
		self.assertIn("does not create a ledger", source)
		self.assertIn("existing RetailEdge Action Follow Up store", source)
		self.assertIn("same permission-aware scope", source)
		self.assertIn("except frappe.ValidationError", source)


if __name__ == "__main__":
	unittest.main()
