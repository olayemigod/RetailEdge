from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.patches import consolidate_duplicate_retailedge_roles as migration


LEGACY = "RetailEdge Manager"
CANONICAL = "RetailEdgeManager"


def grant(parent="Payment Entry", **permissions):
    payload = frappe._dict(parent=parent, permlevel=0, if_owner=0)
    payload.update({field: 0 for field in migration.PERMISSION_FIELDS})
    payload.update(permissions)
    return payload


class TestRoleConsolidationPermissionSafety(unittest.TestCase):
    def run_preflight(self, rows, *, roles=None):
        role_pairs = roles or {LEGACY: CANONICAL}
        def get_all(doctype, *, filters=None, fields=None):
            return rows.get((doctype, filters["role"]), [])
        return (
            patch.object(migration, "LEGACY_TO_CANONICAL", role_pairs),
            patch.object(migration.frappe.db, "exists", return_value=True),
            patch.object(migration.frappe, "get_all", side_effect=get_all),
            patch.object(migration, "rename_doc"),
            patch.object(migration, "_merge_duplicate_has_role_rows"),
            patch.object(migration, "_merge_duplicate_permission_rows"),
            patch.object(migration.frappe, "clear_cache"),
            patch.object(migration, "get_link_fields", return_value=[]),
            patch.object(migration.frappe, "log_error"),
        )

    def assert_blocked_before_mutation(self, rows, *, roles=None):
        patches = self.run_preflight(rows, roles=roles)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4] as merge_roles, patches[5] as merge_grants, patches[6], patches[7], patches[8] as audit:
            migration.execute()
            rename.assert_not_called()
            merge_roles.assert_not_called()
            merge_grants.assert_not_called()
            audit.assert_called_once()
            self.assertEqual(audit.call_args.kwargs.get("title"), "RetailEdge role consolidation deferred")
            self.assertIn("Explicit administrator reconciliation", audit.call_args.kwargs.get("message", ""))

    def test_create_submit_escalation_is_rejected(self):
        self.assert_blocked_before_mutation({
            ("Custom DocPerm", LEGACY): [grant(read=1, create=1, submit=1)],
            ("Custom DocPerm", CANONICAL): [grant(read=1)],
        })

    def test_nonoverlapping_legacy_grant_is_rejected(self):
        self.assert_blocked_before_mutation({
            ("DocPerm", LEGACY): [grant("Journal Entry", read=1)],
            ("DocPerm", CANONICAL): [],
        })

    def test_mask_and_if_owner_differences_are_rejected(self):
        self.assertIn("mask", migration.PERMISSION_FIELDS)
        self.assert_blocked_before_mutation({
            ("Custom DocPerm", LEGACY): [grant(read=1, mask=1)],
            ("Custom DocPerm", CANONICAL): [grant(read=1, mask=0)],
        })
        legacy_owned = grant(read=1)
        legacy_owned.if_owner = 1
        self.assert_blocked_before_mutation({
            ("DocPerm", LEGACY): [legacy_owned],
            ("DocPerm", CANONICAL): [grant(read=1)],
        })

    def test_second_role_conflict_prevents_first_role_merge(self):
        self.assert_blocked_before_mutation({
            ("DocPerm", "RetailEdge Cashier"): [grant("Company", read=1)],
            ("DocPerm", "RetailEdgeCashier"): [grant("Company", read=1)],
            ("Custom DocPerm", LEGACY): [grant(write=1)],
            ("Custom DocPerm", CANONICAL): [grant(read=1)],
        }, roles={"RetailEdge Cashier": "RetailEdgeCashier", LEGACY: CANONICAL})

    def test_identical_permissions_allow_the_original_safe_merge_path(self):
        rows = {
            ("Custom DocPerm", LEGACY): [grant(read=1, print=1)],
            ("Custom DocPerm", CANONICAL): [grant(read=1, print=1)],
        }
        patches = self.run_preflight(rows)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4] as merge_roles, patches[5] as merge_grants, patches[6], patches[7], patches[8] as audit:
            migration.execute()
            audit.assert_not_called()
        merge_roles.assert_called_once_with(LEGACY, CANONICAL)
        self.assertEqual(merge_grants.call_count, 2)
        rename.assert_called_once()
        self.assertTrue(rename.call_args.kwargs["merge"])

    def test_legacy_reviewer_role_link_does_not_expand_canonical_users(self):
        patches = self.run_preflight({})
        role_links = [{"parent": "RetailEdge Daily Sales Audit Reviewer Role", "fieldname": "role", "issingle": 0}]
        def exists(doctype, value):
            if doctype == "Role":
                return True
            if doctype == "RetailEdge Daily Sales Audit Reviewer Role":
                return value == {"role": LEGACY}
            return True
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7] as links, patches[8] as audit:
            links.return_value = role_links
            with patch.object(migration.frappe.db, "exists", side_effect=exists):
                migration.execute()
            rename.assert_not_called()
            audit.assert_called_once()

    def test_legacy_only_page_role_assignment_fails_closed(self):
        rows = {
            ("Has Role", LEGACY): [frappe._dict(parent="private-review", parenttype="Page", parentfield="roles")],
        }
        patches = self.run_preflight(rows)
        def exists(doctype, value):
            if doctype == "Role":
                return True
            if doctype == "Has Role" and isinstance(value, dict) and value.get("role") == CANONICAL:
                return False
            return True
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8] as audit:
            with patch.object(migration.frappe.db, "exists", side_effect=exists):
                migration.execute()
            rename.assert_not_called()
            audit.assert_called_once()

    def test_preflight_remains_strict_for_manual_audit(self):
        patches = self.run_preflight({
            ("Custom DocPerm", LEGACY): [grant(read=1, submit=1)],
            ("Custom DocPerm", CANONICAL): [grant(read=1)],
        })
        with patches[0], patches[1], patches[2]:
            with self.assertRaises(frappe.ValidationError):
                migration._assert_permission_equivalence_before_merge()

    def test_equivalent_roles_merge_without_audit(self):
        patches = self.run_preflight({})
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8] as audit:
            migration.execute()
            rename.assert_called_once()
            audit.assert_not_called()

    def test_canonical_role_assignment_counterpart_preserves_authority(self):
        rows = {
            ("Has Role", LEGACY): [frappe._dict(parent="private-review", parenttype="Page", parentfield="roles")],
        }
        patches = self.run_preflight(rows)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8] as audit:
            migration.execute()
        rename.assert_called_once()

    def test_no_implicit_permission_union_remains(self):
        source = open(migration.__file__, encoding="utf-8").read()
        self.assertNotIn("merged = max(", source)
        self.assertIn("_assert_permission_equivalence_before_merge()", source)


if __name__ == "__main__":
    unittest.main()
