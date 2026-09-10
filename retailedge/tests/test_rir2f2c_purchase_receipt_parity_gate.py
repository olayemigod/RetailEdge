from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


class TestRIR2F2CPurchaseReceiptParityGate(unittest.TestCase):
	def read_app(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_standard_receipt_actions_delegate_to_existing_edgesuite_ownership(self):
		component = self.read_app("public/js/professional_purchasing/ProfessionalPurchasing.vue")
		prepare_receipt = component.split("\t\tprepareReceipt(row) {", 1)[1].split("\n\t\tasync preparePurchaseReturn()", 1)[0]
		self.assertIn("dispatchEdgeSuiteEvent(OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT", prepare_receipt)
		self.assertNotIn("prepare_purchase_receipt_draft", prepare_receipt)
		self.assertNotIn('frappe.set_route("Form", "Purchase Receipt", result.name)', prepare_receipt)
		self.assertIn("openPurchaseReceipts() { dispatchEdgeSuiteEvent(OPEN_PURCHASE_RECEIPT_HISTORY_EVENT); }", component)

	def test_edgesuite_receipt_actions_are_intercepted_before_native_handoff(self):
		controller = self.read_app("retailedge/page/professional_purchasing/professional_purchasing.js")
		for contract in (
			'const PREPARE_RECEIPT_TRIGGER_LABEL = "Prepare Receipt"',
			'const REVIEW_RECEIPT_TRIGGER_LABEL = "Review Receipt"',
			'const PURCHASE_RECEIPTS_TRIGGER_LABEL = "Purchase Receipts"',
			'const RECEIPT_HISTORY_TRIGGER_LABEL = "Receipt History"',
			'const ADVANCED_PREPARE_RECEIPT_EVENT = "retailedge-advanced-prepare-purchase-receipt"',
			'const ADVANCED_PURCHASE_RECEIPTS_LABEL = "Advanced: Purchase Receipts in ERPNext"',
			"applyPurchaseReceiptParityGate(root)",
			'button.setAttribute("data-retailedge-receipt-preview", "true")',
			'button.setAttribute("data-retailedge-receipt-history", "true")',
			"OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT",
			"OPEN_PURCHASE_RECEIPT_HISTORY_EVENT",
			"if (!nativeDeskEnabled()) return;",
			"event.stopImmediatePropagation()",
		):
			self.assertIn(contract, controller)
		hidden = controller.split("hiddenButtonLabels:", 1)[1].split("],", 1)[0]
		self.assertNotIn("PURCHASE_RECEIPTS_TRIGGER_LABEL", hidden)
		self.assertIn('frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE', controller)

	def test_native_receipt_handoffs_are_explicitly_advanced_when_allowed(self):
		controller = self.read_app("retailedge/page/professional_purchasing/professional_purchasing.js")
		preview = self.read_app("public/js/professional_purchasing/ProfessionalPurchaseReceiptPreviewOverlay.vue")
		history = self.read_app("public/js/professional_purchasing/ProfessionalPurchaseReceiptHistoryOverlay.vue")
		self.assertIn('const ADVANCED_PURCHASE_RECEIPTS_LABEL = "Advanced: Purchase Receipts in ERPNext"', controller)
		self.assertIn('type: "POST"', controller)
		self.assertIn("PREPARE_RECEIPT_METHOD", controller)
		self.assertIn('frappe.set_route("Form", "Purchase Receipt", result.name)', controller)
		self.assertIn("Advanced: Prepare in ERPNext", preview)
		self.assertIn("nativeFallbackEnabled", preview)
		self.assertIn("Advanced: Purchase Receipts in ERPNext", history)
		self.assertIn('frappe.set_route("List", "Purchase Receipt")', history)
		self.assertIn("nativeFallbackEnabled", history)

	def test_shared_guard_still_blocks_native_purchase_receipt_routes_for_edgesuite_only(self):
		controller = self.read_app("retailedge/page/professional_purchasing/professional_purchasing.js")
		guard = self.read_app("public/js/retailedge_edgesuite_only_operational_guard.bundle.js")
		self.assertIn('"Purchase Receipt",', controller)
		self.assertIn('"purchase-receipt",', controller)
		self.assertIn('const RESTRICTED_MODE = "edgesuite_only"', guard)
		self.assertIn('if (family !== "form" && family !== "list") return false;', guard)

	def test_legacy_backend_remains_draft_first_without_direct_posting(self):
		backend = self.read_app("professional_purchasing.py")
		self.assertIn("make_purchase_receipt(po.name)", backend)
		self.assertIn("receipt.insert()", backend)
		self.assertNotIn("receipt.submit()", backend)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', backend)
		self.assertNotIn('frappe.new_doc("GL Entry")', backend)
		self.assertNotIn("ignore_permissions=True", backend)

	def test_historical_c_gate_remains_documented_and_native_peer_not_promoted(self):
		doc = (REPO_ROOT / "docs" / "rir2f2c_purchase_receipt_parity_gate.md").read_text(encoding="utf-8")
		master = self.read_app("master_experience.py")
		self.assertIn("PARITY_BLOCKED_NATIVE_COMPLETION", doc)
		self.assertIn("RIR2F2D exit criteria", doc)
		self.assertIn('PURCHASE_ORDER_NATIVE_PEER_DOCTYPE = "Purchase Order"', master)
		self.assertNotIn('PURCHASE_RECEIPT_NATIVE_PEER_DOCTYPE = "Purchase Receipt"', master)


if __name__ == "__main__":
	unittest.main()
