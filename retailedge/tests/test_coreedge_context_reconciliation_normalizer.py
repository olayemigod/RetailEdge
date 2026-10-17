from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.integrations import context_reconciliation

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCoreEdgeContextReconciliationNormalizer(unittest.TestCase):
	def test_normalizer_preserves_company_branch_profile_authority(self):
		profiles = [
			{
				"name": "Old Ketu",
				"company": "RetailEdge Consulting",
				"branch": "Ketu",
				"enabled": 0,
				"modified": "2026-01-01",
			},
			{
				"name": "Ketu",
				"company": "RetailEdge Consulting",
				"branch": "Ketu",
				"enabled": 1,
				"modified": "2026-09-01",
			},
		]
		with (
			patch.object(context_reconciliation.frappe.db, "exists", return_value=True),
			patch.object(context_reconciliation.frappe, "get_all", return_value=profiles),
			patch.object(
				context_reconciliation,
				"_get_branch_identity",
				return_value={"label": "Ketu", "code": ""},
			),
		):
			rows = context_reconciliation.get_context_reconciliation_rows()

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["local_doctype"], "Branch")
		self.assertEqual(rows[0]["local_name"], "Ketu")
		self.assertEqual(rows[0]["company"], "RetailEdge Consulting")
		self.assertTrue(rows[0]["active"])
		self.assertEqual(rows[0]["source_profile"], "Ketu")

	def test_normalizer_is_read_only_and_coreedge_decoupled(self):
		source = (APP_ROOT / "integrations" / "context_reconciliation.py").read_text(encoding="utf-8")
		self.assertNotIn("import coreedge", source)
		self.assertNotIn("from coreedge", source)
		for forbidden in (
			"ignore_permissions=True",
			".insert(",
			".save(",
			".submit(",
			"frappe.db.set_value(",
			"frappe.db.commit(",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
