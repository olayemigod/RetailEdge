from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
EDGESUITE_SHA = "a2d1705f794e17c88d66d7041df4dfb47b2684ff"


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
		self.assertIn('"retailedge.product_context.get_product_availability"', hooks)
		self.assertIn('"retailedge.product_context.validate_print_context"', hooks)

	def test_thermal_receipt_payload_is_permission_guarded_and_paper_aware(self):
		source = self.read_app("thermal_receipt.py")
		for contract in (
			'SUPPORTED_THERMAL_RECEIPT_DOCTYPES = {"Sales Invoice", "POS Invoice"}',
			'_assert_document_permission(doctype, name, "read")',
			'_assert_document_permission(doctype, name, "print")',
			'if cint(doc.docstatus) != 1:',
			'"blocks": blocks_by_paper["80"]',
			'"blocks_by_paper": blocks_by_paper',
			'"template_variants": variants',
			'"branch": _branch(doc)',
		):
			self.assertIn(contract, source)
		for forbidden in ("ignore_permissions=True", "frappe.db.commit", "doc.save(", "doc.submit("):
			self.assertNotIn(forbidden, source)

	def test_receipt_payload_uses_horizontal_pedge_table_without_device_commands(self):
		source = self.read_app("thermal_receipt.py")
		for contract in (
			'ITEM_COLUMN_WIDTHS',
			'META_COLUMN_WIDTHS',
			'_("Invoice No.")',
			'_("Customer")',
			'_("Cashier")',
			'_("Branch")',
			'_("Product")',
			'_("Qty")',
			'_("Price")',
			'_("Subtotal")',
			'_("Total Qty")',
			'_("Balance Due")',
			'receipt.get("show_footer")',
			'receipt.get("show_footer_separator")',
			'receipt.get("footer_message")',
		):
			self.assertIn(contract, source)
		self.assertNotIn('_("Thank you for your business.")', source)
		for forbidden in ("navigator.serial", "requestPort", "0x1b", "0x1d", "ESC @"):
			self.assertNotIn(forbidden, source)

	def test_receipt_uses_erpnext_net_values_and_keeps_payment_summary(self):
		source = self.read_app("thermal_receipt.py")
		for contract in (
			'row.get("net_rate") if row.get("net_rate") is not None else row.get("rate")',
			'row.get("net_amount") if row.get("net_amount") is not None else row.get("amount")',
			'receipt.get("show_payment_method")',
			'receipt.get("payment_method")',
			'_("Discount")',
			'_("Tax / Charges")',
			'_("Paid")',
			'_("Change")',
			'_("Write Off")',
			'_("Credit / Refund Due")',
		):
			self.assertIn(contract, source)
		self.assertNotIn("_payment_blocks", source)

	def test_browser_adapter_uses_shared_runtime_and_queryless_setup_route(self):
		source = self.read_app("public/js/thermalReceiptPrinting.js")
		for contract in (
			'adapter.profiles?.resolve',
			'adapter.devices?.connectBoundSerial',
			'adapter.profiles.receiptOptions(profile)',
			'adapter.profiles.textEncoder(profile)',
			'adapter.printReceipt(documentPayload, { encodeText })',
			'payload?.blocks_by_paper?.[paperWidth]',
			'return "/app/edge-printing";',
			'frappe.set_route("edge-printing")',
		):
			self.assertIn(contract, source)
		self.assertNotIn("/app/edge-printing?", source)
		for forbidden in ("navigator.serial", "requestPort(", "getPorts(", "bluetoothServiceClassId"):
			self.assertNotIn(forbidden, source)

	def test_connected_printer_must_match_resolved_profile_binding(self):
		source = self.read_app("public/js/thermalReceiptPrinting.js")
		for contract in (
			'adapter.bindingStore?.get?.(profile.name)',
			'portInfoMatchesBinding(current.portInfo || {}, binding.portInfo || {})',
			'if (current?.connected && !currentMatchesBinding)',
			'await adapter.disconnect("serial")',
			'adapter.devices?.connectBoundSerial?.(',
			'adapter.simulation?.isEnabled?.() && current?.connected',
		):
			self.assertIn(contract, source)
		self.assertNotIn("if (current?.connected) return current;", source)

	def test_generic_reprint_never_opens_cash_drawer_by_default(self):
		source = self.read_app("public/js/thermalReceiptPrinting.js")
		self.assertIn("openDrawer = false", source)
		self.assertIn("if (openDrawer && profileOptions.cashDrawer)", source)

	def test_document_output_and_make_sale_reuse_shared_receipt_adapter(self):
		document_output = self.read_app("public/js/document_output_sharing/DocumentOutputSharing.vue")
		make_sale = self.read_app("public/js/make_sale/MakeSale.vue")
		for source in (document_output, make_sale):
			self.assertIn("Print Receipt", source)
			self.assertIn("printRetailReceipt", source)
			self.assertIn("openRetailPrinterSetup", source)
			self.assertNotIn("navigator.serial", source)
		self.assertIn("Print Document", document_output)

	def test_final_devices_navigation_is_internal_page_without_query_context(self):
		source = self.read_app("printing_navigation.py")
		hooks = self.read_app("hooks.py")
		final_navigation = self.read_app("navigation_consolidation.py")
		for contract in (
			'PRINTING_PAGE = "edge-printing"',
			'item["target_type"] = "Page"',
			'item["target"] = PRINTING_PAGE',
			'target.startswith("/app/edge-printing?")',
			'target.startswith("/desk/edge-printing?")',
		):
			self.assertIn(contract, source)
		self.assertIn(
			'"retailedge.master_experience.get_retailedge_business_hub_context": "retailedge.navigation_consolidation.get_retailedge_business_hub_context"',
			hooks,
		)
		self.assertIn("from retailedge.printing_navigation import normalize_printing_navigation", final_navigation)
		self.assertIn("return normalize_printing_navigation(context)", final_navigation)

	def test_branch_print_policy_is_opt_in_and_presentation_only(self):
		settings = self.read_app("print_output_settings.py")
		context = self.read_app("print_output_context.py")
		governance = self.read_app("print_format_governance.py")
		patches = self.read_app("patches.txt")
		self.assertIn('BRANCH_PRINT_VISIBILITY_FIELD = "show_branch_on_printed_documents"', settings)
		self.assertIn('"default": "0"', settings)
		self.assertIn('"Show Branch on Printed Documents"', settings)
		self.assertIn("_show_branch_on_printed_documents", context)
		self.assertIn('"show_branch": show_branch', context)
		self.assertIn('"branch": branch if show_branch else ""', context)
		self.assertIn("output.show_branch and output.branch", governance)
		self.assertIn("retailedge.patches.install_pedge_print_formats_v6", patches)

	def test_all_release_gates_pin_same_audited_edgesuite_runtime(self):
		for workflow_path in (
			".github/workflows/ci.yml",
			".github/workflows/edgesuite-ui-candidate-compat.yml",
			".github/workflows/upgrade-validation.yml",
			".github/workflows/browser-persona-smoke.yml",
		):
			workflow = self.read_repo(workflow_path)
			self.assertIn(EDGESUITE_SHA, workflow, workflow_path)
			self.assertNotIn("2d8521573f4045b62eb62c6bf4c4827fb7d03dda", workflow, workflow_path)

	def test_ci_verifies_shared_print_bundle(self):
		workflow = self.read_repo(".github/workflows/ci.yml")
		self.assertIn(EDGESUITE_SHA, workflow)
		self.assertIn("edgeui_print.bundle", workflow)


if __name__ == "__main__":
	unittest.main()
