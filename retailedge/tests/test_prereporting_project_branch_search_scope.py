from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import project_search


class TestPrereportingProjectBranchSearchScope(unittest.TestCase):
	def test_missing_company_returns_no_options_before_scope_or_query(self):
		with (
			patch.object(project_search.frappe, "has_permission", return_value=True),
			patch.object(project_search, "get_operational_branch_scope") as scope,
			patch.object(project_search.frappe, "get_list") as get_list,
		):
			result = project_search.search_project_branches(company="")

		self.assertEqual(result, [])
		scope.assert_not_called()
		get_list.assert_not_called()

	def test_company_permission_is_required_before_scope_resolution(self):
		def permission(doctype, *_args, **_kwargs):
			return doctype == "Branch"

		with (
			patch.object(project_search.frappe, "has_permission", side_effect=permission),
			patch.object(project_search, "get_operational_branch_scope") as scope,
		):
			with self.assertRaises(frappe.PermissionError):
				project_search.search_project_branches(company="Scope Co")

		scope.assert_not_called()

	def test_restricted_zero_scope_returns_no_options_without_branch_query(self):
		with (
			patch.object(project_search.frappe, "has_permission", return_value=True),
			patch.object(
				project_search,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": [],
					"source": "branch_assignment",
				},
			) as scope,
			patch.object(project_search.frappe, "get_list") as get_list,
			patch.object(project_search.frappe.db, "exists") as exists,
		):
			result = project_search.search_project_branches(company="Scope Co")

		self.assertEqual(result, [])
		scope.assert_called_once_with("Scope Co", user=frappe.session.user)
		get_list.assert_not_called()
		exists.assert_not_called()

	def test_restricted_scope_intersects_allowed_and_company_profile_branches(self):
		def get_list(doctype, **kwargs):
			if doctype == "RetailEdge Branch Profile":
				return ["Main", "Other"]
			self.assertEqual(doctype, "Branch")
			self.assertEqual(kwargs["filters"], {"name": ["in", ["Main"]]})
			return [frappe._dict(name="Main")]

		with (
			patch.object(project_search.frappe, "has_permission", return_value=True),
			patch.object(
				project_search,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main", "Remote"],
					"source": "branch_assignment",
				},
			),
			patch.object(project_search.frappe.db, "exists", return_value=True),
			patch.object(project_search.frappe, "get_list", side_effect=get_list),
		):
			result = project_search.search_project_branches(company="Scope Co")

		self.assertEqual([row["value"] for row in result], ["Main"])

	def test_restricted_empty_company_intersection_fails_closed(self):
		def get_list(doctype, **_kwargs):
			if doctype == "RetailEdge Branch Profile":
				return ["Other"]
			raise AssertionError("Branch query must not run for an empty intersection")

		with (
			patch.object(project_search.frappe, "has_permission", return_value=True),
			patch.object(
				project_search,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main"],
					"source": "branch_assignment",
				},
			),
			patch.object(project_search.frappe.db, "exists", return_value=True),
			patch.object(project_search.frappe, "get_list", side_effect=get_list),
		):
			result = project_search.search_project_branches(company="Scope Co")

		self.assertEqual(result, [])

	def test_restricted_scope_without_readable_profiles_uses_allowed_branches(self):
		def permission(doctype, *_args, **_kwargs):
			return doctype in {"Branch", "Company"}

		with (
			patch.object(project_search.frappe, "has_permission", side_effect=permission),
			patch.object(
				project_search,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main", "Remote"],
					"source": "legacy_branch_restriction",
				},
			),
			patch.object(project_search.frappe.db, "exists", return_value=True),
			patch.object(
				project_search.frappe,
				"get_list",
				return_value=[frappe._dict(name="Main"), frappe._dict(name="Remote")],
			) as get_list,
		):
			result = project_search.search_project_branches(company="Scope Co")

		self.assertEqual([row["value"] for row in result], ["Main", "Remote"])
		get_list.assert_called_once()
		self.assertEqual(get_list.call_args.kwargs["filters"], {"name": ["in", ["Main", "Remote"]]})

	def test_unrestricted_legacy_scope_preserves_permission_aware_branch_search(self):
		with (
			patch.object(project_search.frappe, "has_permission", return_value=True),
			patch.object(
				project_search,
				"get_operational_branch_scope",
				return_value={
					"restricted": False,
					"allowed_branches": [],
					"source": "unrestricted_legacy",
				},
			),
			patch.object(project_search.frappe.db, "exists", return_value=False),
			patch.object(
				project_search.frappe,
				"get_list",
				return_value=[frappe._dict(name="Main")],
			) as get_list,
		):
			result = project_search.search_project_branches(
				txt="Ma",
				company="Scope Co",
				limit=200,
			)

		self.assertEqual([row["value"] for row in result], ["Main"])
		self.assertEqual(get_list.call_args.kwargs["filters"], {"name": ["like", "%Ma%"]})
		self.assertEqual(get_list.call_args.kwargs["limit_page_length"], project_search.MAX_RESULTS)

	def test_source_contract_uses_explicit_scope_and_bounded_permission_aware_reads(self):
		source = inspect.getsource(project_search.search_project_branches)
		self.assertIn("get_operational_branch_scope", source)
		self.assertIn('frappe.has_permission("Company", "read", doc=company)', source)
		self.assertIn("frappe.get_list", source)
		self.assertIn("MAX_RESULTS", source)
		self.assertNotIn("get_user_allowed_branches", source)
		self.assertNotIn("user_has_global_branch_access", source)
		self.assertNotIn("frappe.get_all", source)
		self.assertNotIn("ignore_permissions", source)

	def test_project_search_and_project_operations_composition_are_unchanged(self):
		project_source = inspect.getsource(project_search.search_projects)
		branch_source = inspect.getsource(project_search.search_project_branches)
		self.assertIn('frappe.get_list(\n\t\t"Project"', project_source)
		self.assertIn('frappe.get_list(\n\t\t"Branch"', branch_source)
		self.assertNotIn("insert(", branch_source)
		self.assertNotIn("save(", branch_source)
		self.assertNotIn("db_set", branch_source)


if __name__ == "__main__":
	unittest.main()
