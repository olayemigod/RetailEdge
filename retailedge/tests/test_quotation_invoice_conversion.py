from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestQuotationInvoiceConversion(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_registry_is_unique_per_quotation_and_auditable(self):
		definition = json.loads(self.read("retailedge/doctype/retailedge_quotation_invoice_conversion/retailedge_quotation_invoice_conversion.json"))
		self.assertEqual(definition["name"], "RetailEdge Quotation Invoice Conversion")
		self.assertEqual(definition["autoname"], "field:quotation")
		fields = {row["fieldname"]: row for row in definition["fields"]}
		self.assertEqual(fields["quotation"].get("unique"), 1)
		self.assertEqual(fields["quotation"].get("options"), "Quotation")
		self.assertEqual(fields["sales_invoice"].get("fieldtype"), "Data")
		self.assertIsNone(fields["sales_invoice"].get("options"))
		self.assertEqual(fields["converted_by"].get("options"), "User")
		self.assertEqual(fields["converted_on"].get("fieldtype"), "Datetime")

	def test_registry_internal_writes_do_not_narrow_erpnext_custom_roles(self):
		definition = json.loads(self.read("retailedge/doctype/retailedge_quotation_invoice_conversion/retailedge_quotation_invoice_conversion.json"))
		all_role = next(row for row in definition["permissions"] if row.get("role") == "All")
		self.assertEqual(all_role.get("create"), 1)
		self.assertEqual(all_role.get("write"), 1)
		self.assertEqual(all_role.get("delete"), 1)
		self.assertFalse(bool(all_role.get("read")))
		controller = self.read("retailedge/doctype/retailedge_quotation_invoice_conversion/retailedge_quotation_invoice_conversion.py")
		self.assertIn("conversion_write_authorized()", controller)

	def test_registry_blocks_manual_mutation(self):
		controller = self.read("retailedge/doctype/retailedge_quotation_invoice_conversion/retailedge_quotation_invoice_conversion.py")
		self.assertIn("conversion_write_authorized()", controller)
		self.assertIn("cannot be edited manually", controller)
		self.assertIn("cannot be deleted manually", controller)
		self.assertIn("Only submitted Quotations", controller)
		self.assertIn("Quotation Company does not match", controller)

	def test_registry_reservation_is_transactional_and_race_safe(self):
		source = self.read("quotation_invoice_conversion.py")
		for contract in ("reserve_quotation_conversion", "frappe.DuplicateEntryError", "tracker.insert()", "complete_quotation_conversion", "tracker.save()", "no manual commit is performed"):
			self.assertIn(contract, source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_deleted_draft_can_retire_stale_registry_without_weakening_cancelled_invoice_safety(self):
		source = self.read("quotation_invoice_conversion.py")
		exists_check = source.index('frappe.db.exists("Sales Invoice", sales_invoice)')
		stale_delete = source.index('frappe.get_doc(CONVERSION_DOCTYPE, existing["name"]).delete()', exists_check)
		reserve_insert = source.index("tracker.insert()", stale_delete)
		self.assertLess(exists_check, stale_delete)
		self.assertLess(stale_delete, reserve_insert)
		self.assertIn("use ERPNext Amend", source)

	def test_direct_invoice_reserves_before_invoice_insert_and_completes_after(self):
		source = self.read("professional_sales_invoice.py")
		reserve = source.index("tracker = reserve_quotation_conversion")
		insert = source.index("target.insert()", reserve)
		complete = source.index("complete_quotation_conversion(tracker, target.name)", insert)
		self.assertLess(reserve, insert)
		self.assertLess(insert, complete)
		self.assertIn("same request transaction", source)

	def test_converted_quotations_are_removed_from_smart_source_search(self):
		source = self.read("professional_sales_invoice.py")
		registry = self.read("quotation_invoice_conversion.py")
		self.assertIn("filter_unconverted_quotation_results", source)
		self.assertIn("page_length = min(max(limit * 5, limit), 100)", source)
		self.assertIn("quotation_has_conversion", registry)
		self.assertIn("len(results) >= limit", registry)

	def test_missing_migration_fails_closed(self):
		source = self.read("quotation_invoice_conversion.py")
		self.assertIn("assert_conversion_registry_available", source)
		self.assertIn("Run bench migrate", source)


if __name__ == "__main__":
	unittest.main()
