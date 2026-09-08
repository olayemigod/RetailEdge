from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


class TestRIR2F2CPurchaseReceiptParityGate(unittest.TestCase):
	def read_app(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_current_receipt_workflow_still_requires_native_completion(self):
		component = self.read_app("public/js/professional_purchasing/ProfessionalPurchasing.vue")
		self.assertIn("retailedge.professional_purchasing.prepare_purchase_receipt_draft", component)
		self.assertIn('frappe.set_route("Form", "Purchase Receipt", result.name)', component)
		self.assertIn('openPurchaseReceipts() { frappe.set_route("List", "Purchase Receipt"); }', component)

	def test_edgesuite_only_receipt_actions_fail_closed_before_native_handoff(self):
		controller = self.read_app("retailedge/page/professional_purchasing/professional_purchasing.js")
		for contract in (
			'const PREPARE_RECEIPT_TRIGGER_LABEL = "Prepare Receipt"',
			'const REVIEW_RECEIPT_TRIGGER_LABEL = "Review Receipt"',
			'const PURCHASE_RECEIPTS_TRIGGER_LABEL = "Purchase Receipts"',
			'const ADVANCED_PREPARE_RECEIPT_EVENT = "retailedge-advanced-prepare-purchase-receipt"',
			'const ADVANCED_PURCHASE_RECEIPTS_LABEL = "Advanced: Purchase Receipts in ERPNext"',
			"applyPurchaseReceiptParityGate(root)",
			'button.setAttribute("data-retailedge-parity-blocked", "Purchase Receipt")',
			'button.setAttribute("data-retailedge-receipt-preview", "true")',
			"OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT",
			"if (!nativeDeskEnabled()) return;",
			"event.stopImmediatePropagation()",
		):
			self.assertIn(contract, controller)
		self.assertIn('frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE', controller)

	def test_native_receipt_handoff_is_explicitly_advanced_when_allowed(self):
		controller = self.read_app("retailedge/page/professional_purchasing/professional_purchasing.js")
		overlay = self.read_app("public/js/professional_purchasing/ProfessionalPurchaseReceiptPreviewOverlay.vue")
		self.assertIn('button.setAttribute("data-retailedge-advanced-native", "Purchase Receipt")', controller)
		self.assertIn('const ADVANCED_PURCHASE_RECEIPTS_LABEL = "Advanced: Purchase Receipts in ERPNext"', controller)
		self.assertIn('type: "POST"', controller)
		self.assertIn("PREPARE_RECEIPT_METHOD", controller)
		self.assertIn('frappe.set_route("Form", "Purchase Receipt", result.name)', controller)
		self.assertIn("Advanced: Prepare in ERPNext", overlay)
		self.assertIn("nativeFallbackEnabled", overlay)

	def test_shared_guard_still_blocks_native_purchase_receipt_routes_for_edgesuite_only(self):
		controller = self.read_app("retailedge/page/professional_purchasing/professional_purchasing.js")
		guard = self.read_app("public/js/retailedge_edgesuite_only_operational_guard.bundle.js")
		self.assertIn('"Purchase Receipt",', controller)
		self.assertIn('"purchase-receipt",', controller)
		self.assertIn('const RESTRICTED_MODE = "edgesuite_only"', guard)
		self.assertIn('if (family !== "form" && family !== "list") return false;', guard)

	def test_backend_remains_draft_first_erpnext_mapper_without_direct_posting(self):
		backend = self.read_app("professional_purchasing.py")
		self.assertIn("make_purchase_receipt(po.name)", backend)
		self.assertIn("receipt.insert()", backend)
		self.assertNotIn("receipt.submit()", backend)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', backend)
		self.assertNotIn('frappe.new_doc("GL Entry")', backend)
		self.assertNotIn("ignore_permissions=True", backend)

	def test_purchase_receipt_ownership_is_documented_as_blocked_not_promoted(self):
		doc = (REPO_ROOT / "docs" / "rir2f2c_purchase_receipt_parity_gate.md").read_text(encoding="utf-8")
		master = self.read_app("master_experience.py")
		self.assertIn("PARITY_BLOCKED_NATIVE_COMPLETION", doc)
		self.assertIn("RIR2F2D exit criteria", doc)
		self.assertIn('PURCHASE_ORDER_NATIVE_PEER_DOCTYPE = "Purchase Order"', master)
		self.assertNotIn('PURCHASE_RECEIPT_NATIVE_PEER_DOCTYPE = "Purchase Receipt"', master)


if __name__ == "__main__":
	unittest.main()
