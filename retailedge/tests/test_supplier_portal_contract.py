from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestSupplierPortalContract(unittest.TestCase):
	def test_supplier_identity_is_server_derived_and_native_routes_are_reused(self):
		source = (APP_ROOT / "supplier_portal.py").read_text()
		self.assertIn('get_parents_for_user("Supplier")', source)
		self.assertIn('"Supplier" not in frappe.get_roles', source)
		self.assertIn("get_transaction_list", source)
		for doctype in ("Request for Quotation", "Supplier Quotation", "Purchase Order", "Purchase Invoice"):
			self.assertIn(doctype, source)
		for route in ("/rfq", "/supplier-quotations", "/purchase-orders", "/purchase-invoices"):
			self.assertIn(route, source)
		self.assertNotIn("GL Entry", source)
		self.assertNotIn("Stock Ledger Entry", source)

	def test_purchase_order_activity_is_append_only_and_rechecks_native_permission(self):
		source = (APP_ROOT / "supplier_portal_collaboration.py").read_text()
		self.assertIn("has_website_permission", source)
		self.assertIn("purchase_order.supplier not in suppliers", source)
		self.assertIn("purchase_order.docstatus != 1", source)
		self.assertIn("for update", source)
		self.assertIn('frappe.whitelist(methods=["POST"])', source)
		self.assertIn('"purchase_order_mutated": False', source)
		self.assertIn("activity.insert(ignore_permissions=True)", source)
		self.assertNotIn("purchase_order.save", source)
		self.assertNotIn("frappe.db.set_value", source)

	def test_supplier_activity_doctype_is_immutable_and_not_portal_writable(self):
		controller = (APP_ROOT / "retailedge" / "doctype" / "supplier_portal_activity" / "supplier_portal_activity.py").read_text()
		schema = (APP_ROOT / "retailedge" / "doctype" / "supplier_portal_activity" / "supplier_portal_activity.json").read_text()
		self.assertIn("Supplier portal activity records are immutable.", controller)
		self.assertIn("supplier_portal_activity_api_write", controller)
		self.assertIn('self.reference_doctype != "Purchase Order"', controller)
		self.assertNotIn('"role":"Supplier"', schema)
		self.assertIn('"Purchase Manager"', schema)
		self.assertIn('"Purchase User"', schema)

	def test_supplier_financial_context_is_read_only_and_supplier_scoped(self):
		source = (APP_ROOT / "supplier_portal_financial.py").read_text()
		self.assertIn('"account_type": "Payable"', source)
		self.assertIn('"party_type": "Supplier"', source)
		self.assertIn('"supplier": ["in", suppliers]', source)
		self.assertIn('"party": ["in", suppliers]', source)
		self.assertIn('"docstatus": 1', source)
		self.assertIn('"payment_type": "Pay"', source)
		self.assertIn('"read_only": True', source)
		self.assertNotIn("frappe.new_doc", source)
		self.assertNotIn("frappe.db.set_value", source)
		self.assertNotIn("GL Entry", source)
		self.assertNotIn("Stock Ledger Entry", source)

	def test_supplier_portal_menu_is_additive_and_migrated(self):
		source = (APP_ROOT / "supplier_portal_setup.py").read_text()
		patches = (APP_ROOT / "patches.txt").read_text()
		self.assertIn('SUPPLIER_PORTAL_ROUTE = "/supplier_portal"', source)
		self.assertIn('"role": "Supplier"', source)
		self.assertIn("settings.append(", source)
		self.assertNotIn('settings.set("menu"', source)
		self.assertIn("retailedge.patches.install_supplier_portal_menu", patches)

	def test_supplier_ui_is_product_neutral_and_edgesuite_ready(self):
		template = (APP_ROOT / "www" / "supplier_portal.html").read_text()
		statement = (APP_ROOT / "www" / "supplier_account_statement.html").read_text()
		self.assertIn('data-edge-suite-ready="true"', template)
		self.assertIn("ERPNext remains the transaction authority", template)
		self.assertIn("never change submitted Purchase Orders", template)
		self.assertIn("read-only ERPNext accounting data", template)
		self.assertIn('data-edge-suite-ready="true"', statement)
		self.assertIn("Payment Ledger Entry", statement)
		self.assertNotIn("RetailEdge", template)
		self.assertNotIn("ProcessEdge", template)
		self.assertNotIn("RetailEdge", statement)
		self.assertNotIn("ProcessEdge", statement)


if __name__ == "__main__":
	unittest.main()
