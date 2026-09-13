from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "standard_internal_transfer_completion.py"
DIALOG = ROOT / "public/js/retailedge_business_hub/StandardInternalTransferCompletionDialog.vue"
HUB = ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"
CASH_CUSTODY = ROOT / "cash_custody.py"
CASH_TRANSFER = ROOT / "guided_cash_transfer.py"
HOOKS = ROOT / "hooks.py"
CASH_MOVEMENT = ROOT / "cash_movement.py"
CONTRACT = ROOT.parent / "docs/rir2g1e_standard_internal_transfer_completion.md"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_service_is_payment_entry_internal_transfer_only():
	source = _read(SERVICE)
	assert 'PAYMENT_ENTRY_DOCTYPE = "Payment Entry"' in source
	assert 'INTERNAL_TRANSFER = "Internal Transfer"' in source
	assert 'CASH_DEPOSIT_TYPE = "Cash Deposit"' in source
	assert 'doc.get("payment_type") != INTERNAL_TRANSFER' in source


def test_preview_is_persistence_free_and_erpnext_authoritative():
	source = _read(SERVICE)
	start = source.index("def get_standard_internal_transfer_completion_preview")
	end = source.index('@frappe.whitelist(methods=["POST"])', start)
	preview = source[start:end]
	for contract in (
		"_get_payment_entry",
		"_validate_transfer_context",
		"_standard_transfer_blockers",
		"_validate_accounts",
		"_validate_cash_deposit_context",
		"get_workflow_readiness",
		'"persistence": "none"',
		'"source_of_truth": "ERPNext Payment Entry"',
	):
		assert contract in source
	for forbidden in (
		".save()",
		".insert()",
		".submit()",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Payment Ledger Entry")',
	):
		assert forbidden not in preview


def test_advanced_payment_shapes_fail_closed():
	source = _read(SERVICE)
	for contract in (
		"party_type",
		"party",
		"references",
		"deductions",
		"difference_amount",
		"book_advance_payments_in_separate_party_account",
		"Advanced ERPNext",
	):
		assert contract in source


def test_accounts_are_same_company_bank_or_cash_and_company_currency_only():
	source = _read(SERVICE)
	for contract in (
		"paid_from",
		"paid_to",
		"From Account and To Account must be different",
		'_assert_read("Account", account)',
		'"company"',
		'"is_group"',
		'"account_type"',
		'"account_currency"',
		'{"Bank", "Cash"}',
		"company_currency",
		"Multi-currency internal transfers require Advanced ERPNext review",
	):
		assert contract in source


def test_amount_and_bank_reference_rules_are_revalidated():
	source = _read(SERVICE)
	for contract in (
		"paid_amount",
		"received_amount",
		"must match and be greater than zero",
		"reference_no",
		"Reference No is required when a Bank account is involved",
	):
		assert contract in source


def test_operational_branch_is_revalidated_and_restricted_blank_fails_closed():
	source = _read(SERVICE)
	for contract in (
		"get_operational_branch_scope",
		"resolve_operational_branch",
		"has no Branch attribution for your restricted access",
		"get_operating_context",
		"current Operating Branch",
	):
		assert contract in source


def test_cash_deposit_reuses_existing_custody_and_bank_authorities():
	source = _read(SERVICE)
	for contract in (
		"retailedge_cash_custody_type",
		"retailedge_cashier",
		"retailedge_pos_opening_shift",
		"validate_cash_deposit_bank_destination",
		"get_cash_custody_snapshot",
		'"Cash"',
		'"Bank"',
		"available_cash",
	):
		assert contract in source


def test_direct_submit_locks_stale_checks_revalidates_then_native_submits():
	source = _read(SERVICE)
	start = source.index("def submit_standard_internal_transfer")
	end = source.index('@frappe.whitelist(methods=["POST"])', start + 10)
	method = source[start:end]
	for contract in (
		"FOR UPDATE",
		"expected_modified",
		"_validate_transfer_context",
		"_standard_transfer_blockers",
		"_validate_accounts",
		"_validate_cash_deposit_context",
		"get_workflow_readiness",
		'_clean(workflow_readiness.get("source")) == "frappe"',
		'frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "submit", doc=doc)',
		"doc.submit()",
	):
		assert contract in method
	for forbidden in (
		".docstatus =",
		".workflow_state =",
		"frappe.db.commit",
		"ignore_permissions=True",
	):
		assert forbidden not in method


def test_workflow_action_uses_f3f27_and_never_assigns_status_truth():
	source = _read(SERVICE)
	method = source[source.index("def apply_standard_internal_transfer_workflow_action"):]
	for contract in (
		"FOR UPDATE",
		"expected_modified",
		"expected_workflow_state",
		"_validate_transfer_context",
		"_validate_accounts",
		"_validate_cash_deposit_context",
		"get_workflow_readiness",
		"apply_document_workflow_action(",
		"expected_modified=expected_modified",
		"expected_state=str(expected_workflow_state or",
	):
		assert contract in method
	assert ".workflow_state =" not in method
	assert ".docstatus =" not in method


def test_backend_never_writes_gl_or_payment_ledger_directly():
	source = _read(SERVICE)
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Payment Ledger Entry")',
		"frappe.db.set_value",
	):
		assert forbidden not in source


def test_completion_dialog_uses_server_authoritative_actions_only():
	source = _read(DIALOG)
	for contract in (
		"get_standard_internal_transfer_completion_preview",
		"submit_standard_internal_transfer",
		"apply_standard_internal_transfer_workflow_action",
		"workflow_readiness?.available_actions",
		"expected_modified",
		"expected_workflow_state",
		"Advanced: Open in ERPNext",
	):
		assert contract in source
	for forbidden in (".workflow_state =", ".docstatus =", ".status ="):
		assert forbidden not in source


def test_business_hub_opens_completion_after_cash_deposit_and_transfer():
	source = _read(HUB)
	assert 'import StandardInternalTransferCompletionDialog from "./StandardInternalTransferCompletionDialog.vue"' in source
	assert "handleSimpleCashDepositSaved(result)" in source
	assert "handleSimpleCashTransferSaved(result)" in source
	assert 'this.openInternalTransferCompletion({ doctype: "Payment Entry", name: result.name })' in source
	assert "internalTransferCompletionOpen" in source
	assert "internalTransferCompletionDocument" in source


def test_existing_draft_creators_remain_draft_only():
	for path in (CASH_CUSTODY, CASH_TRANSFER):
		source = _read(path)
		assert "doc.insert()" in source
		assert "doc.submit()" not in source


def test_existing_cash_deposit_before_submit_hook_remains_installed():
	source = _read(HOOKS)
	assert '"Payment Entry": {' in source
	assert '"before_submit": "retailedge.cash_custody.validate_cash_deposit_before_submit"' in source
	custody = _read(CASH_CUSTODY)
	assert "SELECT name FROM `tabPOS Opening Shift` WHERE name = %s FOR UPDATE" in custody
	assert "validate_cash_deposit_bank_destination(doc)" in custody


def test_cash_movement_remains_posted_gl_truth():
	source = _read(CASH_MOVEMENT)
	assert "FROM `tabGL Entry` gle" in source
	assert "doc.submit()" not in source


def test_contract_keeps_shift_close_and_reconciliation_out_of_scope():
	source = _read(CONTRACT)
	assert "cashier shift closing mechanics" in source
	assert "Payment Reconciliation" in source
