from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.banking_readiness import (
	READINESS_BLOCKED,
	READINESS_WARNING,
	evaluate_bank_account_readiness,
)


class BankingReadinessTests(FrappeTestCase):
	def _fake_read_row(self, bank_row, account_row):
		def reader(doctype, name, candidates):
			if doctype == "Bank Account":
				return frappe._dict({"name": name, **bank_row})
			if doctype == "Account":
				return frappe._dict({"name": name, **account_row})
			return frappe._dict()

		return reader

	def _evaluate(self, bank_row=None, account_row=None, duplicate_count=1, mop_configured=True):
		bank_row = bank_row or {
			"bank": "Access Bank",
			"account": "Bank - RC",
			"company": "Retail Company",
			"disabled": 0,
			"retailedge_branch": "",
		}
		account_row = account_row or {
			"company": "Retail Company",
			"account_type": "Bank",
			"is_group": 0,
			"disabled": 0,
		}
		with (
			patch("retailedge.banking_readiness.has_doctype", return_value=True),
			patch("retailedge.banking_readiness.has_field", return_value=True),
			patch(
				"retailedge.banking_readiness._read_row",
				side_effect=self._fake_read_row(bank_row, account_row),
			),
			patch("retailedge.banking_readiness.frappe.db.count", return_value=duplicate_count),
			patch(
				"retailedge.banking_readiness._mode_of_payment_context",
				return_value={
					"configured": mop_configured,
					"modes": ["Bank Transfer"] if mop_configured else [],
					"conflicts": [],
				},
			),
		):
			return evaluate_bank_account_readiness("Access Bank Ketu", company="Retail Company")

	def test_company_and_bank_gl_are_hard_boundary(self):
		result = self._evaluate(
			account_row={
				"company": "Another Company",
				"account_type": "Bank",
				"is_group": 0,
				"disabled": 0,
			}
		)
		self.assertEqual(result["readiness"], READINESS_BLOCKED)
		self.assertIn("gl_company_mismatch", {row["code"] for row in result["issues"]})
		self.assertFalse(result["can_reconcile"])

	def test_non_bank_gl_is_blocked(self):
		result = self._evaluate(
			account_row={
				"company": "Retail Company",
				"account_type": "Receivable",
				"is_group": 0,
				"disabled": 0,
			}
		)
		self.assertEqual(result["readiness"], READINESS_BLOCKED)
		self.assertIn("gl_account_not_bank_type", {row["code"] for row in result["issues"]})

	def test_duplicate_bank_account_gl_mapping_is_blocked(self):
		result = self._evaluate(duplicate_count=2)
		self.assertEqual(result["readiness"], READINESS_BLOCKED)
		self.assertIn("ambiguous_bank_account_mapping", {row["code"] for row in result["issues"]})

	def test_missing_mode_of_payment_is_warning_not_blocker(self):
		result = self._evaluate(mop_configured=False)
		self.assertEqual(result["readiness"], READINESS_WARNING)
		self.assertTrue(result["can_match"])
		self.assertTrue(result["can_reconcile"])
		self.assertIn("mode_of_payment_default_missing", {row["code"] for row in result["warnings"]})

	def test_company_wide_bank_account_does_not_require_branch(self):
		result = self._evaluate()
		self.assertNotEqual(result["readiness"], READINESS_BLOCKED)
		self.assertEqual(result["branch_scope"], "Company Wide / Central")
		self.assertIn("branch_not_restricted", {row["code"] for row in result["warnings"]})
