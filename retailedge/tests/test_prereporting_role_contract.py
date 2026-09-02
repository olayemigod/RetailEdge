from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.setup_roles import (
	ALL_RETAILEDGE_ROLE_NAMES,
	RETAILEDGE_ROLE_ALIASES,
	RETAILEDGE_ROLE_NAMES,
	canonical_retailedge_role,
	canonicalize_retailedge_roles,
	retailedge_role_variants,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestPrereportingRoleContract(unittest.TestCase):
	def test_longstanding_compact_roles_remain_canonical(self):
		self.assertEqual(
			RETAILEDGE_ROLE_NAMES,
			(
				"RetailEdgeCashier",
				"RetailEdgeManager",
				"RetailEdgeBranchManager",
				"RetailEdgeAuditor",
			),
		)
		self.assertEqual(canonical_retailedge_role("RetailEdge Manager"), "RetailEdgeManager")
		self.assertEqual(canonical_retailedge_role("RetailEdge Branch Manager"), "RetailEdgeBranchManager")
		self.assertEqual(canonical_retailedge_role("RetailEdge Auditor"), "RetailEdgeAuditor")
		self.assertEqual(canonical_retailedge_role("RetailEdge Cashier"), "RetailEdgeCashier")

	def test_spaced_names_remain_explicit_compatibility_aliases(self):
		self.assertEqual(RETAILEDGE_ROLE_ALIASES["RetailEdgeManager"], ("RetailEdge Manager",))
		self.assertEqual(RETAILEDGE_ROLE_ALIASES["RetailEdgeBranchManager"], ("RetailEdge Branch Manager",))
		self.assertEqual(RETAILEDGE_ROLE_ALIASES["RetailEdgeAuditor"], ("RetailEdge Auditor",))
		self.assertEqual(RETAILEDGE_ROLE_ALIASES["RetailEdgeCashier"], ("RetailEdge Cashier",))
		self.assertEqual(
			set(retailedge_role_variants("RetailEdge Manager")),
			{"RetailEdgeManager", "RetailEdge Manager"},
		)
		self.assertEqual(len(ALL_RETAILEDGE_ROLE_NAMES), 8)

	def test_role_sets_can_be_compared_without_alias_drift(self):
		self.assertEqual(
			canonicalize_retailedge_roles(
				{"RetailEdge Manager", "RetailEdgeBranchManager", "Accounts Manager"}
			),
			{"RetailEdgeManager", "RetailEdgeBranchManager", "Accounts Manager"},
		)

	def test_migration_is_additive_and_does_not_rename_or_remove_roles(self):
		source = (APP_ROOT / "setup_roles.py").read_text(encoding="utf-8")
		patch = (APP_ROOT / "patches" / "normalize_retailedge_role_assignments.py").read_text(encoding="utf-8")
		patches_txt = (APP_ROOT / "patches.txt").read_text(encoding="utf-8")

		self.assertIn("_add_canonical_roles_for_alias_assignments", source)
		self.assertIn('user_doc.append("roles", {"role": canonical})', source)
		self.assertIn("user_doc.save(ignore_permissions=True)", source)
		self.assertNotIn("remove_roles", source)
		self.assertNotIn("frappe.rename_doc", source)
		self.assertNotIn('frappe.db.set_value("Role"', source)
		self.assertIn("ensure_retailedge_roles(migrate_alias_assignments=True)", patch)
		self.assertIn("retailedge.patches.normalize_retailedge_role_assignments", patches_txt)

	def test_desk_access_contract_stays_system_user_compatible(self):
		source = (APP_ROOT / "setup_roles.py").read_text(encoding="utf-8")
		self.assertIn('"desk_access": 1', source)
		self.assertIn('if frappe.db.exists("Role", role_name):', source)
		self.assertNotIn('"desk_access": 0', source)


if __name__ == "__main__":
	unittest.main()
