from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class WorkingBranchPermissionProbeContractTests(unittest.TestCase):
	def _read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def _assert_silent_pos_opening_probe(self, source: str) -> None:
		start = source.index("def _find_open_erpnext_pos_opening")
		end_candidates = [
			index
			for marker in ("\n\ndef _assert_switch_safe", "\n\n@frappe.whitelist()")
			if (index := source.find(marker, start + 1)) >= 0
		]
		end = min(end_candidates) if end_candidates else len(source)
		probe = source[start:end]
		for contract in (
			'previous_messages = list(getattr(frappe.local, "message_log", []) or [])',
			'frappe.has_permission("POS Opening Entry", "read", user=user)',
			"if not frappe.has_permission",
			"return None",
			"finally:",
			"frappe.local.message_log = previous_messages",
		):
			self.assertIn(contract, probe)
		self.assertLess(
			probe.index('frappe.has_permission("POS Opening Entry", "read", user=user)'),
			probe.index("frappe.get_list("),
		)

	def test_operating_context_probe_is_permission_safe_and_silent(self):
		self._assert_silent_pos_opening_probe(self._read("operating_context.py"))

	def test_transaction_workspace_probe_is_permission_safe_and_silent(self):
		self._assert_silent_pos_opening_probe(
			self._read("retailedge/page/transaction_workspace/transaction_workspace.py")
		)


if __name__ == "__main__":
	unittest.main()
