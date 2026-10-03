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

	def test_retailedge_publishes_permission_aware_edgesuite_product_availability(self):
		provider = self.read_app("product_context.py")
		hooks = self.read_app("hooks.py")
		for contract in (
			'"key": "retailedge"',
			'"product_key": "retailedge"',
			'"home_route": "/app/retailedge-business-hub"',
			'frappe.get_doc("Page", "retailedge-business-hub").is_permitted()',
		):
			self.assertIn(contract, provider)
		self.assertIn(
			'"retailedge.product_context.get_product_availability"',
			hooks,
		)

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
			'"TOTAL: {0}"',
			'"Outstanding: {0}"',
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
			'adapter.profiles.textEncoder(profile)',
			'adapter.printReceipt(documentPayload, { encodeText })',
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

	def test_printer_profile_uses_authoritative_receipt_company_and_branch(self):
		source = self.read_app("public/js/thermalReceiptPrinting.js")
		payload_index = source.index("const payload = await callReceiptPayload")
		context_index = source.index("company: String(payload?.company || company ||")
		profile_index = source.index("const profile = await resolveSerialProfile")
		self.assertLess(payload_index, context_index)
		self.assertLess(context_index, profile_index)
		self.assertIn("branch: String(payload?.branch || branch ||", source)

	def test_receipt_uses_erpnext_net_values_discounts_tender_and_change(self):
		source = self.read_app("thermal_receipt.py")
		for contract in (
			'row.get("net_rate") if row.get("net_rate") is not None else row.get("rate")',
			'row.get("net_amount") if row.get("net_amount") is not None else row.get("amount")',
			'"Item Discount: {0}%"',
			'"Additional Discount (included): {0}"',
			'"Tendered: {0}"',
			'"Change: {0}"',
			'"Grand Total: {0}"',
			'"Rounding: {0}"',
			'"Write Off: {0}"',
			'"Credit / Refund Due: {0}"',
			'receipt_label = _("Return Receipt") if cint(doc.get("is_return"))',
		):
			self.assertIn(contract, source)

	def test_partial_payment_receipt_keeps_payment_rows_and_outstanding_balance(self):
		source = self.read_app("thermal_receipt.py")
		payment_index = source.index('if payment_blocks:')
		outstanding_index = source.index("if outstanding > 0:")
		self.assertLess(payment_index, outstanding_index)
		self.assertIn('"Outstanding: {0}"', source)
		self.assertIn('"Credit / Refund Due: {0}"', source)

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

	def test_devices_and_printing_navigation_carries_operating_context(self):
		source = self.read_app("master_experience.py")
		for contract in (
			'params = {',
			'"purpose": "Receipt"',
			'"product_key": "retailedge"',
			'company = str(operating.get("company") or "").strip()',
			'branch = str(operating.get("branch") or "").strip()',
			'item["target_type"] = "URL"',
			'item["target"] = f"/app/edge-printing?{urlencode(params)}"',
			'target.startswith("/app/edge-printing?")',
		):
			self.assertIn(contract, source)

	def test_retailedge_validates_scoped_print_profile_context(self):
		provider = self.read_app("product_context.py")
		hooks = self.read_app("hooks.py")
		for contract in (
			"def validate_print_context",
			'key != "retailedge"',
			'frappe.db.exists("Company", company)',
			'company_doc.has_permission("read", user=user)',
			'frappe.db.exists("Branch", branch)',
			"get_enabled_branch_profile_companies",
			"get_exact_branch_profile",
			"has_enabled_branch_profiles",
			"company not in configured_companies",
			"validate_user_branch_access",
			'"handled": True',
			'"allowed": True',
		):
			self.assertIn(contract, provider)
		self.assertIn(
			'"retailedge.product_context.validate_print_context"',
			hooks,
		)

	def test_retailedge_ci_uses_the_transport_hardened_edgesuite_candidate(self):
		workflow = self.read_repo(".github/workflows/ci.yml")
		self.assertIn("50c1c973fc06d77c8d851f17c88dc586f57fd12f", workflow)
		self.assertIn("edgeui_print.bundle", workflow)


if __name__ == "__main__":
	unittest.main()
