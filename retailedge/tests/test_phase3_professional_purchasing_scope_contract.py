from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from retailedge import landed_cost_allocation as landed
from retailedge import professional_purchasing as purchasing


ROOT = Path(__file__).resolve().parents[1]
PURCHASING = ROOT / "professional_purchasing.py"
LANDED = ROOT / "landed_cost_allocation.py"


class TestPhase3ProfessionalPurchasingScopeContract(TestCase):
	def test_active_company_cannot_be_overridden_by_browser_scope(self):
		with (
			patch.object(
				purchasing,
				"get_operating_context",
				return_value={"company": "RetailEdge Consulting", "branch": ""},
			),
			patch.object(purchasing, "_assert_read"),
		):
			with self.assertRaises(frappe.PermissionError):
				purchasing._resolve_scope(company="Other Company")

	def test_active_branch_cannot_be_overridden_by_browser_scope(self):
		with (
			patch.object(
				purchasing,
				"get_operating_context",
				return_value={"company": "RetailEdge Consulting", "branch": "Lagos"},
			),
			patch.object(purchasing, "_assert_read"),
		):
			with self.assertRaises(frappe.PermissionError):
				purchasing._resolve_scope(
					company="RetailEdge Consulting",
					branch="Abuja",
				)

	def test_restricted_scope_uses_operational_branch_contract(self):
		with (
			patch.object(
				purchasing,
				"get_operating_context",
				return_value={"company": "RetailEdge Consulting", "branch": ""},
			),
			patch.object(purchasing, "_assert_read"),
			patch.object(
				purchasing,
				"get_operational_branch_scope",
				return_value={
					"company": "RetailEdge Consulting",
					"restricted": True,
					"allowed_branches": ["Lagos"],
					"source": "branch_assignment",
				},
			),
			patch.object(purchasing, "validate_operating_branch") as validate_branch,
		):
			scope = purchasing._resolve_scope(
				company="RetailEdge Consulting",
				branch="Lagos",
			)

		self.assertEqual(
			scope,
			("RetailEdge Consulting", "Lagos", ["Lagos"], False),
		)
		validate_branch.assert_called_once_with(
			company="RetailEdge Consulting",
			branch="Lagos",
			user=frappe.session.user,
			throw=True,
		)

	def test_source_branch_revalidation_uses_branch_setup_aware_validator(self):
		source = SimpleNamespace(
			doctype="Purchase Receipt",
			name="MAT-PRE-0001",
			docstatus=1,
			is_return=0,
			company="RetailEdge Consulting",
		)
		with (
			patch.object(purchasing, "_assert_read"),
			patch.object(purchasing, "_document_branch", return_value="Disabled Branch"),
			patch.object(
				purchasing,
				"validate_operating_branch",
				side_effect=frappe.PermissionError,
			) as validate_branch,
		):
			with self.assertRaises(frappe.PermissionError):
				purchasing._validate_native_purchase_return_source(
					source,
					source_label="Purchase Receipt",
				)

		validate_branch.assert_called_once_with(
			company="RetailEdge Consulting",
			branch="Disabled Branch",
			user=frappe.session.user,
			throw=True,
		)

	def test_active_company_and_branch_limit_smart_selectors(self):
		source = PURCHASING.read_text(encoding="utf-8")
		self.assertIn('filters = {"name": active_company} if active_company else None', source)
		self.assertIn('if resolved_branch:', source)
		self.assertIn('filters["name"] = resolved_branch', source)
		self.assertIn("validate_operating_branch(", source)
		self.assertNotIn("validate_user_branch_access(", source)

	def test_landed_cost_inherits_shared_professional_purchasing_scope(self):
		source = LANDED.read_text(encoding="utf-8")
		self.assertIn("_resolve_scope", source)
		self.assertIn("_branch_scoped_filters", source)
		self.assertIn("_validate_native_purchase_return_source", source)
		self.assertIn("search_landed_cost_sources", source)
		self.assertIn("_get_source", source)

	def test_phase3_keeps_erpnext_landed_cost_authority_unchanged(self):
		source = LANDED.read_text(encoding="utf-8")
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("update_landed_cost(", source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)
		self.assertIn("make_lcv", source)
		self.assertIn("landed_cost_voucher.submit()", source)


if __name__ == "__main__":
	import unittest

	unittest.main()
