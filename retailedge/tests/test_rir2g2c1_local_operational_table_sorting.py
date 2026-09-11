from __future__ import annotations

from pathlib import Path

from retailedge import business_expense


ROOT = Path(__file__).resolve().parents[1]
BUSINESS_UI = ROOT / "public/js/business_expenses/BusinessExpenses.vue"
PAYMENT_UI = ROOT / "public/js/payment_management/PaymentManagement.vue"
PURCHASING_UI = ROOT / "public/js/professional_purchasing/ProfessionalPurchasing.vue"
G2B_SERVICE = ROOT / "standard_purchase_invoice_completion.py"
G2A_MASTER = ROOT / "master_experience.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_business_expense_sort_contract_is_allowlisted():
	assert business_expense.BUSINESS_EXPENSE_SORT_FIELDS == {
		"expense_date",
		"expense_category",
		"payee_name",
		"branch",
		"expense_status",
		"ledger_status",
		"amount",
		"modified",
		"name",
	}
	assert business_expense.BUSINESS_EXPENSE_SORT_DIRECTIONS == {"asc", "desc"}
	assert (
		business_expense.DEFAULT_BUSINESS_EXPENSE_ORDER
		== "expense_date desc, modified desc, name desc"
	)


def test_business_expense_invalid_sort_preserves_historical_default():
	for value in (
		None,
		{},
		{"field": "description", "direction": "asc"},
		{"field": "amount", "direction": "drop table"},
		'{"field":"description","direction":"asc"}',
	):
		normalized, order_by = business_expense._normalise_business_expense_sort(value)
		assert normalized is None
		assert order_by == business_expense.DEFAULT_BUSINESS_EXPENSE_ORDER


def test_business_expense_valid_sort_is_deterministic():
	normalized, order_by = business_expense._normalise_business_expense_sort(
		{"field": "amount", "direction": "asc"}
	)
	assert normalized == {"field": "amount", "direction": "asc"}
	assert order_by == "amount asc, modified desc, name desc"

	normalized, order_by = business_expense._normalise_business_expense_sort(
		'{"field":"expense_date","direction":"desc"}'
	)
	assert normalized == {"field": "expense_date", "direction": "desc"}
	assert order_by == "expense_date desc, modified desc, name desc"


def test_business_expense_endpoint_uses_normalized_sort_only():
	source = _read(ROOT / "business_expense.py")
	assert "sort: dict[str, Any] | str | None = None" in source
	assert "normalized_sort, order_by = _normalise_business_expense_sort(sort)" in source
	assert "order_by=order_by" in source
	assert '"sort": normalized_sort' in source
	assert 'order_by=f"{' not in source


def test_business_expense_ui_sends_sort_and_resets_page():
	source = _read(BUSINESS_UI)
	assert "listSort: null" in source
	assert "sort: this.listSort" in source
	assert "sortBusinessExpenses(field)" in source
	assert "this.pagination.page = 1" in source
	assert 'sortBusinessExpenses("expense_date")' in source
	assert 'sortBusinessExpenses("amount")' in source
	assert 'v-for="row in rows"' in source


def test_business_expense_visible_data_headers_are_sortable():
	source = _read(BUSINESS_UI)
	for field in (
		"expense_date",
		"expense_category",
		"payee_name",
		"branch",
		"expense_status",
		"ledger_status",
		"amount",
	):
		assert f'sortBusinessExpenses("{field}")' in source
	assert "sortBusinessExpenseMark(field)" in source


def test_payment_management_has_separate_bounded_table_sort_state():
	source = _read(PAYMENT_UI)
	for marker in (
		"draftPaymentSort: null",
		"settlementAdvanceSort: null",
		"customerAdvanceSort: null",
		"sortedDraftPayments()",
		"sortedSettlementAdvances()",
		"sortedCustomerAdvances()",
	):
		assert marker in source


def test_payment_management_renders_sorted_rows_and_non_sortable_action_columns():
	source = _read(PAYMENT_UI)
	assert 'v-for="row in sortedDraftPayments"' in source
	assert 'v-for="row in sortedSettlementAdvances"' in source
	assert 'v-for="row in sortedCustomerAdvances"' in source
	assert '<th>Action</th>' in source
	assert '<th class="num">Apply</th>' in source
	assert '<th>Actions</th>' in source
	for marker in (
		"sortDraftPaymentsBy(field)",
		"sortSettlementAdvancesBy(field)",
		"sortCustomerAdvancesBy(field)",
		"nextLocalSort(",
		"sortedCopy(",
	):
		assert marker in source


def test_payment_sort_comparator_is_type_aware_and_empty_last():
	source = _read(PAYMENT_UI)
	for marker in (
		"function comparableValue",
		'kind: "empty"',
		'kind: "number"',
		'kind: "date"',
		'kind: "text"',
		"localeCompare",
		"empty",
	):
		assert marker in source


def test_settlement_allocations_remain_payment_entry_keyed():
	source = _read(PAYMENT_UI)
	assert "settlement.allocations[row.name]" in source
	assert "Object.entries(this.settlement.allocations || {})" in source


def test_professional_purchasing_draft_queue_is_locally_sortable_and_bounded():
	source = _read(PURCHASING_UI)
	assert "draftInvoiceSort: null" in source
	assert "sortedDraftPurchaseInvoices()" in source
	assert 'v-for="row in sortedDraftPurchaseInvoices"' in source
	assert "sortDraftInvoicesBy(field)" in source
	assert "draftInvoiceSortMark(field)" in source
	assert "limit: 20" in source
	assert "<th>Action</th>" in source


def test_g2b_and_g2a_contracts_remain_present():
	assert "get_standard_purchase_invoice_completion_queue" in _read(G2B_SERVICE)
	assert "_contain_native_navigation_for_edgesuite_only" in _read(G2A_MASTER)
