from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import call, patch

from retailedge.patches import ensure_retailedge_cashier_posnext_permissions as permission_patch


APP_ROOT = Path(__file__).resolve().parents[1]
PATCHES = APP_ROOT / "patches.txt"


class TestCashierPOSNextPermissionBridge(unittest.TestCase):
	def test_execute_grants_only_required_pos_runtime_permissions(self):
		with (
			patch.object(permission_patch.frappe.db, "exists", return_value=True),
			patch.object(permission_patch, "_grant") as grant,
		):
			permission_patch.execute()

		expected_calls = []
		for role in permission_patch.CASHIER_ROLES:
			expected_calls.extend(
				[
					call("Account", role, ("read", "select")),
					call("POS Opening Shift", role, ("read", "create", "write", "submit")),
					call("POS Closing Shift", role, ("read", "create", "write", "submit")),
				]
			)
		self.assertEqual(grant.call_args_list, expected_calls)

	def test_bridge_does_not_expand_cashier_authority(self):
		source = Path(permission_patch.__file__).read_text(encoding="utf-8")
		for forbidden_permission in ("delete", "cancel", "amend"):
			self.assertNotIn(f'"{forbidden_permission}"', source)
		for forbidden_role in ("POSNext Cashier", "Sales User", "Accounts User", "System Manager"):
			self.assertNotIn(forbidden_role, source)

	def test_patch_runs_after_existing_cashier_operational_permissions(self):
		patches = PATCHES.read_text(encoding="utf-8")
		operational_patch = "retailedge.patches.ensure_retailedge_cashier_operational_permissions"
		posnext_patch = "retailedge.patches.ensure_retailedge_cashier_posnext_permissions"
		self.assertIn(operational_patch, patches)
		self.assertIn(posnext_patch, patches)
		self.assertLess(patches.index(operational_patch), patches.index(posnext_patch))


if __name__ == "__main__":
	unittest.main()
