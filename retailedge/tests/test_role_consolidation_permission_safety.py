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
        def get_all(doctype, *, filters=None, fields=None, **kwargs):
            if doctype == "Role":
                names = filters["name"][1]
                role_policies = rows.get(("Role", "policies"), {})
                return [
                    frappe._dict(name=role, **role_policies.get(role, {
                        "disabled": 0,
                        "desk_access": 1,
                        "two_factor_auth": 0,
                        "restrict_to_domain": "",
                    }))
                    for role in names
                ]
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
            patch.object(migration, "get_doctype_ptype_map", return_value={}),
        )

    def assert_blocked_before_mutation(self, rows, *, roles=None):
        patches = self.run_preflight(rows, roles=roles)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4] as merge_roles, patches[5] as merge_grants, patches[6], patches[7], patches[8] as audit, patches[9]:
            with self.assertRaises(frappe.ValidationError):
                migration.execute()
            rename.assert_not_called()
            merge_roles.assert_not_called()
            merge_grants.assert_not_called()
            audit.assert_not_called()

    def test_preflight_reports_all_conflicts_without_truncation(self):
        rows = {
            ("DocPerm", LEGACY): [grant(f"Business DocType {index}", read=1) for index in range(16)],
            ("DocPerm", CANONICAL): [],
        }
        patches = self.run_preflight(rows)
        with patches[0], patches[1], patches[2], patches[9]:
            with self.assertRaises(frappe.ValidationError) as blocked:
                migration._assert_permission_equivalence_before_merge()
        self.assertIn("Business DocType 0", str(blocked.exception))
        self.assertIn("Business DocType 15", str(blocked.exception))
        self.assertNotIn("(+4 more)", str(blocked.exception))

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
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4] as merge_roles, patches[5] as merge_grants, patches[6], patches[7], patches[8] as audit, patches[9]:
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
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7] as links, patches[8] as audit, patches[9]:
            links.return_value = role_links
            with patch.object(migration.frappe.db, "exists", side_effect=exists):
                with self.assertRaises(frappe.ValidationError):
                    migration.execute()
            rename.assert_not_called()
            audit.assert_not_called()

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
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8] as audit, patches[9]:
            with patch.object(migration.frappe.db, "exists", side_effect=exists):
                with self.assertRaises(frappe.ValidationError):
                    migration.execute()
            rename.assert_not_called()
            audit.assert_not_called()

    def test_custom_permission_type_difference_blocks_role_merge(self):
        rows = {
            ("Custom DocPerm", LEGACY): [grant("User", read=1, impersonate=1)],
            ("Custom DocPerm", CANONICAL): [grant("User", read=1, impersonate=0)],
        }
        patches = self.run_preflight(rows)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8] as audit, patches[9] as ptypes:
            ptypes.return_value = {"User": ["impersonate"]}
            with self.assertRaises(frappe.ValidationError) as blocked:
                migration.execute()
            rename.assert_not_called()
            audit.assert_not_called()
            self.assertIn("Custom DocPerm User", str(blocked.exception))

    def test_legacy_two_factor_auth_policy_is_preserved(self):
        rows = {
            ("Role", "policies"): {
                LEGACY: {
                    "disabled": 0, "desk_access": 1,
                    "two_factor_auth": 1, "restrict_to_domain": "",
                },
                CANONICAL: {
                    "disabled": 0, "desk_access": 1,
                    "two_factor_auth": 0, "restrict_to_domain": "",
                },
            },
        }
        patches = self.run_preflight(rows)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8] as audit, patches[9]:
            with self.assertRaises(frappe.ValidationError) as blocked:
                migration.execute()
            rename.assert_not_called()
            audit.assert_not_called()
            self.assertIn("Role.two_factor_auth", str(blocked.exception))

    def test_preflight_remains_strict_for_manual_audit(self):
        patches = self.run_preflight({
            ("Custom DocPerm", LEGACY): [grant(read=1, submit=1)],
            ("Custom DocPerm", CANONICAL): [grant(read=1)],
        })
        with patches[0], patches[1], patches[2], patches[9]:
            with self.assertRaises(frappe.ValidationError):
                migration._assert_permission_equivalence_before_merge()

    def test_equivalent_roles_merge_without_audit(self):
        patches = self.run_preflight({})
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8] as audit, patches[9]:
            migration.execute()
            rename.assert_called_once()
            audit.assert_not_called()

    def test_canonical_role_assignment_counterpart_preserves_authority(self):
        rows = {
            ("Has Role", LEGACY): [frappe._dict(parent="private-review", parenttype="Page", parentfield="roles")],
        }
        patches = self.run_preflight(rows)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8] as audit, patches[9]:
            migration.execute()
        rename.assert_called_once()

    def test_no_implicit_permission_union_remains(self):
        source = open(migration.__file__, encoding="utf-8").read()
        self.assertNotIn("merged = max(", source)
        self.assertIn("_assert_permission_equivalence_before_merge()", source)


if __name__ == "__main__":
    unittest.main()
