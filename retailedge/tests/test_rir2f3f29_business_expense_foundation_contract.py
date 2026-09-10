from __future__ import annotations

import inspect
import json
from pathlib import Path

from retailedge import business_expense
from retailedge import workflow_actions
from retailedge import workflow_readiness


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT.parent
DOCTYPE_JSON = (
	ROOT
	/ "retailedge/doctype/retailedge_business_expense/retailedge_business_expense.json"
)
SETTINGS_JSON = (
	ROOT
	/ "retailedge/doctype/retailedge_settings/retailedge_settings.json"
)
DOC = APP_ROOT / "docs/rir2f3f29_business_expense_foundation.md"


def test_business_expense_is_separate_from_cashier_expense_and_has_no_pos_fields():
	data = json.loads(DOCTYPE_JSON.read_text(encoding="utf-8"))
	assert data["name"] == "RetailEdge Business Expense"
	fields = {row["fieldname"] for row in data["fields"]}
	assert "expense_category" in fields
	assert "payment_account" in fields
	assert "workflow_state" in fields
	assert "posting_reference" in fields
	assert "pos_profile" not in fields
	assert "linked_pos_opening_shift" not in fields
	assert "cashier" not in fields


def test_business_expense_settings_define_simple_fallback_process():
	data = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
	fields = {row["fieldname"]: row for row in data["fields"]}
	assert fields["enable_business_expenses"]["default"] == "1"
	assert (
		fields["business_expense_process"]["options"]
		== "Approval Required\\nDirect Posting"
	)
	assert fields["business_expense_posting_document_type"]["options"] == "Journal Entry"


def test_business_expense_validation_is_company_branch_and_account_aware():
	source = inspect.getsource(business_expense)
	assert "get_operational_branch_scope" in source
	assert "get_exact_branch_profile" in source
	assert "_validate_expense_account" in source
	assert "_validate_payment_account" in source
	assert "_validate_cost_center" in source
	assert "ignore_permissions" not in source


def test_workflow_readiness_has_business_expense_fallback_but_frappe_still_wins():
	source = inspect.getsource(workflow_readiness)
	assert 'if workflow:' in source
	assert 'if doctype == "RetailEdge Business Expense":' in source
	assert "_retailedge_business_expense_workflow_enabled" in source
	assert "RetailEdge Business Expense Approval" in source


def test_workflow_action_bridge_supports_business_expense_without_direct_state_mutation():
	source = inspect.getsource(workflow_actions)
	assert "BUSINESS_EXPENSE_DOCTYPE" in source
	assert "_apply_business_expense_lifecycle" in source
	assert "apply_workflow(doc, action)" in source
	assert ".workflow_state =" not in source
	assert ".docstatus =" not in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source


def test_foundation_deliberately_does_not_post_accounting_yet():
	source = inspect.getsource(business_expense)
	assert "frappe.new_doc(\"Journal Entry\")" not in source
	assert "frappe.new_doc('Journal Entry')" not in source
	doc = DOC.read_text(encoding="utf-8")
	assert "does not create Journal Entry or GL Entry" in doc
	assert "Cashier Expense remains a separate POS/shift workflow" in doc
