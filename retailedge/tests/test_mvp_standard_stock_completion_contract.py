from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "standard_stock_completion.py"
DIALOG = ROOT / "public/js/retailedge_business_hub/StandardStockCompletionDialog.vue"
HUB = ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"
GUIDED_TRANSFER = ROOT / "guided_stock_transfer.py"
GUIDED_ADJUSTMENT = ROOT / "guided_stock_adjustment.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_completion_is_bounded_to_standard_stock_documents():
	source = _read(SERVICE)
	assert 'SUPPORTED_DOCTYPES = {STOCK_ENTRY_DOCTYPE, STOCK_RECONCILIATION_DOCTYPE}' in source
	assert 'MATERIAL_TRANSFER' in source
	assert 'STOCK_RECONCILIATION_PURPOSE' in source
	assert 'MAX_STANDARD_ITEMS = 50' in source
	assert 'Amended stock documents require Advanced ERPNext review.' in source
	assert 'Serial No or Batch tracking and requires Advanced ERPNext' in source


def test_completion_revalidates_company_branch_and_warehouse_scope():
	source = _read(SERVICE)
	for contract in (
		"get_operational_branch_scope",
		"resolve_operational_branch",
		"resolve_branch_from_warehouse",
		"_validate_transfer_branch_warehouse",
		"_validate_adjustment_branch_warehouse",
		'frappe.has_permission("Company", "read"',
		'frappe.has_permission("Warehouse", "read"',
		'frappe.db.get_value("Warehouse", warehouse, "company")',
		"RetailEdge cannot prove the Branch scope",
	):
		assert contract in source


def test_preview_is_persistence_free_and_workflow_aware():
	source = _read(SERVICE)
	start = source.index("def get_standard_stock_completion_preview")
	end = source.index('@frappe.whitelist(methods=["POST"])', start)
	preview = source[start:end]
	assert "_build_preview" in preview
	assert ".submit()" not in preview
	assert ".insert()" not in preview
	assert ".save()" not in preview
	assert "get_workflow_readiness" in source
	assert '"persistence": "none"' in source


def test_direct_submit_locks_stale_checks_revalidates_and_delegates_to_erpnext():
	source = _read(SERVICE)
	start = source.index("def submit_standard_stock_document")
	end = source.index('@frappe.whitelist(methods=["POST"])', start + 10)
	method = source[start:end]
	for contract in (
		"FOR UPDATE",
		"expected_modified",
		"_build_preview(doc)",
		"get_workflow_readiness",
		'frappe.has_permission(doctype, "submit", doc=doc)',
		"doc.submit()",
		"ERPNext native stock submit",
	):
		assert contract in source
	for forbidden in (
		".docstatus =",
		".workflow_state =",
		"frappe.db.commit",
		"ignore_permissions=True",
		'frappe.new_doc("Stock Ledger Entry")',
	):
		assert forbidden not in method


def test_workflow_action_uses_authoritative_frappe_workflow_engine():
	source = _read(SERVICE)
	method = source[source.index("def apply_standard_stock_workflow_action"):]
	for contract in (
		"expected_modified",
		"expected_workflow_state",
		"_build_preview(doc)",
		"apply_document_workflow_action(",
		"expected_modified=expected_modified",
		"expected_state=_clean(expected_workflow_state)",
	):
		assert contract in method
	assert ".workflow_state =" not in method
	assert ".docstatus =" not in method


def test_backend_never_writes_stock_ledger_or_valuation_directly():
	source = _read(SERVICE)
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit",
		'frappe.new_doc("Stock Ledger Entry")',
		"frappe.db.set_value",
		"update_stock_ledger",
		"valuation_rate =",
		"basic_rate =",
	):
		assert forbidden not in source


def test_completion_dialog_uses_server_authoritative_actions_only():
	source = _read(DIALOG)
	for contract in (
		"get_standard_stock_completion_preview",
		"submit_standard_stock_document",
		"apply_standard_stock_workflow_action",
		"workflow_readiness?.available_actions",
		"expected_modified",
		"expected_workflow_state",
		"Advanced: Open in ERPNext",
	):
		assert contract in source
	for forbidden in (".workflow_state =", ".docstatus =", ".status ="):
		assert forbidden not in source


def test_business_hub_opens_completion_after_both_guided_stock_drafts():
	source = _read(HUB)
	assert 'import StandardStockCompletionDialog from "./StandardStockCompletionDialog.vue"' in source
	assert 'this.openStockCompletion({ doctype: "Stock Entry", name: result.name })' in source
	assert 'this.openStockCompletion({ doctype: "Stock Reconciliation", name: result.name })' in source
	assert "stockCompletionOpen" in source
	assert "stockCompletionDocument" in source
	assert 'this.notifyGuidedDraftSaved(result, "Stock Entry", "Stock Transfer")' not in source
	assert 'this.notifyGuidedDraftSaved(result, "Stock Reconciliation", "Stock Reconciliation")' not in source


def test_guided_creators_remain_draft_only():
	for path in (GUIDED_TRANSFER, GUIDED_ADJUSTMENT):
		source = _read(path)
		assert "doc.insert()" in source
		assert "doc.submit()" not in source
