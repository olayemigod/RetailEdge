from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.business_control_center import _safe_early_warning
from retailedge.control_early_warning import _profitability_trend

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeR9BackendSecurityAuditTests(unittest.TestCase):
	@patch("retailedge.business_control_center.get_control_early_warning")
	def test_business_control_center_isolates_owner_permission_failure_from_legacy_action_center(self, warning_loader):
		warning_loader.side_effect = frappe.PermissionError("owner intelligence denied")
		result = _safe_early_warning(frappe._dict(company="Demo", branch="Aba", from_date="2026-08-01", to_date="2026-08-22"))
		self.assertFalse(result["available"])
		self.assertEqual(result["warnings"], [])
		self.assertTrue(result["metadata"]["permission_isolated"])

	@patch("retailedge.control_early_warning.user_has_global_branch_access", return_value=False)
	@patch("retailedge.control_early_warning.get_accounting_profitability")
	def test_restricted_blank_branch_scope_does_not_execute_company_profitability(self, accounting, _global_scope):
		result = _profitability_trend(
			frappe._dict(company="Demo", branch="", from_date="2026-08-01", to_date="2026-08-22")
		)
		self.assertFalse(result["available"])
		accounting.assert_not_called()

	def test_owner_level_r9_endpoints_use_owner_dashboard_capability(self):
		for filename in ("supplier_obligations_control.py", "budget_spend_control.py"):
			source = (APP_ROOT / filename).read_text(encoding="utf-8")
			self.assertIn("require_dashboard_action", source, filename)
			self.assertIn('DASHBOARD_KEY = "owner-dashboard"', source, filename)

	def test_business_control_file_generation_uses_stricter_owner_capability(self):
		source = (APP_ROOT / "dashboard_files.py").read_text(encoding="utf-8")
		self.assertIn('"business-control-center": lambda filters', source)
		self.assertIn('return "owner-dashboard" if scope_key == "business-control-center"', source)
		self.assertIn("_capability_scope(scope_key)", source)

	def test_business_control_center_reuses_action_center_resolved_scope_for_r9_warnings(self):
		source = (APP_ROOT / "business_control_center.py").read_text(encoding="utf-8")
		self.assertIn('warning_filters = frappe._dict(action_center.get("filters") or resolved)', source)
		self.assertIn("_safe_early_warning(warning_filters)", source)

	def test_r9_security_paths_do_not_use_permission_bypass(self):
		for filename in (
			"financial_position.py",
			"supplier_obligations_control.py",
			"budget_spend_control.py",
			"control_early_warning.py",
			"business_control_center.py",
		):
			source = (APP_ROOT / filename).read_text(encoding="utf-8")
			self.assertNotIn("ignore_permissions", source, filename)
			self.assertNotIn("frappe.db.commit", source, filename)


if __name__ == "__main__":
	unittest.main()
