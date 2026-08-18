from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_supplier import (
	MAX_LINK_RESULTS,
	create_simple_supplier,
	get_simple_supplier_context,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _DraftSupplier(SimpleNamespace):
	doctype = "Supplier"

	def __init__(self):
		super().__init__(name="SUPP-0001", insert_calls=0)

	def insert(self):
		self.insert_calls += 1
		return self


class _SupplierMeta:
	@staticmethod
	def has_field(fieldname):
		return fieldname in {"mobile_no", "email_id", "tax_id"}


class TestGuidedSupplier(unittest.TestCase):
	@patch("retailedge.guided_supplier._default_supplier_group", return_value="All Supplier Groups")
	@patch("retailedge.guided_supplier._assert_can_create_supplier")
	def test_context_uses_erpnext_default(self, _permission, _group):
		context = get_simple_supplier_context()
		self.assertEqual(context["defaults"]["supplier_group"], "All Supplier Groups")
		self.assertEqual(context["limits"]["link_results"], MAX_LINK_RESULTS)

	@patch("retailedge.guided_supplier.frappe.get_meta", return_value=_SupplierMeta())
	@patch("retailedge.guided_supplier._validate_leaf_master")
	@patch("retailedge.guided_supplier._assert_read_permission")
	@patch("retailedge.guided_supplier._default_supplier_group", return_value="All Supplier Groups")
	@patch("retailedge.guided_supplier._assert_can_create_supplier")
	@patch("retailedge.guided_supplier.frappe.new_doc")
	def test_supplier_creation_uses_native_supplier_document(
		self,
		mock_new_doc,
		_permission,
		_group,
		_read,
		_leaf,
		_meta,
	):
		doc = _DraftSupplier()
		mock_new_doc.return_value = doc
		result = create_simple_supplier(
			{
				"supplier_name": "Acme Supply Ltd",
				"supplier_type": "Company",
				"supplier_group": "Local Suppliers",
				"mobile_no": "08000000000",
				"email_id": "accounts@example.com",
			}
		)

		self.assertEqual(doc.supplier_name, "Acme Supply Ltd")
		self.assertEqual(doc.supplier_group, "Local Suppliers")
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(result["doctype"], "Supplier")
		self.assertEqual(result["name"], "SUPP-0001")

	@patch("retailedge.guided_supplier._assert_can_create_supplier")
	def test_invalid_supplier_type_is_rejected(self, _permission):
		with self.assertRaises(frappe.ValidationError):
			create_simple_supplier({"supplier_name": "Bad Type", "supplier_type": "Unknown"})

	def test_backend_and_dialog_contract_is_permission_aware_and_bounded(self):
		backend = (APP_ROOT / "guided_supplier.py").read_text(encoding="utf-8")
		dialog = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleSupplierDialog.vue"
		).read_text(encoding="utf-8")
		self.assertIn("MAX_LINK_RESULTS = 20", backend)
		self.assertIn('frappe.has_permission(SUPPLIER_DOCTYPE, "create")', backend)
		self.assertIn("doc.insert()", backend)
		self.assertNotIn("ignore_permissions=True", backend)
		self.assertNotIn(".submit()", backend)
		self.assertIn("Open Full Form", dialog)
		self.assertIn("searchSupplierGroup", dialog)


if __name__ == "__main__":
	unittest.main()
