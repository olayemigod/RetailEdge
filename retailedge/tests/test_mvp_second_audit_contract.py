from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master_experience.py"
HUB = ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
RC3 = ROOT.parent / "docs" / "rir2e_consolidated_browser_persona_qa.md"


def test_business_expense_replaces_cashier_expense_as_primary_intent_when_available():
	source = MASTER.read_text(encoding="utf-8")
	assert "BUSINESS_EXPENSE_QUICK_ACTION" in source
	assert '"key": "record-expense"' in source
	assert '"label": "Record Expense"' in source
	assert '"target": "business-expenses"' in source
	assert 'frappe.has_permission(BUSINESS_EXPENSE_NATIVE_PEER_DOCTYPE, "create")' in source
	assert 'if action.get("key") == "record-expense"' in source


def test_cashier_expense_remains_fallback_for_cashier_only_context():
	source = HUB.read_text(encoding="utf-8")
	assert 'if (action.doctype === "RetailEdge Business Expense" || action.target === "business-expenses")' in source
	assert 'frappe.route_options = { action: "new" };' in source
	assert 'frappe.set_route("business-expenses");' in source
	assert "this.simpleCashierExpenseOpen = true;" in source


def test_business_hub_exposes_approved_mvp_shortcut_set():
	source = HUB.read_text(encoding="utf-8")
	for contract in (
		'addAction("new-sales-invoice", "Make Sale")',
		'addAction("receive-customer-payment")',
		'addAction("pay-supplier")',
		'addAction("record-expense")',
		'addPage("professional-purchasing", "Receive Stock"',
		'addAction("transfer-stock")',
		'addAction("record-purchase")',
		'addPage("bank-matching-reconciliation", "Match Bank Transactions"',
	):
		assert contract in source
	assert 'v-if="homeQuickActions.length"' in source
	assert '@click="runHomeQuickAction(shortcut)"' in source


def test_home_route_shortcuts_are_permission_derived_from_final_navigation():
	source = HUB.read_text(encoding="utf-8")
	assert "const pageTargets = new Set(" in source
	assert '(this.navigationGroups || [])' in source
	assert '.filter((item) => item.target_type === "Page")' in source
	assert "if (!pageTargets.has(target)) return;" in source


def test_rc3_contract_matches_current_stock_movement_and_frappe_v16_routing():
	source = RC3.read_text(encoding="utf-8")
	assert "retailedge_mvp_second_audit_20260912.md" in source
	assert "Frappe v16 Desk routing is handled correctly" in source
	assert "Stock Movement History is now part of the EdgeSuite-owned 1.0 composition" in source
	assert "Stock Movement History remains on its existing Query Report" not in source
	assert "Do **not** use RIR2E to promote" not in source
