from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_customer import (
	MAX_LINK_RESULTS,
	create_simple_customer,
	get_simple_customer_context,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _DraftCustomer(SimpleNamespace):
	doctype = "Customer"

	def __init__(self):
		super().__init__(name="CUST-0001", insert_calls=0)

	def insert(self):
		self.insert_calls += 1
		return self


class _CustomerMeta:
	@staticmethod
	def has_field(fieldname):
		return fieldname in {"mobile_no", "email_id", "tax_id"}


class TestGuidedCustomer(unittest.TestCase):
	@patch("retailedge.guided_customer._default_territory", return_value="All Territories")
	@patch("retailedge.guided_customer._default_customer_group", return_value="All Customer Groups")
	@patch("retailedge.guided_customer._assert_can_create_customer")
	def test_context_uses_erpnext_defaults(self, _permission, _group, _territory):
		context = get_simple_customer_context()
		self.assertEqual(context["defaults"]["customer_group"], "All Customer Groups")
		self.assertEqual(context["defaults"]["territory"], "All Territories")
		self.assertEqual(context["limits"]["link_results"], MAX_LINK_RESULTS)

	@patch("retailedge.guided_customer.frappe.get_meta", return_value=_CustomerMeta())
	@patch("retailedge.guided_customer._validate_leaf_master")
	@patch("retailedge.guided_customer._assert_read_permission")
	@patch("retailedge.guided_customer._default_territory", return_value="All Territories")
	@patch("retailedge.guided_customer._default_customer_group", return_value="All Customer Groups")
	@patch("retailedge.guided_customer._assert_can_create_customer")
	@patch("retailedge.guided_customer.frappe.new_doc")
	def test_customer_creation_uses_native_customer_document(
		self,
		mock_new_doc,
		_permission,
		_group,
		_territory,
		_read,
		_leaf,
		_meta,
	):
		doc = _DraftCustomer()
		mock_new_doc.return_value = doc
		result = create_simple_customer(
			{
				"customer_name": "Acme Retail Ltd",
				"customer_type": "Company",
				"customer_group": "Commercial",
				"territory": "Lagos",
				"mobile_no": "08000000000",
				"email_id": "accounts@example.com",
			}
		)

		self.assertEqual(doc.customer_name, "Acme Retail Ltd")
		self.assertEqual(doc.customer_group, "Commercial")
		self.assertEqual(doc.territory, "Lagos")
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(result["doctype"], "Customer")
		self.assertEqual(result["name"], "CUST-0001")

	@patch("retailedge.guided_customer._assert_can_create_customer")
	def test_invalid_customer_type_is_rejected(self, _permission):
		with self.assertRaises(frappe.ValidationError):
			create_simple_customer({"customer_name": "Bad Type", "customer_type": "Unknown"})

	def test_backend_and_dialog_contract_is_permission_aware_and_bounded(self):
		backend = (APP_ROOT / "guided_customer.py").read_text(encoding="utf-8")
		dialog = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleCustomerDialog.vue"
		).read_text(encoding="utf-8")
		self.assertIn("MAX_LINK_RESULTS = 20", backend)
		self.assertIn('frappe.has_permission(CUSTOMER_DOCTYPE, "create")', backend)
		self.assertIn("doc.insert()", backend)
		self.assertNotIn("ignore_permissions=True", backend)
		self.assertNotIn(".submit()", backend)
		self.assertIn("Open Full Form", dialog)
		self.assertIn("searchCustomerGroup", dialog)
		self.assertIn("searchTerritory", dialog)


if __name__ == "__main__":
	unittest.main()
