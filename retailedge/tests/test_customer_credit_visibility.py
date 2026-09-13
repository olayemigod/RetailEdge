from __future__ import annotations

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from retailedge import customer_credit_visibility as credit


class TestCustomerCreditVisibility(FrappeTestCase):
	def _call(
		self,
		*,
		credit_limit=1000,
		outstanding=400,
		overdue_threshold=200,
		overdue_amount=50,
		bypass=False,
		overdue_enabled=True,
	):
		customer_state = credit.frappe._dict(
			customer_name="Customer One",
			customer_group="Commercial",
			is_frozen=0,
			disabled=0,
		)

		def get_value(doctype, name_or_filters, fields=None, **kwargs):
			if doctype == "Customer" and fields == ["customer_name", "customer_group", "is_frozen", "disabled"]:
				return customer_state
			if doctype == "Customer Credit Limit" and fields == "bypass_credit_limit_check":
				return int(bypass)
			return None

		with (
			patch.object(credit, "_assert_read"),
			patch.object(credit, "_can_read_credit_report", return_value=True),
			patch.object(credit.frappe.db, "get_value", side_effect=get_value),
			patch.object(credit.frappe, "get_cached_value", return_value="NGN"),
			patch.object(credit.frappe, "get_single_value", return_value=int(overdue_enabled)),
			patch.object(credit, "get_credit_limit", return_value=credit_limit) as native_limit,
			patch.object(credit, "get_customer_outstanding", return_value=outstanding) as native_outstanding,
			patch.object(credit, "get_overdue_billing_threshold", return_value=overdue_threshold) as native_threshold,
			patch.object(credit, "get_customer_overdue_amount", return_value=overdue_amount) as native_overdue,
		):
			result = credit.get_customer_credit_visibility("CUST-001", "Test Company")

		return result, native_limit, native_outstanding, native_threshold, native_overdue

	def test_uses_native_erpnext_credit_helpers(self):
		result, native_limit, native_outstanding, native_threshold, native_overdue = self._call()

		native_limit.assert_called_once_with("CUST-001", "Test Company")
		native_outstanding.assert_called_once_with(
			"CUST-001",
			"Test Company",
			ignore_outstanding_sales_order=False,
		)
		native_threshold.assert_called_once_with("CUST-001", "Test Company")
		native_overdue.assert_called_once_with("CUST-001", "Test Company")
		self.assertEqual(result["remaining_credit"], 600)
		self.assertFalse(result["credit_limit_crossed"])
		self.assertEqual(result["scope"], "company")
		self.assertTrue(result["advisory_only"])

	def test_sales_order_bypass_is_reflected_in_native_exposure_call(self):
		result, _limit, native_outstanding, _threshold, _overdue = self._call(bypass=True)

		native_outstanding.assert_called_once_with(
			"CUST-001",
			"Test Company",
			ignore_outstanding_sales_order=True,
		)
		self.assertTrue(result["sales_order_credit_check_bypassed"])

	def test_no_credit_limit_is_not_zero_available_credit(self):
		result, *_mocks = self._call(credit_limit=0, outstanding=400)

		self.assertFalse(result["has_credit_limit"])
		self.assertIsNone(result["remaining_credit"])
		self.assertFalse(result["credit_limit_crossed"])

	def test_crossed_credit_and_overdue_limits_are_advisory_flags(self):
		result, *_mocks = self._call(
			credit_limit=500,
			outstanding=750,
			overdue_threshold=200,
			overdue_amount=250,
			overdue_enabled=True,
		)

		self.assertTrue(result["credit_limit_crossed"])
		self.assertEqual(result["remaining_credit"], -250)
		self.assertTrue(result["overdue_threshold_crossed"])
		self.assertIn("ERPNext", result["final_enforcement"])

	def test_disabled_overdue_control_does_not_claim_enforcement(self):
		result, *_mocks = self._call(
			overdue_threshold=200,
			overdue_amount=250,
			overdue_enabled=False,
		)

		self.assertFalse(result["overdue_enforcement_enabled"])
		self.assertFalse(result["overdue_threshold_crossed"])

	def test_report_permission_is_required(self):
		with (
			patch.object(credit, "_assert_read"),
			patch.object(credit, "_can_read_credit_report", return_value=False),
		):
			with self.assertRaises(credit.frappe.PermissionError):
				credit.get_customer_credit_visibility("CUST-001", "Test Company")

	def test_source_does_not_reimplement_credit_ledger_or_write_documents(self):
		source = open(credit.__file__, encoding="utf-8").read()

		self.assertIn("get_credit_limit", source)
		self.assertIn("get_customer_outstanding", source)
		self.assertIn("get_customer_overdue_amount", source)
		self.assertNotIn('DocType("GL Entry")', source)
		self.assertNotIn('DocType("Payment Ledger Entry")', source)
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn(".insert(", source)
		self.assertNotIn(".save(", source)
		self.assertNotIn(".submit(", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)
