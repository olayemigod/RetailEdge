from __future__ import annotations

import unittest

from retailedge.retailedge.report.retailedge_branch_performance_summary import (
	retailedge_branch_performance_summary as branch_report,
)


class TestBranchPerformanceVarianceQuality(unittest.TestCase):
	def test_headline_variance_preserves_signed_and_absolute_views(self):
		rows = [
			{"branch": "Lagos", "gross_sales": 100000, "audit_variance": -1500},
			{"branch": "Abuja", "gross_sales": 80000, "audit_variance": 1000},
		]
		cards = {card["label"]: card["value"] for card in branch_report.get_report_summary(rows)}
		self.assertEqual(cards["Absolute Audit Variance"], 2500)
		self.assertEqual(cards["Audit Variance"], -500)

	def test_row_level_column_remains_signed_audit_variance(self):
		columns = {column["fieldname"]: column for column in branch_report.get_columns()}
		self.assertEqual(columns["audit_variance"]["label"], "Audit Variance")
		self.assertEqual(columns["audit_variance"]["fieldtype"], "Currency")
