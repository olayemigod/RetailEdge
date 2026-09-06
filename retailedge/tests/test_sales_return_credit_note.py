from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge import professional_sales_invoice as service


class TestSalesReturnCreditNote(FrappeTestCase):
	def _source(self, **overrides):
		values = {
			"company": "Test Company",
			"customer": "Test Customer",
			"branch": "Lagos",
			"is_return": 0,
			"is_consolidated": 0,
			"is_pos": 0,
		}
		values.update(overrides)
		source = MagicMock()
		source.name = "SINV-0001"
		source.docstatus = 1
		source.get.side_effect = values.get
		return source

	def _target(self, **overrides):
		values = {
			"is_return": 1,
			"return_against": "SINV-0001",
			"company": "Test Company",
			"customer": "Test Customer",
			"items": [{"qty": -1}],
			"branch": "Lagos",
			"retailedge_branch": "",
			"selling_price_list": "",
			"shipping_rule": "",
		}
		values.update(overrides)
		target = MagicMock()
		target.doctype = "Sales Invoice"
		target.name = "SINV-RET-0001"
		target.docstatus = 0
		target.company = values["company"]
		target.customer = values["customer"]
		target.grand_total = -1000
		target.currency = "NGN"
		target.get.side_effect = values.get
		return target

	def _call(self, source=None, target=None):
		source = source or self._source()
		target = target or self._target()
		with (
			patch.object(service, "_permission", return_value=True),
			patch.object(service, "_assert_read") as assert_read,
			patch.object(service.frappe, "get_doc", return_value=source),
			patch.object(service, "_validate_source_context", return_value=("Test Company", "Lagos")),
			patch.object(service, "erpnext_make_sales_return", return_value=target) as mapper,
			patch.object(service, "_validate_invoice_stock_context", return_value="Lagos") as validate_stock,
			patch.object(service, "_set_branch_if_supported") as set_branch,
		):
			result = service.create_sales_return_credit_note_draft("SINV-0001")
		return result, target, mapper, assert_read, validate_stock, set_branch

	def test_valid_source_uses_native_mapper_and_inserts_draft_only(self):
		result, target, mapper, assert_read, validate_stock, set_branch = self._call()

		assert_read.assert_called_once_with("Sales Invoice", "SINV-0001")
		mapper.assert_called_once_with("SINV-0001")
		validate_stock.assert_called_once_with(
			target,
			company="Test Company",
			source_branch="Lagos",
		)
		set_branch.assert_called_once_with(target, "Lagos")
		target.insert.assert_called_once_with()
		target.submit.assert_not_called()
		self.assertEqual(result["posting_status"], "Draft")
		self.assertTrue(result["is_return"])
		self.assertEqual(result["return_against"], "SINV-0001")
		self.assertEqual(result["source_doctype"], "Sales Invoice")
		self.assertEqual(result["route"], "/app/sales-invoice/SINV-RET-0001")

	def test_create_permission_is_required_before_read_or_mapper(self):
		with (
			patch.object(service, "_permission", return_value=False),
			patch.object(service, "_assert_read") as assert_read,
			patch.object(service, "erpnext_make_sales_return") as mapper,
			self.assertRaises(frappe.PermissionError),
		):
			service.create_sales_return_credit_note_draft("SINV-0001")
		assert_read.assert_not_called()
		mapper.assert_not_called()

	def test_source_read_permission_is_required_before_mapper(self):
		with (
			patch.object(service, "_permission", return_value=True),
			patch.object(service, "_assert_read", side_effect=frappe.PermissionError),
			patch.object(service, "erpnext_make_sales_return") as mapper,
			self.assertRaises(frappe.PermissionError),
		):
			service.create_sales_return_credit_note_draft("SINV-0001")
		mapper.assert_not_called()

	def test_draft_return_and_consolidated_pos_sources_are_rejected_before_mapper(self):
		cases = [
			("draft", self._source()),
			("return", self._source(is_return=1)),
			("consolidated-pos", self._source(is_consolidated=1, is_pos=1)),
		]
		cases[0][1].docstatus = 0
		for label, source in cases:
			with self.subTest(label=label):
				with (
					patch.object(service, "_permission", return_value=True),
					patch.object(service, "_assert_read"),
					patch.object(service.frappe, "get_doc", return_value=source),
					patch.object(service, "erpnext_make_sales_return") as mapper,
					self.assertRaises(frappe.ValidationError),
				):
					service.create_sales_return_credit_note_draft("SINV-0001")
				mapper.assert_not_called()

	def test_invalid_native_mapper_targets_are_rejected_before_insert(self):
		cases = {
			"wrong-doctype": {"doctype": "Credit Note"},
			"non-draft": {"docstatus": 1},
			"not-return": {"is_return": 0},
			"wrong-link": {"return_against": "SINV-OTHER"},
			"wrong-company": {"company": "Other Company"},
			"wrong-customer": {"customer": "Other Customer"},
			"no-negative-qty": {"items": [{"qty": 1}]},
		}
		for label, change in cases.items():
			with self.subTest(label=label):
				target = self._target(**{key: value for key, value in change.items() if key not in {"doctype", "docstatus"}})
				if "doctype" in change:
					target.doctype = change["doctype"]
				if "docstatus" in change:
					target.docstatus = change["docstatus"]
				with (
					patch.object(service, "_permission", return_value=True),
					patch.object(service, "_assert_read"),
					patch.object(service.frappe, "get_doc", return_value=self._source()),
					patch.object(service, "_validate_source_context", return_value=("Test Company", "Lagos")),
					patch.object(service, "erpnext_make_sales_return", return_value=target),
					patch.object(service, "_validate_invoice_stock_context") as validate_stock,
					self.assertRaises(frappe.ValidationError),
				):
					service.create_sales_return_credit_note_draft("SINV-0001")
				target.insert.assert_not_called()
				validate_stock.assert_not_called()

	def test_return_source_search_is_bounded_and_filters_return_documents(self):
		rows = [
			{"value": "SINV-0001", "description": "One"},
			{"value": "SINV-POS", "description": "POS"},
		]
		with (
			patch.object(service, "_permission", return_value=True),
			patch.object(service, "_validate_context", return_value=("Test Company", "Lagos", "")),
			patch.object(service, "_operating_document_filters", return_value={"company": "Test Company", "branch": "Lagos"}),
			patch.object(service, "search_link", return_value=rows) as search,
			patch.object(service.frappe, "get_all", return_value=["SINV-POS"]) as get_all,
		):
			result = service.search_professional_invoice_sources("return", txt="SINV", limit=20)

		self.assertEqual(result, [rows[0]])
		filters = search.call_args.kwargs["filters"]
		self.assertEqual(filters["docstatus"], 1)
		self.assertEqual(filters["is_return"], 0)
		self.assertEqual(filters["company"], "Test Company")
		self.assertEqual(filters["branch"], "Lagos")
		self.assertEqual(search.call_args.kwargs["page_length"], 100)
		self.assertEqual(search.call_args.kwargs["link_fieldname"], "return_against")
		get_all.assert_called_once()

	def test_source_contract_has_no_refund_or_ledger_write_path(self):
		source = open(service.__file__, encoding="utf-8").read()
		self.assertIn("erpnext_make_sales_return(source.name)", source)
		self.assertIn("target.insert()", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn('frappe.new_doc("Payment Entry")', source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)


if __name__ == "__main__":
	import unittest

	unittest.main()
