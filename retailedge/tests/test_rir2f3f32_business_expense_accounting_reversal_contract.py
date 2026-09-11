from __future__ import annotations

import inspect
import json
from pathlib import Path

from retailedge import business_expense
from retailedge import business_expense_register
from retailedge import business_expense_reversal


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_JSON = (
	ROOT
	/ "retailedge/doctype/retailedge_business_expense/retailedge_business_expense.json"
)
PAGE = ROOT / "public/js/business_expenses/BusinessExpenses.vue"
DOC = ROOT.parent / "docs/rir2f3f32_business_expense_accounting_reversal.md"


def test_reversal_is_additive_audit_metadata_on_business_expense():
	data = json.loads(DOCTYPE_JSON.read_text(encoding="utf-8"))
	fields = {row["fieldname"]: row for row in data["fields"]}
	for fieldname in (
		"reversal_reference_type",
		"reversal_reference",
		"reversal_posting_date",
		"reversal_reason",
		"reversed_by",
		"reversed_on",
	):
		assert fieldname in fields
		assert fields[fieldname].get("allow_on_submit") == 1
		assert fields[fieldname].get("read_only") == 1
	assert "Reversed" in fields["expense_status"]["options"].splitlines()
	assert "Reversed" in fields["ledger_status"]["options"].splitlines()


def test_business_expense_payload_exposes_reversal_audit_fields():
	source = inspect.getsource(business_expense._business_expense_payload)
	for fieldname in (
		"reversal_reference_type",
		"reversal_reference",
		"reversal_posting_date",
		"reversal_reason",
		"reversed_by",
		"reversed_on",
	):
		assert f'"{fieldname}"' in source
	assert '"Reversed",' in inspect.getsource(business_expense)


def test_reversal_action_is_locked_stale_safe_and_idempotent():
	source = inspect.getsource(
		business_expense_reversal.reverse_business_expense_posting
	)
	assert "_lock_business_expense(name)" in source
	assert source.index("_journal_reference_state(") < source.index(
		"_assert_modified(doc, expected_modified)"
	)
	assert 'if existing["submitted"]:' in source
	assert "idempotent=True" in source
	assert "Reversal reason is required." in source
	assert "_assert_reversal_access(doc)" in source
	assert "build_business_expense_reversal_readiness(doc)" in source


def test_reversal_never_cancels_or_mutates_original_submitted_journal():
	source = inspect.getsource(business_expense_reversal)
	reverse_source = inspect.getsource(
		business_expense_reversal.reverse_business_expense_posting
	)
	assert "frappe.get_doc(POSTING_DOCUMENT_TYPE, doc.posting_reference)" in reverse_source
	assert "reversal = _build_reversal_journal_entry(" in reverse_source
	assert "reversal.insert()" in reverse_source
	assert "reversal.submit()" in reverse_source
	assert ".cancel()" not in source
	assert "ignore_permissions" not in source
	assert 'frappe.new_doc("GL Entry")' not in source
	assert "frappe.db.commit" not in source


def test_reversal_validates_exact_original_two_line_posting_contract():
	source = inspect.getsource(
		business_expense_reversal._validate_original_posting_contract
	)
	assert "len(rows) != 2" in source
	assert "row.account == doc.expense_account" in source
	assert "row.account == doc.payment_account" in source
	assert "_same_amount(row.debit_in_account_currency, amount)" in source
	assert "_same_amount(row.credit_in_account_currency, amount)" in source
	assert "expense_row.cost_center != doc.cost_center" in source
	assert "expense_row.project != doc.project" in source
	assert 'meta.has_field("retailedge_branch")' in source


def test_reversal_mapping_is_exact_inverse_of_direct_paid_spend():
	source = inspect.getsource(
		business_expense_reversal._build_reversal_journal_entry
	)
	assert '"account": doc.payment_account' in source
	assert '"debit_in_account_currency": amount' in source
	assert '"account": doc.expense_account' in source
	assert '"credit_in_account_currency": amount' in source
	assert 'expense_row["cost_center"] = doc.cost_center' in source
	assert 'expense_row["project"] = doc.project' in source
	assert "original.name" in source
	assert "reason" in source


def test_reversal_date_cannot_precede_original_posting_date():
	source = inspect.getsource(
		business_expense_reversal.reverse_business_expense_posting
	)
	assert "reversal_date < getdate(original.posting_date)" in source
	assert "cannot be before the original accounting posting date" in source


def test_reversal_finalisation_preserves_active_workflow_state():
	source = inspect.getsource(
		business_expense_reversal.reverse_business_expense_posting
	)
	assert '"ledger_status": "Reversed"' in source
	assert 'if not _get_active_workflow(BUSINESS_EXPENSE_DOCTYPE):' in source
	assert 'result_fields["expense_status"] = "Reversed"' in source
	assert "workflow_state" not in source


def test_expense_register_shows_positive_original_and_negative_reversal():
	source = inspect.getsource(business_expense_register)
	assert '"Business Expense Reversal",' in source
	assert "def _build_business_expense_reversal_where_sql" in source
	assert "CONCAT('BER:', be.name)" in source
	assert "(0 - be.amount) AS amount" in source
	assert "'Business Expense Reversal' AS source_type" in source
	assert "be.reversal_reference = be_rje.name" in source
	assert "be_rje.docstatus = 1" in source
	assert "be.ledger_status IN ('Posted', 'Reversed')" in source


def test_expense_register_dedupes_original_and_reversal_journal_gl_rows():
	source = inspect.getsource(business_expense_register)
	assert "be_post.posting_reference = gle.voucher_no" in source
	assert "be_reverse.reversal_reference = gle.voucher_no" in source
	assert 'clauses.append("be_post.name IS NULL")' in source
	assert 'clauses.append("be_reverse.name IS NULL")' in source


def test_edgesuite_owns_reversal_with_explicit_reason_and_posting_date():
	source = PAGE.read_text(encoding="utf-8")
	assert "get_business_expense_reversal_readiness" in source
	assert "reverse_business_expense_posting" in source
	assert "Reverse Accounting" in source
	assert 'fieldname: "posting_date"' in source
	assert 'fieldname: "reason"' in source
	assert "The original accounting entry remains unchanged." in source
	assert "expected_modified: this.current.modified" in source
	assert 'frappe.set_route("Form", "Journal Entry"' not in source


def test_contract_preserves_accounting_truth_and_defers_partial_reversal():
	doc = DOC.read_text(encoding="utf-8")
	assert "original submitted Journal Entry is never cancelled or edited" in doc
	assert "new submitted Journal Entry" in doc
	assert "partial reversal is out of scope" in doc
	assert "normal site migration is required" in doc
	assert "Manual browser/persona QA remains deferred" in doc

def test_posted_business_expense_native_workflow_state_is_server_terminal():
	source = inspect.getsource(
		business_expense._assert_posted_business_expense_workflow_terminal
	)
	validate_source = inspect.getsource(business_expense.validate_business_expense_document)
	assert "_assert_posted_business_expense_workflow_terminal(doc)" in validate_source
	assert '"posting_reference", "workflow_state"' in source
	assert "previous.posting_reference" in source
	assert "cannot move to another Workflow State" in source

