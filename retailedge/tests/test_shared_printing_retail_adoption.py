from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


class TestSharedPrintingRetailAdoption(unittest.TestCase):
	def read_app(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def read_repo(self, relative: str) -> str:
		return (REPO_ROOT / relative).read_text(encoding="utf-8")

	def test_thermal_receipt_payload_is_product_owned_and_permission_guarded(self):
		source = self.read_app("thermal_receipt.py")
		for contract in (
			'SUPPORTED_THERMAL_RECEIPT_DOCTYPES = {"Sales Invoice", "POS Invoice"}',
			'get_thermal_receipt_payload',
			'_assert_document_permission(doctype, name, "read")',
			'_assert_document_permission(doctype, name, "print")',
			'if cint(doc.docstatus) != 1:',
			'"blocks": _receipt_blocks(doc, definition)',
			'"schema_version": 1',
			'"document_type": "receipt"',
		):
			self.assertIn(contract, source)
		for forbidden in (
			"ignore_permissions=True",
			"frappe.db.commit",
			"doc.save(",
			"doc.submit(",
		):
			self.assertNotIn(forbidden, source)

	def test_receipt_payload_contains_logical_blocks_not_device_commands(self):
		source = self.read_app("thermal_receipt.py")
		for contract in (
			'"type": "text"',
			'"type": "row"',
			'"type": "rule"',
			'"type": "qr"',
			'"TOTAL"',
			'"Outstanding"',
		):
			self.assertIn(contract, source)
		for forbidden in (
			"navigator.serial",
			"requestPort",
			"0x1b",
			"0x1d",
			"ESC @",
		):
			self.assertNotIn(forbidden, source)

	def test_browser_adapter_uses_edgesuite_profiles_binding_and_print_runtime(self):
		source = self.read_app("public/js/thermalReceiptPrinting.js")
		for contract in (
			'RETAILEDGE_PRODUCT_KEY',
			'adapter.profiles?.resolve',
			'adapter.devices?.connectBoundSerial',
			'adapter.profiles.connectionOptions(profile)',
			'adapter.profiles.receiptOptions(profile)',
			'adapter.printReceipt(documentPayload)',
			'RETAIL_PRINTER_SETUP_REQUIRED',
			'/app/edge-printing?',
		):
			self.assertIn(contract, source)
		for forbidden in (
			"navigator.serial",
			"requestPort(",
			"getPorts(",
			"bluetoothServiceClassId",
		):
			self.assertNotIn(forbidden, source)

	def test_generic_reprint_never_opens_cash_drawer_by_default(self):
		source = self.read_app("public/js/thermalReceiptPrinting.js")
		self.assertIn("openDrawer = false", source)
		self.assertIn("if (openDrawer && profileOptions.cashDrawer)", source)

	def test_document_output_keeps_document_print_and_adds_direct_receipt_print(self):
		component = self.read_app("public/js/document_output_sharing/DocumentOutputSharing.vue")
		for contract in (
			'Print Document',
			'Print Receipt',
			'canDirectReceiptPrint',
			'directPrintReceipt',
			'printRetailReceipt',
			'openRetailPrinterSetup',
		):
			self.assertIn(contract, component)

	def test_make_sale_reuses_shared_retail_receipt_adapter_after_submission(self):
		component = self.read_app("public/js/make_sale/MakeSale.vue")
		for contract in (
			'Print Receipt',
			'receiptPrinting',
			'printSavedReceipt',
			'printRetailReceipt',
			'document: "sales-invoice"',
			'openRetailPrinterSetup',
		):
			self.assertIn(contract, component)
		self.assertNotIn("navigator.serial", component)

	def test_devices_and_printing_is_discoverable_in_business_setup(self):
		source = self.read_app("master_experience.py")
		for contract in (
			"DEVICES_PRINTING_ITEM",
			'"label": "Devices & Printing"',
			'"target": "edge-printing"',
			"_add_devices_printing_navigation(navigation_groups)",
			'"edge-printing",',
			'"shared_receipt_printing"] = "edgesuite_serial_receipt_v1"',
		):
			self.assertIn(contract, source)

	def test_retailedge_ci_uses_the_printing_capable_edgesuite_foundation(self):
		workflow = self.read_repo(".github/workflows/ci.yml")
		self.assertIn("800cf1fd4aad82038f74411872e534400ad1ead0", workflow)


if __name__ == "__main__":
	unittest.main()
