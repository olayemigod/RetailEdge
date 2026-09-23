from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPriceListGovernanceContract(unittest.TestCase):
	def test_branch_setup_owns_default_selling_and_buying_price_lists(self):
		definition = json.loads(
			(APP_ROOT / "retailedge" / "doctype" / "retailedge_branch_profile" / "retailedge_branch_profile.json").read_text(encoding="utf-8")
		)
		fields = {row["fieldname"]: row for row in definition["fields"]}
		self.assertEqual(fields["default_selling_price_list"]["options"], "Price List")
		self.assertEqual(fields["default_buying_price_list"]["options"], "Price List")

		service = (APP_ROOT / "branch_setup.py").read_text(encoding="utf-8")
		page = (APP_ROOT / "public" / "js" / "branch_setup" / "BranchSetup.vue").read_text(encoding="utf-8")
		for fieldname in ("default_selling_price_list", "default_buying_price_list"):
			self.assertIn(fieldname, service)
			self.assertIn(fieldname, page)
		self.assertIn('key: "pricing"', page)
		self.assertIn("Branch defaults take precedence", page)

	def test_branch_assignment_can_allocate_multiple_price_lists(self):
		definition = json.loads(
			(APP_ROOT / "retailedge" / "doctype" / "retailedge_branch_assignment" / "retailedge_branch_assignment.json").read_text(encoding="utf-8")
		)
		fields = {row["fieldname"]: row for row in definition["fields"]}
		self.assertEqual(fields["allowed_price_lists"]["fieldtype"], "Table")
		self.assertEqual(fields["allowed_price_lists"]["options"], "RetailEdge Branch Assignment Price List")

		child = json.loads(
			(APP_ROOT / "retailedge" / "doctype" / "retailedge_branch_assignment_price_list" / "retailedge_branch_assignment_price_list.json").read_text(encoding="utf-8")
		)
		child_fields = {row["fieldname"]: row for row in child["fields"]}
		self.assertEqual(child_fields["price_list"]["options"], "Price List")
		self.assertEqual(child.get("istable"), 1)

	def test_pricing_precedence_is_branch_default_then_governed_selection_then_defaults(self):
		source = (APP_ROOT / "guided_pricing.py").read_text(encoding="utf-8")
		branch_index = source.index("if branch_default:")
		selected_index = source.index("if selected_price_list:")
		user_default_index = source.index("for key in USER_DEFAULT_KEYS[mode]:")
		self.assertLess(branch_index, selected_index)
		self.assertLess(selected_index, user_default_index)
		for contract in (
			'"source": "branch_default"',
			'"source": "user_selected"',
			'"selection_required": True',
			"get_branch_assignment_price_lists",
			"selected_price_list not in selectable",
			"require_read=selected_price_list not in assigned_price_lists",
		):
			self.assertIn(contract, source)

	def test_branch_assignment_extends_existing_default_instead_of_replacing_it(self):
		source = (APP_ROOT / "guided_pricing.py").read_text(encoding="utf-8")
		self.assertIn("default_candidate = _default_price_list_candidate(", source)
		self.assertIn("[*assigned_price_lists, *([default_name] if default_name else [])]", source)
		self.assertIn('"can_select": bool(assigned_price_lists) and not locked', source)
		self.assertIn('"allowed_price_lists": selectable', source)

	def test_all_primary_sales_and_purchase_entry_surfaces_expose_price_list_selection(self):
		surfaces = {
			"Quick Sale": APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleSalesInvoiceDialog.vue",
			"Make Sale": APP_ROOT / "public" / "js" / "make_sale" / "MakeSale.vue",
			"Quick Purchase": APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePurchaseInvoiceDialog.vue",
			"Record Purchase": APP_ROOT / "public" / "js" / "record_purchase" / "RecordPurchase.vue",
			"Quotation": APP_ROOT / "public" / "js" / "professional_selling" / "ProfessionalQuotationDialog.vue",
			"Sales Order": APP_ROOT / "public" / "js" / "professional_selling" / "ProfessionalSalesOrderDialog.vue",
			"Sales Invoice": APP_ROOT / "public" / "js" / "professional_selling" / "ProfessionalSalesInvoiceDialog.vue",
			"Purchase Order": APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchaseOrderDialog.vue",
		}
		for label, path in surfaces.items():
			source = path.read_text(encoding="utf-8")
			self.assertIn("Price List", source, label)
			self.assertIn("searchPriceList", source, label)
			self.assertIn("setPriceList", source, label)
			self.assertIn("price_list", source, label)
			self.assertIn("refreshAllItemPricing", source, label)

	def test_server_creation_paths_revalidate_selected_price_list(self):
		services = (
			APP_ROOT / "guided_sales_invoice.py",
			APP_ROOT / "guided_purchase_invoice.py",
			APP_ROOT / "professional_quotation.py",
			APP_ROOT / "professional_sales_order.py",
			APP_ROOT / "professional_purchase_order.py",
		)
		for path in services:
			source = path.read_text(encoding="utf-8")
			self.assertIn("selected_price_list=", source, path.name)
			self.assertIn("selection_required", source, path.name)
			self.assertNotIn("ignore_permissions=True", source, path.name)

		# Professional Sales Invoice delegates new-invoice creation to the governed Sales Invoice engine.
		invoice = (APP_ROOT / "professional_sales_invoice.py").read_text(encoding="utf-8")
		self.assertIn("create_simple_sales_invoice_draft(values)", invoice)

	def test_delivery_and_receipt_workflows_inherit_submitted_source_pricing(self):
		delivery = (APP_ROOT / "professional_delivery.py").read_text(encoding="utf-8")
		receipt = (APP_ROOT / "professional_purchase_receipt.py").read_text(encoding="utf-8")
		self.assertIn("erpnext_make_delivery_note(source.name)", delivery)
		self.assertIn("erpnext_make_delivery_note_from_invoice(source.name)", delivery)
		self.assertNotIn("resolve_sales_item_pricing(", delivery)
		self.assertIn("make_purchase_receipt(po.name)", receipt)
		self.assertNotIn("resolve_purchase_item_pricing(", receipt)

	def test_conversion_flows_do_not_reprice_accepted_source_documents(self):
		order_dialog = (APP_ROOT / "public" / "js" / "professional_selling" / "ProfessionalSalesOrderDialog.vue").read_text(encoding="utf-8")
		invoice_dialog = (APP_ROOT / "public" / "js" / "professional_selling" / "ProfessionalSalesInvoiceDialog.vue").read_text(encoding="utf-8")
		self.assertIn('v-if="mode === \'new\'"', order_dialog)
		self.assertIn('v-if="mode === \'new\'"', invoice_dialog)
		invoice_backend = (APP_ROOT / "professional_sales_invoice.py").read_text(encoding="utf-8")
		self.assertIn("_copy_quotation_commercial_terms", invoice_backend)
		self.assertIn('"selling_price_list"', invoice_backend)


if __name__ == "__main__":
	unittest.main()
