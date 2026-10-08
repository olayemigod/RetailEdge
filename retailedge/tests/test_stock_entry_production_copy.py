from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSFER = ROOT / "public/js/transfer_stock/TransferStock.vue"
ADJUSTMENT = ROOT / "public/js/stock_adjustment/StockAdjustment.vue"


def test_stock_entry_pages_use_business_copy_and_preserve_stock_authority():
	transfer = TRANSFER.read_text(encoding="utf-8")
	adjustment = ADJUSTMENT.read_text(encoding="utf-8")

	for marker in (
		"The Stock Entry has been submitted and the stock movement is posted.",
		"The Stock Entry draft now owns the transfer.",
		"advanced Stock Entry review",
		"Stock Entry draft is saved",
		"Advanced: Open Stock Entry",
		"advanced Stock Entry form",
	):
		assert marker in transfer

	for marker in (
		"The Stock Reconciliation has been submitted and the stock correction is posted.",
		"The Stock Reconciliation draft now owns this stock count.",
		"advanced Stock Reconciliation review",
		"Stock Reconciliation draft is saved",
		"Advanced: Open Stock Reconciliation",
		"advanced Stock Reconciliation form",
	):
		assert marker in adjustment

	for text in (transfer, adjustment):
		for forbidden in ("ERPNext", "Frappe Workflow", "Advanced: ERPNext"):
			assert forbidden not in text

	for marker in (
		"create_simple_stock_transfer_draft",
		"update_standard_stock_document_draft",
		"get_standard_stock_completion_preview",
		'v-if="canUseNativeDesk"',
		'@click="openAdvancedNative"',
		'frappe.set_route("Form", "Stock Entry", this.savedDocument.name)',
		'frappe.new_doc("Stock Entry", { purpose: "Material Transfer" })',
		"sameWarehouse()",
		"transferContextReady()",
	):
		assert marker in transfer

	for marker in (
		"create_simple_stock_adjustment_draft",
		"update_standard_stock_document_draft",
		"get_standard_stock_completion_preview",
		'v-if="canUseNativeDesk"',
		'@click="openAdvancedNative"',
		'frappe.set_route("Form", "Stock Reconciliation", this.savedDocument.name)',
		'frappe.new_doc("Stock Reconciliation")',
		"resolveBranchWarehouse",
	):
		assert marker in adjustment
