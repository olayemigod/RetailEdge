from __future__ import annotations

import json
import unittest
from pathlib import Path

from retailedge.setup_roles import (
    ALL_RETAILEDGE_ROLE_NAMES,
    RETAILEDGE_ROLE_NAMES,
    canonical_retailedge_role,
    canonicalize_retailedge_roles,
    retailedge_role_variants,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestPrereportingRoleContract(unittest.TestCase):
    def test_exactly_four_canonical_product_roles_exist_in_code(self):
        expected = (
            "RetailEdgeCashier",
            "RetailEdgeManager",
            "RetailEdgeBranchManager",
            "RetailEdgeAuditor",
        )
        self.assertEqual(RETAILEDGE_ROLE_NAMES, expected)
        self.assertEqual(ALL_RETAILEDGE_ROLE_NAMES, expected)

    def test_role_helpers_do_not_expand_aliases(self):
        for role_name in RETAILEDGE_ROLE_NAMES:
            self.assertEqual(canonical_retailedge_role(role_name), role_name)
            self.assertEqual(retailedge_role_variants(role_name), (role_name,))
        self.assertEqual(
            canonicalize_retailedge_roles(
                {"RetailEdgeCashier", "RetailEdgeManager", "Accounts Manager"}
            ),
            {"RetailEdgeCashier", "RetailEdgeManager", "Accounts Manager"},
        )

    def test_legacy_role_migration_is_registered_and_removes_duplicates(self):
        patch = (
            APP_ROOT / "patches" / "consolidate_duplicate_retailedge_roles.py"
        ).read_text(encoding="utf-8")
        patches_txt = (APP_ROOT / "patches.txt").read_text(encoding="utf-8")

        self.assertIn("retailedge.patches.consolidate_duplicate_retailedge_roles", patches_txt)
        for legacy, canonical in (
            ("RetailEdge Cashier", "RetailEdgeCashier"),
            ("RetailEdge Manager", "RetailEdgeManager"),
            ("RetailEdge Branch Manager", "RetailEdgeBranchManager"),
            ("RetailEdge Auditor", "RetailEdgeAuditor"),
        ):
            self.assertIn(f'"{legacy}": "{canonical}"', patch)
        self.assertIn("rename_doc(", patch)
        self.assertIn("merge=True", patch)
        self.assertIn("_merge_duplicate_has_role_rows", patch)
        self.assertIn("_merge_duplicate_permission_rows", patch)

    def test_json_permission_rows_use_only_canonical_product_roles_once(self):
        legacy_roles = {
            "RetailEdge Cashier",
            "RetailEdge Manager",
            "RetailEdge Branch Manager",
            "RetailEdge Auditor",
        }
        for path in APP_ROOT.rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            permissions = payload.get("permissions") or []
            keys = []
            for row in permissions:
                role = row.get("role")
                self.assertNotIn(role, legacy_roles, path)
                keys.append((role, int(row.get("permlevel") or 0), int(row.get("if_owner") or 0)))
            self.assertEqual(len(keys), len(set(keys)), path)

    def test_desk_access_contract_stays_system_user_compatible(self):
        source = (APP_ROOT / "setup_roles.py").read_text(encoding="utf-8")
        self.assertIn('"desk_access": 1', source)
        self.assertIn('if frappe.db.exists("Role", role_name):', source)
        self.assertNotIn('"desk_access": 0', source)


if __name__ == "__main__":
    unittest.main()
