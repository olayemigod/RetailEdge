from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
FORMATS = APP_ROOT / "professional_print_formats.py"
THERMAL = APP_ROOT / "thermal_receipt.py"
BROWSER = APP_ROOT / "public" / "js" / "thermalReceiptPrinting.js"
GOVERNANCE = APP_ROOT / "print_format_governance.py"
SETTINGS = APP_ROOT / "print_output_settings.py"
PRINT_CONTEXT = APP_ROOT / "print_output_context.py"
RETAIL_SETTINGS = APP_ROOT / "retailedge" / "page" / "retail_settings" / "retail_settings.py"
PATCHES = APP_ROOT / "patches.txt"


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
	assert thermal.index('_("Balance Due")') < thermal.index("blocks.extend(_receipt_presentation_blocks(receipt, paper_width))")


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
	assert '"Show Branch on Printed Documents"' in settings
	assert "output.show_branch and output.branch" in governance
	assert 'display_branch = _text(output.get("branch")) if output.get("show_branch") else ""' in thermal
	assert '"branch": _branch(doc)' in thermal


def test_receipt_content_is_settings_controlled_across_html_and_thermal_paths():
	settings = SETTINGS.read_text(encoding="utf-8")
	context = PRINT_CONTEXT.read_text(encoding="utf-8")
	governance = GOVERNANCE.read_text(encoding="utf-8")
	thermal = THERMAL.read_text(encoding="utf-8")
	settings_page = RETAIL_SETTINGS.read_text(encoding="utf-8")

	for fieldname in (
		"show_receipt_status",
		"receipt_status_label",
		"show_receipt_payment_method",
		"receipt_payment_method_label",
		"show_receipt_amount_in_words",
		"receipt_amount_in_words_label",
		"show_receipt_footer_separator",
		"show_receipt_footer",
		"receipt_footer_message",
	):
		assert fieldname in settings
		assert fieldname in settings_page

	assert '"key": "receipt-presentation"' in settings_page
	assert '"label": "Receipts & Printing"' in settings_page
	assert "get_receipt_presentation_settings" in context
	assert '"status": status.upper()' in context
	assert '"payment_method": ", ".join(payment_methods)' in context
	assert '"amount_in_words": in_words' in context
	assert '"receipt": _receipt_presentation(doc)' in context

	assert "_RECEIPT_PRESENTATION_SET" in governance
	assert "_RECEIPT_PRESENTATION_ROWS" in governance
	assert "_RECEIPT_GOVERNED_FOOTER" in governance
	assert "_RECEIPT_PAYMENT_AMOUNT_ROWS" in governance
	assert 'result = result.replace(_RECEIPT_PAYMENT_AMOUNT_ROWS, "")' in governance

	assert 'receipt = dict(output.get("receipt") or {})' in thermal
	assert "_receipt_presentation_blocks" in thermal
	assert 'receipt.get("show_status")' in thermal
	assert 'receipt.get("show_payment_method")' in thermal
	assert 'receipt.get("show_amount_in_words")' in thermal
	assert 'receipt.get("show_footer_separator")' in thermal
	assert 'receipt.get("show_footer")' in thermal
	assert 'receipt.get("footer_message")' in thermal
	assert '_("Thank you for your business.")' not in thermal


def test_receipt_settings_keep_business_values_transaction_derived():
	settings = SETTINGS.read_text(encoding="utf-8")
	context = PRINT_CONTEXT.read_text(encoding="utf-8")
	thermal = THERMAL.read_text(encoding="utf-8")

	assert '"status_label": "Status"' in settings
	assert '"payment_method_label": "Payment Method"' in settings
	assert '"amount_in_words_label": "Amount in Words"' in settings
	assert '"footer_message": "Thank you for your business."' in settings
	assert 'payment.get("mode_of_payment")' in context
	assert 'doc.get("status")' in context
	assert 'doc.get("in_words")' in context
	assert "_money(doc.get(\"paid_amount\"), currency)" in thermal
	assert "payment.get_formatted" not in thermal


def test_managed_pedge_receipts_are_governed_for_branch_net_values_and_receipt_policy():
	governance = GOVERNANCE.read_text(encoding="utf-8")

	assert "_DOCUMENT_BRANCH_ROW" in governance
	assert "_RECEIPT_BRANCH_ROW" in governance
	assert 'row.get_formatted("net_rate", doc)' in governance
	assert 'row.get_formatted("net_amount", doc)' in governance
	assert "sync_governed_pedge_print_formats" in governance
	assert "ensure_retailedge_professional_print_formats" in governance
	assert "install_pedge_print_formats_v7" in PATCHES.read_text(encoding="utf-8")


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
