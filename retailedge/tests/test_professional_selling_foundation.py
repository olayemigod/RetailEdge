from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalSellingFoundation(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_registry_keeps_quote_order_delivery_together(self):
		source = self.read("professional_selling.py")
		for contract in (
			'"doctype": "Quotation"',
			'"doctype": "Sales Order"',
			'"doctype": "Delivery Note"',
			'"stage": "Quote"',
			'"stage": "Order"',
			'"stage": "Delivery"',
			'"supports_shipping_rule": True',
		):
			self.assertIn(contract, source)

	def test_context_is_read_only_and_permission_aware(self):
		source = self.read("professional_selling.py")
		for contract in (
			"get_operating_context",
			"resolve_price_list_context",
			"frappe.has_permission",
			"frappe.get_list",
			"get_user_fullname(frappe.session.user)",
			'"policy": "erpnext_native"',
			'"draft_first": True',
			'"submitted_documents_immutable": True',
		):
			self.assertIn(contract, source)
		for forbidden in (
			"ignore_permissions=True",
			"frappe.get_all",
			"frappe.db.commit",
			"frappe.new_doc",
			".insert()",
			".save()",
			".submit()",
			"frappe.db.set_value",
			"frappe.get_user().get_fullname()",
		):
			self.assertNotIn(forbidden, source)

	def test_recent_records_are_bounded(self):
		source = self.read("professional_selling.py")
		self.assertIn("min(int(limit or 8), 20)", source)
		self.assertIn("limit_page_length=limit", source)
		# Recent-document access goes through the shared permission helper;
		# _permission itself is covered above as the frappe.has_permission path.
		self.assertIn('_permission(doctype, "read")', source)

	def test_page_uses_edgesuite_single_shell(self):
		loader = self.read("retailedge/page/professional_selling/professional_selling.js")
		bundle = self.read("public/js/professional_selling.bundle.js")
		component = self.read("public/js/professional_selling/ProfessionalSelling.vue")
		for contract in ("edgeui.bundle.js", "professional_selling.bundle.js"):
			self.assertIn(contract, loader)
		self.assertIn("createEdgeApp", bundle)
		for contract in (
			"EdgeAppShell",
			"EdgePageLayout",
			"EdgePageHeader",
			"EdgeLoadingState",
			"EdgeErrorState",
			'activeRoute="/app/professional-selling"',
		):
			self.assertIn(contract, component)
		self.assertNotIn("<iframe", component.lower())
		self.assertNotIn("frappe-card", component)

	def test_ui_preserves_erpnext_shipping_and_native_document_truth(self):
		component = self.read("public/js/professional_selling/ProfessionalSelling.vue")
		for contract in (
			"ERPNext pricing, taxes, Shipping Rules, stock and accounting remain authoritative",
			"Selling Price List",
			"Shipping Rule",
			"createNative(document)",
			"openNative(document)",
		):
			self.assertIn(contract, component)
		for forbidden in (
			"frappe.client.insert",
			"frappe.client.save",
			"shipping_charge_ledger",
			"delivery_charge_ledger",
		):
			self.assertNotIn(forbidden, component)


if __name__ == "__main__":
	unittest.main()
