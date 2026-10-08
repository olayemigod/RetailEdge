from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCESS = ROOT / "supplier_document_review_access.py"
HOOKS = ROOT / "hooks.py"


def test_supplier_review_read_endpoints_use_controlled_access_override():
	text = HOOKS.read_text(encoding="utf-8")

	assert (
		'"retailedge.supplier_document_review.get_supplier_document_review_context": '
		'"retailedge.supplier_document_review_access.get_supplier_document_review_context"'
	) in text
	assert (
		'"retailedge.supplier_document_review.search_supplier_document_review_options": '
		'"retailedge.supplier_document_review_access.search_supplier_document_review_options"'
	) in text


def test_supplier_review_write_actions_are_not_overridden():
	text = HOOKS.read_text(encoding="utf-8")

	for method in (
		"review_supplier_document_intake",
		"prepare_draft_purchase_invoice",
		"get_supplier_document_purchase_invoice_review",
		"apply_supplier_document_purchase_invoice_workflow_action",
		"submit_supplier_document_purchase_invoice",
	):
		assert f'"retailedge.supplier_document_review.{method}"' not in text


def test_controlled_po_projection_is_exact_and_scope_validated():
	text = ACCESS.read_text(encoding="utf-8")

	assert 'frappe.db.get_value("Purchase Order", purchase_order, fields, as_dict=True)' in text
	assert 'frappe.get_list(\n\t\t"Purchase Order"' not in text
	assert 'row.get("company")' in text
	assert 'getattr(intake, "company"' in text
	assert 'row.get("supplier")' in text
	assert 'getattr(intake, "supplier"' in text
	assert 'review._allowed_branch_names(user=user, company=company)' in text
	assert 'validate_user_branch_access(branch, user=user, company=company, throw=True)' in text
	assert 'po_cache_key = (po_name, str(intake.company or ""), str(intake.supplier or ""))' in text


def test_supplier_search_does_not_require_purchase_order_desk_permission():
	text = ACCESS.read_text(encoding="utf-8")

	assert 'search_link("Supplier", txt, page_length=review.MAX_LINK_RESULTS)' in text
	assert 'reference_doctype="Purchase Order"' not in text
