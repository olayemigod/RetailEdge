from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.supplier_scorecard_governance import (
	MAX_SCORECARD_PERIODS,
	get_supplier_scorecard_capability,
	get_supplier_scorecard_summary,
)


class TestSupplierScorecardGovernance(unittest.TestCase):
	@patch("retailedge.supplier_scorecard_governance._permission")
	def test_capability_reflects_native_permissions(self, mock_permission):
		mock_permission.side_effect = lambda doctype, ptype, name=None: (doctype, ptype) in {
			("Supplier Scorecard", "read"),
			("Supplier Scorecard", "create"),
			("Supplier Scorecard Period", "read"),
		}

		result = get_supplier_scorecard_capability()

		self.assertTrue(result["can_read_scorecard"])
		self.assertTrue(result["can_create_scorecard"])
		self.assertTrue(result["can_read_periods"])
		self.assertEqual(result["max_periods"], MAX_SCORECARD_PERIODS)

	@patch("retailedge.supplier_scorecard_governance.frappe.get_doc")
	@patch("retailedge.supplier_scorecard_governance._assert_read")
	@patch("retailedge.supplier_scorecard_governance._resolve_scope")
	@patch("retailedge.supplier_scorecard_governance._permission", return_value=False)
	def test_summary_is_denied_without_native_scorecard_read_permission(
		self,
		_mock_permission,
		mock_scope,
		_mock_supplier_read,
		mock_get_doc,
	):
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)

		with self.assertRaises(frappe.PermissionError):
			get_supplier_scorecard_summary("SUP-001", company="Demo Company", branch="Lagos")

		mock_get_doc.assert_not_called()

	@patch("retailedge.supplier_scorecard_governance.frappe.get_list")
	@patch("retailedge.supplier_scorecard_governance.frappe.db.exists", return_value=True)
	@patch("retailedge.supplier_scorecard_governance.frappe.get_doc")
	@patch("retailedge.supplier_scorecard_governance._assert_read")
	@patch("retailedge.supplier_scorecard_governance._resolve_scope")
	@patch("retailedge.supplier_scorecard_governance._permission", return_value=True)
	def test_summary_returns_native_score_standing_effective_governance_and_bounded_periods(
		self,
		_mock_permission,
		mock_scope,
		mock_supplier_read,
		mock_get_doc,
		_mock_exists,
		mock_get_list,
	):
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		supplier = SimpleNamespace(
		name="SUP-001",
		supplier_name="Supplier One",
		warn_rfqs=1,
		warn_pos=0,
		prevent_rfqs=0,
		prevent_pos=1,
	)
		scorecard = SimpleNamespace(
		name="SUP-001",
		supplier="SUP-001",
		supplier_score="82.5",
		status="Good",
		period="Per Month",
	)
		mock_get_doc.side_effect = [supplier, scorecard]
		mock_get_list.return_value = [
			{
				"name": "PU-SSP-2026-00001",
				"start_date": "2026-08-01",
				"end_date": "2026-08-31",
				"total_score": 82.5,
			}
		]

		result = get_supplier_scorecard_summary(
			"SUP-001",
			company="Demo Company",
			branch="Lagos",
		)

		mock_scope.assert_called_once_with(company="Demo Company", branch="Lagos")
		mock_supplier_read.assert_called_once_with("Supplier", "SUP-001")
		self.assertTrue(result["scorecard_exists"])
		self.assertEqual(result["scorecard"]["supplier_score"], "82.5")
		self.assertEqual(result["scorecard"]["status"], "Good")
		self.assertEqual(result["scorecard"]["period"], "Per Month")
		self.assertTrue(result["governance"]["warn_rfqs"])
		self.assertTrue(result["governance"]["prevent_pos"])
		self.assertFalse(result["governance"]["warn_pos"])
		self.assertEqual(result["period_count"], 1)
		kwargs = mock_get_list.call_args.kwargs
		self.assertEqual(kwargs["filters"], {"scorecard": "SUP-001", "docstatus": 1})
		self.assertEqual(kwargs["limit_page_length"], MAX_SCORECARD_PERIODS)
		self.assertIn("end_date desc", kwargs["order_by"])

	@patch("retailedge.supplier_scorecard_governance.frappe.get_list")
	@patch("retailedge.supplier_scorecard_governance.frappe.db.exists", return_value=False)
	@patch("retailedge.supplier_scorecard_governance.frappe.get_doc")
	@patch("retailedge.supplier_scorecard_governance._assert_read")
	@patch("retailedge.supplier_scorecard_governance._resolve_scope")
	@patch("retailedge.supplier_scorecard_governance._permission", return_value=True)
	def test_missing_scorecard_does_not_create_or_refresh_anything(
		self,
		_mock_permission,
		mock_scope,
		_mock_supplier_read,
		mock_get_doc,
		_mock_exists,
		mock_get_list,
	):
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		mock_get_doc.return_value = SimpleNamespace(
			name="SUP-001",
			supplier_name="Supplier One",
			warn_rfqs=0,
			warn_pos=0,
			prevent_rfqs=0,
			prevent_pos=0,
		)

		result = get_supplier_scorecard_summary("SUP-001", company="Demo Company", branch="Lagos")

		self.assertFalse(result["scorecard_exists"])
		self.assertIsNone(result["scorecard"])
		self.assertEqual(result["periods"], [])
		mock_get_list.assert_not_called()
		self.assertEqual(mock_get_doc.call_count, 1)

	@patch("retailedge.supplier_scorecard_governance.frappe.get_list")
	@patch("retailedge.supplier_scorecard_governance.frappe.db.exists", return_value=True)
	@patch("retailedge.supplier_scorecard_governance.frappe.get_doc")
	@patch("retailedge.supplier_scorecard_governance._assert_read")
	@patch("retailedge.supplier_scorecard_governance._resolve_scope")
	@patch("retailedge.supplier_scorecard_governance._permission")
	def test_period_history_requires_native_period_read_permission(
		self,
		mock_permission,
		mock_scope,
		_mock_supplier_read,
		mock_get_doc,
		_mock_exists,
		mock_get_list,
	):
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		mock_permission.side_effect = lambda doctype, ptype, name=None: doctype == "Supplier Scorecard"
		mock_get_doc.side_effect = [
			SimpleNamespace(
				name="SUP-001",
				supplier_name="Supplier One",
				warn_rfqs=0,
				warn_pos=0,
				prevent_rfqs=0,
				prevent_pos=0,
			),
			SimpleNamespace(
				name="SUP-001",
				supplier="SUP-001",
				supplier_score="100",
				status="Excellent",
				period="Per Month",
			),
		]

		result = get_supplier_scorecard_summary("SUP-001", company="Demo Company", branch="Lagos")

		self.assertEqual(result["periods"], [])
		mock_get_list.assert_not_called()


if __name__ == "__main__":
	unittest.main()
