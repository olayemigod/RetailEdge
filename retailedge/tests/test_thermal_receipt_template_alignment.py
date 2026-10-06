from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
FORMATS = APP_ROOT / "professional_print_formats.py"
THERMAL = APP_ROOT / "thermal_receipt.py"
BROWSER = APP_ROOT / "public" / "js" / "thermalReceiptPrinting.js"
GOVERNANCE = APP_ROOT / "print_format_governance.py"
SETTINGS = APP_ROOT / "print_output_settings.py"


def test_direct_receipt_uses_existing_pedge_receipt_catalog():
	formats = FORMATS.read_text(encoding="utf-8")
	thermal = THERMAL.read_text(encoding="utf-8")

	for name in (
		"PEdge Sales Receipt 80mm",
		"PEdge Sales Receipt 58mm",
		"PEdge POS Receipt 80mm",
		"PEdge POS Receipt 58mm",
	):
		assert name in formats

	assert "from retailedge.professional_print_formats import RECEIPT_PRINT_FORMATS" in thermal
	assert 'return "PEdge POS Receipt" if doctype == "POS Invoice" else "PEdge Sales Receipt"' in thermal
	assert 'kind == "receipt-58"' in thermal
	assert 'kind == "receipt-80"' in thermal


def test_thermal_receipt_uses_horizontal_pedge_item_table_and_aligned_metadata():
	thermal = THERMAL.read_text(encoding="utf-8")

	for label in (
		"Invoice No.",
		"Date",
		"Customer",
		"Cashier",
		"Branch",
		"Product",
		"Qty",
		"Price",
		"Subtotal",
		"Total Qty",
		"Discount",
		"Tax / Charges",
		"Paid",
		"Change",
		"Total",
		"Balance Due",
		"Thank you for your business.",
	):
		assert label in thermal

	assert "ITEM_COLUMN_WIDTHS" in thermal
	assert "META_COLUMN_WIDTHS" in thermal
	assert "_label_value_blocks" in thermal
	assert "_item_table_blocks" in thermal
	assert '"columns": [' in thermal
	assert '_("Product")' in thermal
	assert '_("Qty")' in thermal
	assert '_("Price")' in thermal
	assert '_("Subtotal")' in thermal
	assert thermal.index('_("Invoice No.")') < thermal.index("blocks.extend(_item_table_blocks(doc, paper_width))")
	assert thermal.index("blocks.extend(_item_table_blocks(doc, paper_width))") < thermal.index('_("Total Qty")')
	assert thermal.index('_("Total")') < thermal.index('_("Balance Due")')
	assert thermal.index('_("Balance Due")') < thermal.index('_("Thank you for your business.")')


def test_thermal_receipt_is_paper_aware_and_preserves_accounting_truth():
	thermal = THERMAL.read_text(encoding="utf-8")
	browser = BROWSER.read_text(encoding="utf-8")

	assert '58: (10, 3, 9, 10)' in thermal
	assert '80: (21, 5, 10, 12)' in thermal
	assert '"blocks_by_paper": blocks_by_paper' in thermal
	assert 'row.get("net_rate") if row.get("net_rate") is not None else row.get("rate")' in thermal
	assert 'row.get("net_amount") if row.get("net_amount") is not None else row.get("amount")' in thermal
	assert "payload?.blocks_by_paper?.[paperWidth]" in browser
	assert "ignore_permissions=True" not in thermal
	assert "doc.save(" not in thermal
	assert "doc.submit(" not in thermal


def test_branch_visibility_is_opt_in_per_branch_and_shared_by_all_output_paths():
	settings = SETTINGS.read_text(encoding="utf-8")
	governance = GOVERNANCE.read_text(encoding="utf-8")
	thermal = THERMAL.read_text(encoding="utf-8")

	assert 'BRANCH_PRINT_VISIBILITY_FIELD = "show_branch_on_printed_documents"' in settings
	assert '"default": "0"' in settings
	assert '"Show Branch on Printed Documents"' in settings
	assert "output.show_branch and output.branch" in governance
	assert 'display_branch = _text(output.get("branch")) if output.get("show_branch") else ""' in thermal
	assert '"branch": _branch(doc)' in thermal


def test_managed_pedge_receipts_are_governed_for_branch_and_net_item_values():
	governance = GOVERNANCE.read_text(encoding="utf-8")

	assert "_DOCUMENT_BRANCH_ROW" in governance
	assert "_RECEIPT_BRANCH_ROW" in governance
	assert 'row.get_formatted("net_rate", doc)' in governance
	assert 'row.get_formatted("net_amount", doc)' in governance
	assert "sync_governed_pedge_print_formats" in governance
	assert "ensure_retailedge_professional_print_formats" in governance


def test_browser_uses_stable_internal_setup_route_and_resolved_pedge_variant():
	browser = BROWSER.read_text(encoding="utf-8")

	assert 'return "/app/edge-printing";' in browser
	assert 'frappe.set_route("edge-printing")' in browser
	assert "URLSearchParams" not in browser
	assert "function resolvedReceiptTemplate" in browser
	assert "payload?.template_variants?.[paperWidth]" in browser
	assert "const template = resolvedReceiptTemplate(payload, options);" in browser
	assert "template," in browser
	assert "paper_width: options.paper" in browser
