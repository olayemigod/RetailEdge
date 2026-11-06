from __future__ import annotations

import unittest
from unittest.mock import MagicMock, call, patch

import frappe

from retailedge.patches import consolidate_duplicate_retailedge_roles as migration

LEGACY = "RetailEdge Manager"
CANONICAL = "RetailEdgeManager"


def grant(parent="Payment Entry", **permissions):
    payload = frappe._dict(parent=parent, permlevel=0, if_owner=0)
    payload.update({field: 0 for field in migration.PERMISSION_FIELDS})
    payload.update(permissions)
    return payload


def raise_validation_error(message, *args, **kwargs):
    raise frappe.ValidationError(message)


class TestRoleConsolidationPermissionSafety(unittest.TestCase):
    def setUp(self):
        throw_patcher = patch.object(
            migration.frappe, "throw", side_effect=raise_validation_error
        )
        throw_patcher.start()
        self.addCleanup(throw_patcher.stop)

    def run_preflight(self, rows, *, roles=None):
        role_pairs = roles or {LEGACY: CANONICAL}
        database = MagicMock()
        database.exists.return_value = True
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
            patch.object(migration.frappe, "db", database),
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

    def assert_canonical_policy_selected(self, rows, *, roles=None):
        patches = self.run_preflight(rows, roles=roles)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5] as merge_grants, patches[6], patches[7], patches[8] as audit, patches[9]:
            migration.execute()
        self.assertEqual(merge_grants.call_count, 2 * len(roles or {LEGACY: CANONICAL}))
        audit.assert_called_once()
        rename.assert_called()

    def test_role_consolidation_patch_cannot_be_skipped_by_migrate(self):
        from frappe.modules.patch_handler import should_never_skip

        from retailedge import hooks

        name = "retailedge.patches.consolidate_duplicate_retailedge_roles"
        self.assertIn(name, hooks.never_skip_patches)
        self.assertTrue(should_never_skip(name, set(hooks.never_skip_patches)))
        self.assertTrue(should_never_skip(name + " # replay", set(hooks.never_skip_patches)))
        self.assertFalse(should_never_skip("retailedge.patches.unrelated_patch", set(hooks.never_skip_patches)))

    def test_permission_conflict_report_exposes_exact_grants_without_mutation(self):
        rows = {
            ("Custom DocPerm", LEGACY): [grant("User", read=1, impersonate=1)],
            ("Custom DocPerm", CANONICAL): [grant("User", read=1)],
            ("DocPerm", LEGACY): [grant("RetailEdge Cashier Expense", read=1)],
            ("DocPerm", CANONICAL): [],
        }
        patches = self.run_preflight(rows)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4] as merge_roles, patches[5] as merge_grants, patches[9] as ptypes:
            ptypes.return_value = {"User": ["impersonate"]}
            report = migration.get_role_permission_conflict_report()
            rename.assert_not_called()
            merge_roles.assert_not_called()
            merge_grants.assert_not_called()
        self.assertTrue(report["read_only"])
        self.assertEqual(report["conflict_count"], 2)
        self.assertIn("impersonate", report["permission_fields_checked"])
        by_doc = {row["document_type"]: row for row in report["conflicts"]}
        self.assertEqual(by_doc["User"]["legacy_grants"], [{"impersonate": 1, "read": 1}])
        self.assertEqual(by_doc["User"]["canonical_grants"], [{"read": 1}])
        self.assertEqual(by_doc["RetailEdge Cashier Expense"]["canonical_grants"], [])

    def test_permission_conflict_report_returns_empty_when_grants_equivalent(self):
        rows = {
            ("DocPerm", LEGACY): [grant("Payment Entry", read=1)],
            ("DocPerm", CANONICAL): [grant("Payment Entry", read=1)],
        }
        patches = self.run_preflight(rows)
        with patches[0], patches[1], patches[2], patches[9]:
            report = migration.get_role_permission_conflict_report()
        self.assertEqual(report["conflict_count"], 0)

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

    def test_create_submit_escalation_is_replaced_by_canonical_policy(self):
        self.assert_canonical_policy_selected({
            ("Custom DocPerm", LEGACY): [grant(read=1, create=1, submit=1)],
            ("Custom DocPerm", CANONICAL): [grant(read=1)],
        })

    def test_nonoverlapping_legacy_grant_is_replaced_by_canonical_policy(self):
        self.assert_canonical_policy_selected({
            ("DocPerm", LEGACY): [grant("Journal Entry", read=1)],
            ("DocPerm", CANONICAL): [],
        })

    def test_mask_and_if_owner_differences_select_canonical_policy(self):
        self.assertIn("mask", migration.PERMISSION_FIELDS)
        self.assert_canonical_policy_selected({
            ("Custom DocPerm", LEGACY): [grant(read=1, mask=1)],
            ("Custom DocPerm", CANONICAL): [grant(read=1, mask=0)],
        })
        legacy_owned = grant(read=1)
        legacy_owned.if_owner = 1
        self.assert_canonical_policy_selected({
            ("DocPerm", LEGACY): [legacy_owned],
            ("DocPerm", CANONICAL): [grant(read=1)],
        })

    def test_all_role_conflicts_use_canonical_permissions(self):
        self.assert_canonical_policy_selected({
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

    def test_approved_salesperson_dashboard_assignment_preserves_manager_access(self):
        role_pairs = (
            ("RetailEdge Manager", "RetailEdgeManager"),
            ("RetailEdge Branch Manager", "RetailEdgeBranchManager"),
        )
        for legacy, canonical in role_pairs:
            with self.subTest(legacy=legacy):
                rows = {
                    ("Has Role", legacy): [
                        frappe._dict(
                            parent="salesperson-performance-dashboard",
                            parenttype="Page",
                            parentfield="roles",
                        )
                    ],
                }
                patches = self.run_preflight(rows, roles={legacy: canonical})

                def exists(doctype, value):
                    if doctype == "Role":
                        return True
                    if doctype == "Has Role":
                        return False
                    return True

                with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
                    with patch.object(migration.frappe.db, "exists", side_effect=exists):
                        migration.execute()
                rename.assert_called_once()

    def test_custom_permission_type_difference_uses_canonical_permissions(self):
        rows = {
            ("Custom DocPerm", LEGACY): [grant("User", read=1, impersonate=1)],
            ("Custom DocPerm", CANONICAL): [grant("User", read=1, impersonate=0)],
        }
        patches = self.run_preflight(rows)
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5] as merge_grants, patches[6], patches[7], patches[8] as audit, patches[9] as ptypes:
            ptypes.return_value = {"User": ["impersonate"]}
            migration.execute()
            self.assertEqual(merge_grants.call_count, 2)
            rename.assert_called_once()
            audit.assert_called_once()

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
        with patches[0], patches[1], patches[2], patches[3] as rename, patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
            migration.execute()
        rename.assert_called_once()

    def test_no_implicit_permission_union_remains(self):
        source = open(migration.__file__, encoding="utf-8").read()
        self.assertNotIn("merged = max(", source)
        self.assertIn('frappe.db.delete(doctype, {"role": legacy})', source)

    def test_permission_merge_helper_deletes_only_legacy_role_rows(self):
        database = MagicMock()
        database.exists.return_value = True
        with patch.object(migration.frappe, "db", database):
            migration._merge_duplicate_permission_rows("DocPerm", LEGACY, CANONICAL)
        self.assertEqual(
            database.delete.call_args_list,
            [call("DocPerm", {"role": LEGACY})],
        )


if __name__ == "__main__":
    unittest.main()
