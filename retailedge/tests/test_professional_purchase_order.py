from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalPurchaseOrder(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_backend_creates_only_standard_draft_purchase_order(self):
		source = self.read("professional_purchase_order.py")
		for contract in (
			"create_professional_purchase_order_draft",
			'frappe.new_doc(PURCHASE_ORDER_DOCTYPE)',
			"_assert_can_create_purchase_order()",
			"_validate_purchase_order_context(values, user=user)",
			"_normalise_items(values.get(\"items\"))",
			"resolve_price_list_context",
			"resolve_purchase_item_pricing",
			"doc.insert()",
			"cint(doc.docstatus) != 0",
		):
			self.assertIn(contract, source)
		for forbidden in (
			"doc.submit()",
			"ignore_permissions=True",
			"frappe.db.commit",
			"frappe.db.set_value",
			"Stock Ledger Entry",
			"GL Entry",
		):
			self.assertNotIn(forbidden, source)

	def test_backend_reuses_existing_buying_scope_pricing_and_item_contracts(self):
		source = self.read("professional_purchase_order.py")
		for contract in (
			"from retailedge.guided_purchase_invoice import",
			"_branch_search_filters",
			"_warehouse_search_filters",
			"_validate_transaction_context",
			"_normalise_items",
			"resolve_purchase_item_pricing",
			'reference_doctype=PURCHASE_ORDER_ITEM_DOCTYPE',
			'filters: dict[str, Any] = {"is_purchase_item": 1, "disabled": 0}',
		):
			self.assertIn(contract, source)

	def test_branch_and_required_date_are_validated_server_side(self):
		source = self.read("professional_purchase_order.py")
		for contract in (
			"resolve_branch_from_warehouse",
			"user_has_global_branch_access",
			"get_user_allowed_branches",
			"validate_user_branch_access",
			"Choose a permitted Branch before creating a Purchase Order.",
			"clearing Branch on the client cannot weaken scope",
			"get_first_existing_field(PURCHASE_ORDER_DOCTYPE, BRANCH_FIELD_CANDIDATES)",
			"Required By date cannot be before the Order Date.",
			'"schedule_date": schedule_date',
		):
			self.assertIn(contract, source)

	def test_dialog_is_edgesuite_guided_and_keeps_native_fallback_optional(self):
		source = self.read("public/js/professional_purchasing/ProfessionalPurchaseOrderDialog.vue")
		for contract in (
			"EdgeModal",
			"EdgeLinkField",
			"EdgeChildTable",
			"search_professional_purchase_order_options",
			"get_professional_purchase_order_item_pricing",
			"create_professional_purchase_order_draft",
			'preference: "purchase"',
			"nativeFallbackEnabled",
		):
			self.assertIn(contract, source)
		self.assertNotIn('frappe.new_doc("Purchase Order")', source)
		self.assertNotIn("frappe.set_route", source)

	def test_edgesuite_only_overlay_disables_native_full_form_fallback(self):
		source = self.read("public/js/professional_purchasing/ProfessionalPurchaseOrderOverlay.vue")
		self.assertIn('frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE', source)
		self.assertIn('const ACCESS_MODE = "edgesuite_only"', source)
		self.assertIn('frappe.new_doc("Purchase Order")', source)
		self.assertIn("if (!this.nativeFallbackEnabled) return;", source)
		self.assertIn('retailedge-professional-purchasing-page-show', source)

	def test_page_controller_promotes_existing_new_po_action_to_guided_overlay(self):
		source = self.read("retailedge/page/professional_purchasing/professional_purchasing.js")
		for contract in (
			'PURCHASE_ORDER_ASSET = "professional_purchase_order.bundle.js"',
			'PURCHASE_ORDER_TRIGGER_LABEL = "New Purchase Order"',
			"installGuidedPurchaseOrderTrigger(wrapper, root)",
			"event.stopImmediatePropagation()",
			"OPEN_PURCHASE_ORDER_EVENT",
			"mountRetailEdgeProfessionalPurchaseOrder",
		):
			self.assertIn(contract, source)
		self.assertNotIn('frappe.new_doc("Purchase Order")', source)

	def test_purchase_order_bundle_is_product_local_and_compiled(self):
		source = self.read("public/js/professional_purchase_order.bundle.js")
		self.assertIn('ProfessionalPurchaseOrderOverlay.vue', source)
		self.assertIn("window.mountRetailEdgeProfessionalPurchaseOrder", source)
		self.assertIn("edgeUI.createEdgeApp", source)

	def test_professional_purchasing_page_roles_are_not_broadened(self):
		page = self.read("retailedge/page/professional_purchasing/professional_purchasing.json")
		for role in ("System Manager", "Purchase User", "Purchase Manager", "Accounts User", "Accounts Manager"):
			self.assertIn(role, page)
		self.assertNotIn("RetailEdge Branch Manager", page)
		self.assertNotIn("RetailEdge Manager", page)


if __name__ == "__main__":
	unittest.main()
