from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.project_activity import get_project_activity_context


class TestProjectActivity(unittest.TestCase):
	@patch("retailedge.project_activity.frappe.has_permission", return_value=True)
	@patch("retailedge.project_activity.frappe.get_list")
	@patch("retailedge.project_activity.frappe.db.exists", return_value=True)
	@patch("retailedge.project_activity.frappe.get_doc")
	def test_activity_uses_native_project_tasks_and_milestones(
		self,
		mock_get_doc,
		_mock_exists,
		mock_get_list,
		_mock_permission,
	):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company")
		mock_get_list.return_value = [
			frappe._dict(
				name="TASK-0001", subject="Mobilisation", status="Working", priority="High",
				progress=50, is_milestone=0, is_group=0, parent_task="",
				exp_start_date="2026-08-01", exp_end_date="2026-08-10", completed_on=None,
			),
			frappe._dict(
				name="TASK-0002", subject="Go Live", status="Open", priority="Urgent",
				progress=0, is_milestone=1, is_group=0, parent_task="",
				exp_start_date="2026-09-01", exp_end_date="2026-09-01", completed_on=None,
			),
		]

		context = get_project_activity_context("PROJ-0001", limit=20)

		self.assertTrue(context["available"])
		self.assertEqual(context["task_count"], 2)
		self.assertEqual(context["milestone_count"], 1)
		self.assertEqual(context["open_count"], 2)
		self.assertEqual(context["tasks"][1]["is_milestone"], True)
		self.assertEqual(context["source_of_truth"], "ERPNext Task")
		self.assertEqual(context["scope"], "Whole Project")
		kwargs = mock_get_list.call_args.kwargs
		self.assertEqual(kwargs["filters"], {"project": "PROJ-0001", "is_template": 0})
		self.assertEqual(kwargs["limit_page_length"], 20)

	@patch("retailedge.project_activity.frappe.has_permission")
	@patch("retailedge.project_activity.frappe.get_doc")
	def test_activity_fails_closed_without_task_read_permission(self, mock_get_doc, mock_permission):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company")
		mock_permission.side_effect = lambda doctype, ptype, doc=None: doctype == "Project"
		with patch("retailedge.project_activity.frappe.db.exists", return_value=True):
			with self.assertRaises(frappe.PermissionError):
				get_project_activity_context("PROJ-0001")

	@patch("retailedge.project_activity.frappe.has_permission", return_value=True)
	@patch("retailedge.project_activity.frappe.get_list", return_value=[])
	@patch("retailedge.project_activity.frappe.db.exists", return_value=True)
	@patch("retailedge.project_activity.frappe.get_doc")
	def test_activity_limit_is_bounded(self, mock_get_doc, _mock_exists, mock_get_list, _mock_permission):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company")
		get_project_activity_context("PROJ-0001", limit=5000)
		self.assertEqual(mock_get_list.call_args.kwargs["limit_page_length"], 500)


if __name__ == "__main__":
	unittest.main()
