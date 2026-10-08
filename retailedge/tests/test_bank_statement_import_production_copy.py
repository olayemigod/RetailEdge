from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/bank_statement_imports/BankStatementImports.vue"


def test_bank_statement_imports_uses_business_copy_and_preserves_governed_bank_transaction_flow():
	text = COMPONENT.read_text(encoding="utf-8")

	for marker in (
		"Required interface components are unavailable",
		"governed Bank Transactions without leaving this workspace",
		"Advanced: Open Statement Imports",
		"accounting is created only through Bank Transactions",
		"Create or link Bank Transactions for valid statement rows?",
		"Advanced: Open Full Record",
	):
		assert marker in text

	for forbidden in (
		"Required EdgeSuite components are unavailable",
		"governed ERPNext Bank Transactions without leaving EdgeSuite",
		"Advanced: ERPNext List",
		"through ERPNext Bank Transactions",
		"Create or link ERPNext Bank Transactions",
	):
		assert forbidden not in text

	for marker in (
		'window.EdgeSuiteUI?.components',
		'v-if="canUseNativeDesk"',
		'@click="openNativeList"',
		'@click="openNativeRecord"',
		'frappe.set_route("List", "RetailEdge Payment Statement Import")',
		'frappe.set_route("Form", "RetailEdge Payment Statement Import"',
		"retailedge.payment_statement_import_workspace",
		"confirmAboveEdgeModal",
		"Create Bank Transactions",
	):
		assert marker in text
