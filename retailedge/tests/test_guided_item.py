from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.guided_item import MAX_LINK_RESULTS, create_simple_item, get_simple_item_context

APP_ROOT = Path(__file__).resolve().parents[1]


class _DraftItem(SimpleNamespace):
	doctype = "Item"

	def __init__(self):
		super().__init__(name="ITEM-0001", insert_calls=0, appended=[])

	def append(self, fieldname, value):
		self.appended.append((fieldname, value))

	def insert(self):
		self.insert_calls += 1
		return self


class _ItemMeta:
	@staticmethod
	def has_field(fieldname):
		return fieldname in {"description", "barcodes"}


class TestGuidedItem(unittest.TestCase):
	@patch("retailedge.guided_item._default_stock_uom", return_value="Nos")
	@patch("retailedge.guided_item._default_item_group", return_value="Products")
	@patch("retailedge.guided_item._assert_can_create_item")
	def test_context_excludes_cost_and_pricing_fields(self, _permission, _group, _uom):
		context = get_simple_item_context()
		self.assertEqual(context["defaults"]["item_group"], "Products")
		self.assertEqual(context["defaults"]["stock_uom"], "Nos")
		self.assertEqual(context["limits"]["link_results"], MAX_LINK_RESULTS)
		self.assertFalse(context["capabilities"]["cost_fields_exposed"])
		self.assertFalse(context["capabilities"]["pricing_fields_exposed"])

	@patch("retailedge.guided_item.frappe.get_meta", return_value=_ItemMeta())
	@patch("retailedge.guided_item._validate_uom")
	@patch("retailedge.guided_item._validate_leaf_item_group")
	@patch("retailedge.guided_item._assert_read_permission")
	@patch("retailedge.guided_item._default_stock_uom", return_value="Nos")
	@patch("retailedge.guided_item._default_item_group", return_value="Products")
	@patch("retailedge.guided_item._assert_can_create_item")
	@patch("retailedge.guided_item.frappe.new_doc")
	def test_item_creation_uses_one_native_insert(
		self,
		mock_new_doc,
		_permission,
		_group,
		_uom,
		_read,
		_leaf,
		_validate_uom,
		_meta,
	):
		doc = _DraftItem()
		mock_new_doc.return_value = doc
		result = create_simple_item(
			{
				"item_code": "SKU-001",
				"item_name": "Retail Product",
				"is_stock_item": 1,
				"item_group": "Products",
				"stock_uom": "Nos",
				"barcode": "1234567890",
			}
		)
		self.assertEqual(doc.item_code, "SKU-001")
		self.assertEqual(doc.item_group, "Products")
		self.assertEqual(doc.stock_uom, "Nos")
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(doc.appended, [("barcodes", {"barcode": "1234567890"})])
		self.assertEqual(result["doctype"], "Item")

	def test_backend_and_dialog_never_expose_cost_or_valuation_fields(self):
		backend = (APP_ROOT / "guided_item.py").read_text(encoding="utf-8")
		dialog = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleItemDialog.vue"
		).read_text(encoding="utf-8")
		self.assertIn("MAX_LINK_RESULTS = 20", backend)
		self.assertIn('frappe.has_permission(ITEM_DOCTYPE, "create")', backend)
		self.assertNotIn("ignore_permissions=True", backend)
		self.assertNotIn("valuation_rate", backend)
		self.assertNotIn("last_purchase_rate", backend)
		self.assertNotIn("buying_price", backend)
		self.assertNotIn("valuation_rate", dialog)
		self.assertNotIn("last_purchase_rate", dialog)
		self.assertIn("Cost, valuation and buying-price fields are intentionally excluded", dialog)
		self.assertIn("Open Full Form", dialog)


if __name__ == "__main__":
	unittest.main()
