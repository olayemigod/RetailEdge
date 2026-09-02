from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from retailedge.edgesuite_ui import (
	_can_open_report,
	_can_open_target,
)


class TestReportNavigationPermissionContract(unittest.TestCase):
	def test_permitted_report_requires_existence_and_native_report_gate(self):
		target_cache = {}
		permission_cache = {}
		item = {"target_type": "Report", "target": "Stock Balance"}

		with (
			patch("retailedge.edgesuite_ui._target_exists", return_value=True) as exists,
			patch("retailedge.edgesuite_ui._can_open_report", return_value=True) as can_open,
		):
			self.assertTrue(
				_can_open_target(
					item,
					target_cache=target_cache,
					permission_cache=permission_cache,
				)
			)

		exists.assert_called_once_with("Report", "Stock Balance")
		can_open.assert_called_once_with("Stock Balance")

	def test_denied_report_is_hidden(self):
		with (
			patch("retailedge.edgesuite_ui._target_exists", return_value=True),
			patch("retailedge.edgesuite_ui._can_open_report", return_value=False),
		):
			self.assertFalse(
				_can_open_target(
					{"target_type": "Report", "target": "General Ledger"},
					target_cache={},
					permission_cache={},
				)
			)

	def test_missing_report_is_rejected_before_permission_gate(self):
		with (
			patch("retailedge.edgesuite_ui._target_exists", return_value=False),
			patch("retailedge.edgesuite_ui._can_open_report") as can_open,
		):
			self.assertFalse(
				_can_open_target(
					{"target_type": "Report", "target": "Missing Report"},
					target_cache={},
					permission_cache={},
				)
			)

		can_open.assert_not_called()

	def test_repeated_report_checks_reuse_request_local_caches(self):
		target_cache = {}
		permission_cache = {}
		item = {"target_type": "Report", "target": "Trial Balance"}

		with (
			patch("retailedge.edgesuite_ui._target_exists", return_value=True) as exists,
			patch("retailedge.edgesuite_ui._can_open_report", return_value=True) as can_open,
		):
			self.assertTrue(
				_can_open_target(item, target_cache=target_cache, permission_cache=permission_cache)
			)
			self.assertTrue(
				_can_open_target(item, target_cache=target_cache, permission_cache=permission_cache)
			)

		exists.assert_called_once_with("Report", "Trial Balance")
		can_open.assert_called_once_with("Trial Balance")

	def test_doctype_and_page_navigation_paths_remain_separate(self):
		with (
			patch("retailedge.edgesuite_ui._doctype_exists_cached", return_value=True) as doctype_exists,
			patch("retailedge.edgesuite_ui._has_permission_cached", return_value=True) as has_permission,
			patch("retailedge.edgesuite_ui._target_exists_cached", return_value=True) as target_exists,
			patch("retailedge.edgesuite_ui._can_open_page_cached", return_value=True) as page_gate,
			patch("retailedge.edgesuite_ui._can_open_report_cached") as report_gate,
		):
			self.assertTrue(
				_can_open_target(
					{"target_type": "DocType", "target": "Sales Invoice"},
					target_cache={},
					permission_cache={},
				)
			)
			self.assertTrue(
				_can_open_target(
					{"target_type": "Page", "target": "stock-position"},
					target_cache={},
					permission_cache={},
				)
			)

		doctype_exists.assert_called_once()
		has_permission.assert_called_once()
		target_exists.assert_called_once_with("Page", "stock-position", {})
		page_gate.assert_called_once_with("stock-position", {})
		report_gate.assert_not_called()

	def test_native_report_gate_delegates_to_frappe_without_permission_reimplementation(self):
		source = inspect.getsource(_can_open_report)
		self.assertIn("from frappe.desk.query_report import get_report_doc", source)
		self.assertIn("get_report_doc(report_name)", source)
		for forbidden in (
			"ignore_permissions",
			"Has Role",
			"Custom Role",
			"frappe.db.set_value",
			"frappe.db.commit",
			"insert(",
			"save(",
		):
			self.assertNotIn(forbidden, source)

	def test_native_report_gate_fails_closed_on_frappe_rejection(self):
		with patch("frappe.desk.query_report.get_report_doc", side_effect=PermissionError("denied")):
			self.assertFalse(_can_open_report("Restricted Report"))


if __name__ == "__main__":
	unittest.main()
