from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalPurchasingUIContract(TestCase):
	def test_standard_page_uses_governed_edgesuite_runtime(self):
		page_dir = APP_ROOT / "retailedge" / "page" / "professional_purchasing"
		page_json = (page_dir / "professional_purchasing.json").read_text()
		page_js = (page_dir / "professional_purchasing.js").read_text()
		bundle = (APP_ROOT / "public" / "js" / "professional_purchasing.bundle.js").read_text()

		self.assertIn('"page_name": "professional-purchasing"', page_json)
		self.assertIn('"standard": "Yes"', page_json)
		self.assertIn('"role": "Purchase Manager"', page_json)
		self.assertIn('"role": "Purchase User"', page_json)
		self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', page_js)
		self.assertIn('const PURCHASING_ASSET = "professional_purchasing.bundle.js"', page_js)
		self.assertIn("window.EdgeSuiteUI?.components", page_js)
		self.assertIn("window.mountRetailEdgeProfessionalPurchasing", page_js)
		self.assertIn("edgeUI.createEdgeApp(ProfessionalPurchasing)", bundle)
		self.assertNotIn("window.EdgeUI", page_js + bundle)

	def test_workspace_uses_native_sourcing_and_receipt_services_inside_edgesuite(self):
		component = (APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text()

		self.assertIn("retailedge.professional_purchasing.get_professional_purchasing_context", component)
		self.assertIn("retailedge.professional_purchasing.search_professional_purchasing_options", component)
		self.assertIn("retailedge.professional_purchasing.prepare_request_for_quotation_draft", component)
		self.assertIn("retailedge.professional_purchasing.prepare_purchase_receipt_draft", component)
		self.assertIn("EdgeLinkField", component)
		self.assertIn("companySearch", component)
		self.assertIn("branchSearch", component)
		self.assertIn("supplierSearch", component)
		self.assertIn("rfqSupplierSearch", component)
		self.assertIn("Purchase Material Requests", component)
		self.assertIn("Start RFQ", component)
		self.assertIn("Prepare Draft RFQ", component)
		self.assertIn("send_email", (APP_ROOT / "professional_purchasing.py").read_text())
		self.assertIn('frappe.set_route("Form", "Request for Quotation", result.name)', component)
		self.assertIn('frappe.set_route("query-report", "Supplier Quotation Comparison")', component)
		self.assertIn("Prepare Receipt", component)
		self.assertIn("sortBy('per_received')", component)
		self.assertIn("sortMaterialBy('per_ordered')", component)
		self.assertIn("frappe.new_doc(\"Purchase Order\")", component)
		self.assertIn('frappe.set_route("Form", "Purchase Receipt", result.name)', component)

		# New operational UX must remain inside the EdgeSuite page rather than opening
		# a parallel Frappe dialog/prompt/toast workflow.
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("frappe.msgprint", component)
		self.assertNotIn("frappe.show_alert", component)
		self.assertNotIn("window.EdgeUI", component)

	def test_backend_is_draft_first_and_does_not_write_ledgers_or_bypass_supplier_validation(self):
		source = (APP_ROOT / "professional_purchasing.py").read_text()

		self.assertIn("make_request_for_quotation(request.name)", source)
		self.assertIn('rfq.append("suppliers", {"supplier": supplier, "send_email": 0})', source)
		self.assertIn("rfq.insert()", source)
		self.assertIn("make_purchase_receipt(po.name)", source)
		self.assertIn("receipt.insert()", source)
		self.assertIn('"posting_status": "Draft"', source)
		self.assertIn("validate_user_branch_access", source)
		self.assertIn("MAX_RFQ_SUPPLIERS = 20", source)
		self.assertNotIn(".submit(", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)

	def test_business_hub_promotes_page_without_removing_native_buying_routes(self):
		source = (APP_ROOT / "master_experience.py").read_text()

		self.assertIn('"target": "professional-purchasing"', source)
		self.assertIn("def _promote_professional_purchasing", source)
		self.assertIn('group.get("key") != "buy"', source)
		self.assertIn('item.get("target") == "Purchase Order"', source)
		self.assertIn("_promote_professional_purchasing(navigation_groups)", source)
		self.assertIn('feature_flags["professional_purchasing"] = "erpnext_native_po_receipt"', source)
		self.assertNotIn('item["target"] = PROFESSIONAL_PURCHASING_ITEM["target"]', source)


if __name__ == "__main__":
	import unittest

	unittest.main()
