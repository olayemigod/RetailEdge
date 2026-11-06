from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROLES = {
    "RetailEdgeCashier",
    "RetailEdgeManager",
    "RetailEdgeBranchManager",
    "RetailEdgeAuditor",
}
LEGACY_ROLES = {
    "RetailEdge Cashier",
    "RetailEdge Manager",
    "RetailEdge Branch Manager",
    "RetailEdge Auditor",
}


class TestRetailEdgePageRoleSync(unittest.TestCase):
    def test_setup_creates_only_canonical_roles(self):
        source = (APP_ROOT / "setup_roles.py").read_text(encoding="utf-8")
        for role in CANONICAL_ROLES:
            self.assertIn(f'"{role}"', source)
        for role in LEGACY_ROLES:
            self.assertNotIn(f'"{role}"', source)

    def test_page_definitions_never_declare_legacy_roles_or_duplicate_roles(self):
        page_root = APP_ROOT / "retailedge" / "page"
        for path in page_root.glob("*/*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            roles = [row["role"] for row in payload.get("roles") or []]
            with self.subTest(page=path.parent.name):
                self.assertFalse(LEGACY_ROLES.intersection(roles))
                self.assertEqual(len(roles), len(set(roles)))

    def test_stale_accounts_reviewer_is_not_declared_on_pages(self):
        for relative_path in (
            "retailedge/page/retailedge_business_hub/retailedge_business_hub.json",
            "retailedge/page/reports_centre/reports_centre.json",
        ):
            source = (APP_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("RetailEdge Accounts Reviewer", source)

    def test_stale_accounts_reviewer_cleanup_is_bounded_and_registered(self):
        patch_source = (
            APP_ROOT / "patches" / "remove_stale_accounts_reviewer_page_roles.py"
        ).read_text(encoding="utf-8")
        patches = (APP_ROOT / "patches.txt").read_text(encoding="utf-8")

        self.assertIn("retailedge.patches.remove_stale_accounts_reviewer_page_roles", patches)
        self.assertIn('STALE_ROLE = "RetailEdge Accounts Reviewer"', patch_source)
        self.assertIn('"retailedge-business-hub"', patch_source)
        self.assertIn('"reports-centre"', patch_source)
        self.assertNotIn('frappe.db.delete("Role"', patch_source)

    def test_core_page_role_reconciliation_is_exact_and_bounded(self):
        patch_source = (
            APP_ROOT / "patches" / "reconcile_core_page_role_access.py"
        ).read_text(encoding="utf-8")
        patches = (APP_ROOT / "patches.txt").read_text(encoding="utf-8")

        self.assertIn("retailedge.patches.reconcile_core_page_role_access", patches)
        self.assertIn('"retailedge-business-hub"', patch_source)
        self.assertIn('"Sales User"', patch_source)
        self.assertIn('"Purchase User"', patch_source)
        self.assertIn('"payment-management"', patch_source)
        self.assertIn('"Accounts User"', patch_source)
        self.assertIn('frappe.db.delete(', patch_source)
        self.assertNotIn("page.save(", patch_source)


if __name__ == "__main__":
    unittest.main()
