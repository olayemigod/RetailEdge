from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import supplier_document_review


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/supplier_document_review/SupplierDocumentReview.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_review_is_bound_to_exact_immutable_handoff_and_authoritative_purchase_order():
	source = inspect.getsource(supplier_document_review._get_supplier_document_purchase_invoice_authority)
	assert "_existing_handoff(extraction.name)" in source
	assert 'frappe.get_doc("Purchase Order", intake.purchase_order)' in source
	assert 'frappe.get_doc("Purchase Invoice", purchase_invoice_name)' in source
	assert "purchase_invoice.supplier != po.supplier or purchase_invoice.company != po.company" in source
	assert "validate_user_branch_access" in source


def test_standard_submit_is_stale_safe_and_uses_erpnext_submit_only():
	source = inspect.getsource(supplier_document_review.submit_supplier_document_purchase_invoice)
	assert "lock_purchase_invoice=True" in source
	assert "expected_purchase_invoice_modified" in source
	assert "purchase_invoice.submit()" in source
	assert "docstatus" in source
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Stock Ledger Entry")',
		'frappe.new_doc("Payment Entry")',
	):
		assert forbidden not in source


def test_standard_submit_fails_closed_on_unreconciled_or_stock_updating_drafts():
	source = inspect.getsource(supplier_document_review._supplier_document_purchase_invoice_blockers)
	for contract in (
		"extracted_currency",
		"currency_mismatch",
		"extracted_total",
		"total_difference",
		"update_stock",
		"purchase_order_linkage",
		"submit_permission",
	):
		assert contract in source
	assert "abs(total_difference) > 0.01" in source


def test_edgesuite_review_replaces_ordinary_native_draft_handoff():
	source = _read(COMPONENT)
	assert "canUseNativeDesk: false" in source
	assert "retailedge.master_experience.get_master_retailedge_business_hub_context" in source
	assert "this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);" in source
	assert "openPurchaseInvoiceReview(row)" in source
	assert "get_supplier_document_purchase_invoice_review" in source
	assert "submit_supplier_document_purchase_invoice" in source
	assert "Submit Purchase Invoice" in source
	assert 'if (result.purchase_invoice) await this.openPurchaseInvoiceReview({ extraction: row.extraction });' in source


def test_native_purchase_routes_are_explicit_advanced_fallbacks():
	source = _read(COMPONENT)
	assert 'v-if="canUseNativeDesk"' in source
	assert 'openPurchaseOrder(name) { if (this.canUseNativeDesk && name)' in source
	assert 'openPurchaseInvoices() { if (this.canUseNativeDesk)' in source
	assert 'openPurchaseInvoice(name) { if (this.canUseNativeDesk && name)' in source
	assert 'if ((item.target_type === "DocType" || item.target_type === "Report") && !this.canUseNativeDesk) return;' in source
