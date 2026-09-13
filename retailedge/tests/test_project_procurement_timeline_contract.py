from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProjectProcurementTimelineContract(TestCase):
	def test_procurement_lifecycle_is_declared_in_native_timeline(self):
		source = (APP_ROOT / "project_operations.py").read_text()

		self.assertIn('{"doctype": "Material Request", "kind": "Procurement", "label": "Material Request"}', source)
		self.assertIn('{"doctype": "Purchase Order", "kind": "Procurement", "label": "Purchase Order"}', source)
		self.assertIn('{"doctype": "Purchase Receipt", "kind": "Procurement", "label": "Purchase Receipt"}', source)

	def test_timeline_requires_safe_parent_project_and_branch_fields(self):
		source = (APP_ROOT / "project_operations.py").read_text()

		self.assertIn('not _has_field(doctype, "project")', source)
		self.assertIn("if branch and not branch_field", source)
		self.assertIn("Project exists only on child rows are omitted", source)
		self.assertIn('"docstatus": ["<", 2]', source)
		self.assertIn("rows[:MAX_TIMELINE_ROWS]", source)


if __name__ == "__main__":
	import unittest
	unittest.main()
