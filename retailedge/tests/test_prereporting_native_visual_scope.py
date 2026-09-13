from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.native_visual_workspaces import (
	SCOPE_COMPANY,
	SCOPE_CONFIGURED_BRANCH_STOCK,
	SCOPE_NATIVE_PERMISSION,
	SUPPORTED_PREVIEW_SCOPES,
	WORKSPACES,
	_build_preview_scope_plan,
	_get_configured_branch_stock_locations,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _FakeMeta:
	def __init__(self, *fields: str):
		self.fields = set(fields)

	def has_field(self, fieldname: str) -> bool:
		return fieldname in self.fields


class RetailEdgePreReportingNativeVisualScopeTests(unittest.TestCase):
	def test_every_doctype_preview_declares_a_supported_scope(self):
		for workspace, config in WORKSPACES.items():
			for source in config["sources"]:
				if source["kind"] != "doctype":
					continue
				with self.subTest(workspace=workspace, target=source["target"]):
					self.assertIn(source.get("scope"), SUPPORTED_PREVIEW_SCOPES)

	def test_company_scope_preserves_static_filters_and_applies_operating_company(self):
		plan = _build_preview_scope_plan(
			{"scope": SCOPE_COMPANY, "filters": {"disabled": 0}},
			doctype="Asset",
			meta=_FakeMeta("company"),
			operating_context={"company": "PISONMART", "branch": "Main"},
		)

		self.assertTrue(plan["query_allowed"])
		self.assertEqual(plan["state"], "applied")
		self.assertEqual(plan["filters"], {"disabled": 0, "company": "PISONMART"})

	def test_company_scope_fails_closed_when_schema_has_no_company_field(self):
		plan = _build_preview_scope_plan(
			{"scope": SCOPE_COMPANY},
			doctype="Unsafe Master",
			meta=_FakeMeta(),
			operating_context={"company": "PISONMART", "branch": "Main"},
		)

		self.assertFalse(plan["query_allowed"])
		self.assertEqual(plan["state"], "blocked")

	def test_native_permission_scope_does_not_invent_company_or_branch_filters(self):
		plan = _build_preview_scope_plan(
			{"scope": SCOPE_NATIVE_PERMISSION, "filters": {"enabled": 1}},
			doctype="Sales Person",
			meta=_FakeMeta(),
			operating_context={"company": "PISONMART", "branch": "Main"},
		)

		self.assertTrue(plan["query_allowed"])
		self.assertEqual(plan["state"], "native_permission")
		self.assertEqual(plan["filters"], {"enabled": 1})

	def test_branch_stock_scope_uses_only_exact_profile_stock_locations(self):
		profile = SimpleNamespace(
			default_warehouse="MAIN-WH",
			default_source_warehouse="MAIN-WH",
			default_target_warehouse="TRANSIT-WH",
			default_returns_warehouse="RETURNS-WH",
		)
		with patch("retailedge.native_visual_workspaces.get_exact_branch_profile", return_value=profile):
			warehouses = _get_configured_branch_stock_locations(company="PISONMART", branch="Main")
			plan = _build_preview_scope_plan(
				{"scope": SCOPE_CONFIGURED_BRANCH_STOCK},
				doctype="Serial No",
				meta=_FakeMeta("warehouse", "company"),
				operating_context={"company": "PISONMART", "branch": "Main"},
			)

		self.assertEqual(warehouses, ["MAIN-WH", "TRANSIT-WH", "RETURNS-WH"])
		self.assertTrue(plan["query_allowed"])
		self.assertEqual(plan["filters"]["company"], "PISONMART")
		self.assertEqual(
			plan["filters"]["warehouse"],
			["in", ["MAIN-WH", "TRANSIT-WH", "RETURNS-WH"]],
		)

	def test_branch_stock_scope_fails_closed_without_exact_branch_stock_setup(self):
		with patch("retailedge.native_visual_workspaces.get_exact_branch_profile", return_value=None):
			plan = _build_preview_scope_plan(
				{"scope": SCOPE_CONFIGURED_BRANCH_STOCK},
				doctype="Serial No",
				meta=_FakeMeta("warehouse", "company"),
				operating_context={"company": "PISONMART", "branch": "Main"},
			)

		self.assertFalse(plan["query_allowed"])
		self.assertEqual(plan["state"], "blocked")

	def test_workspace_uses_server_operating_context_and_keeps_bounded_permission_aware_reads(self):
		source = (APP_ROOT / "native_visual_workspaces.py").read_text()
		self.assertIn("operating_context = get_operating_context()", source)
		self.assertIn("frappe.get_list(", source)
		self.assertIn("limit_page_length=RECENT_LIMIT", source)
		self.assertNotIn("frappe.get_all(\n\t\tdoctype", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.defaults.get_user_default", source)


if __name__ == "__main__":
	unittest.main()
