from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.branch_assignment import _ranges_overlap, _status_for_dates, get_active_branch_assignments


APP_ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT_JSON = (
	APP_ROOT
	/ "retailedge"
	/ "doctype"
	/ "retailedge_branch_assignment"
	/ "retailedge_branch_assignment.json"
)
ASSIGNMENT_JS = (
	APP_ROOT
	/ "retailedge"
	/ "doctype"
	/ "retailedge_branch_assignment"
	/ "retailedge_branch_assignment.js"
)
ASSIGNMENT_VUE = APP_ROOT / "public" / "js" / "branch_assignments" / "BranchAssignments.vue"


class TestBranchAssignmentHistory(unittest.TestCase):
	def test_doctype_captures_user_branch_period_and_history(self):
		definition = json.loads(ASSIGNMENT_JSON.read_text(encoding="utf-8"))
		fields = {row["fieldname"]: row for row in definition["fields"]}
		for fieldname in (
			"user",
			"company",
			"branch",
			"branch_setup",
			"branch_role",
			"effective_from",
			"effective_to",
			"status",
			"is_primary",
			"transfer_reason",
			"notes",
		):
			self.assertIn(fieldname, fields)
		self.assertEqual(fields["status"].get("read_only"), 1)
		self.assertEqual(definition.get("track_changes"), 1)
		self.assertFalse(any(permission.get("delete") for permission in definition["permissions"]))

	def test_effective_status_is_time_derived(self):
		with patch("retailedge.branch_assignment.nowdate", return_value="2026-08-27"):
			self.assertEqual(_status_for_dates(date(2026, 9, 1), None), "Planned")
			self.assertEqual(_status_for_dates(date(2026, 8, 1), None), "Active")
			self.assertEqual(_status_for_dates(date(2026, 1, 1), date(2026, 7, 31)), "Ended")

	def test_date_range_overlap_supports_transfers_and_parallel_distinct_branches(self):
		self.assertTrue(_ranges_overlap(date(2026, 1, 1), date(2026, 6, 30), date(2026, 6, 1), None))
		self.assertFalse(_ranges_overlap(date(2026, 1, 1), date(2026, 6, 30), date(2026, 7, 1), None))

	@patch("retailedge.branch_assignment._has_assignment_doctype", return_value=True)
	@patch("retailedge.branch_assignment.frappe.get_list")
	def test_active_assignment_lookup_uses_effective_dates_not_saved_status(self, mock_get_list, _mock_doctype):
		mock_get_list.return_value = [
			frappe._dict(
				name="RE-BA-1",
				user="user@example.com",
				company="Company A",
				branch="Branch B",
				branch_setup="B",
				branch_role="Sales",
				effective_from=date(2026, 7, 1),
				effective_to=None,
				is_primary=1,
			)
		]
		rows = get_active_branch_assignments(user="user@example.com", company="Company A", as_of="2026-08-27")
		self.assertEqual([row["branch"] for row in rows], ["Branch B"])
		filters = mock_get_list.call_args.kwargs["filters"]
		self.assertNotIn("status", filters)
		self.assertEqual(filters["effective_from"], ["<=", date(2026, 8, 27)])

	def test_form_company_to_branch_query_uses_branch_setup_mapping(self):
		source = ASSIGNMENT_JS.read_text(encoding="utf-8")
		self.assertIn("search_configured_company_branches", source)
		self.assertIn('company: frm.doc.company || ""', source)
		self.assertIn('frm.set_value("branch", null)', source)
		self.assertIn("Transfer to Branch", source)

	def test_transfer_service_preserves_history_and_accounting_safety(self):
		source = (APP_ROOT / "branch_assignment.py").read_text(encoding="utf-8")
		for contract in (
			"old.effective_to = add_days(effective_date, -1)",
			"new_doc = frappe.new_doc(\"RetailEdge Branch Assignment\")",
			"_assert_no_open_pos_work",
			"_validate_same_branch_overlap",
			"_validate_primary_overlap",
		):
			self.assertIn(contract, source)
		for forbidden in (
			"ignore_permissions=True",
			"frappe.db.commit",
			'frappe.new_doc("GL Entry")',
			'frappe.new_doc("Stock Ledger Entry")',
		):
			self.assertNotIn(forbidden, source)

	def test_edgesuite_history_page_is_sortable_and_has_assign_transfer_actions(self):
		source = ASSIGNMENT_VUE.read_text(encoding="utf-8")
		for contract in (
			"EdgeAppShell",
			"Branch Assignments",
			"Assign User",
			"Transfer",
			"setSort(column.key)",
			"sortDirection",
			"effective_from",
			"effective_to",
		):
			self.assertIn(contract, source)

	def test_setup_hub_exposes_branch_assignments_page(self):
		setup = (APP_ROOT / "retailedge" / "page" / "retailedge_setup" / "retailedge_setup.py").read_text(encoding="utf-8")
		setup_vue = (APP_ROOT / "public" / "js" / "retailedge_setup" / "RetailEdgeSetup.vue").read_text(encoding="utf-8")
		self.assertIn('"label": "Branch Assignments"', setup)
		self.assertIn('"page": "branch-assignments"', setup)
		self.assertIn("if (resource?.page)", setup_vue)


if __name__ == "__main__":
	unittest.main()
