from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from retailedge import business_expense


ROOT = Path(__file__).resolve().parents[1]
BUSINESS_UI = ROOT / "public/js/business_expenses/BusinessExpenses.vue"
PAYMENT_UI = ROOT / "public/js/payment_management/PaymentManagement.vue"
PURCHASING_UI = ROOT / "public/js/professional_purchasing/ProfessionalPurchasing.vue"
G2B_SERVICE = ROOT / "standard_purchase_invoice_completion.py"
G2A_MASTER = ROOT / "master_experience.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


class TestRIR2G2C1LocalOperationalTableSorting(TestCase):
	def test_business_expense_sort_contract_is_allowlisted(self):
		self.assertEqual(
			business_expense.BUSINESS_EXPENSE_SORT_FIELDS,
			{
				"expense_date",
				"expense_category",
				"payee_name",
				"branch",
				"expense_status",
				"ledger_status",
				"amount",
				"modified",
				"name",
			},
		)
		self.assertEqual(business_expense.BUSINESS_EXPENSE_SORT_DIRECTIONS, {"asc", "desc"})
		self.assertEqual(
			business_expense.DEFAULT_BUSINESS_EXPENSE_ORDER,
			"expense_date desc, modified desc, name desc",
		)

	def test_business_expense_invalid_sort_preserves_historical_default(self):
		for value in (
			None,
			{},
			{"field": "description", "direction": "asc"},
			{"field": "amount", "direction": "drop table"},
			'{"field":"description","direction":"asc"}',
		):
			normalized, order_by = business_expense._normalise_business_expense_sort(value)
			self.assertIsNone(normalized)
			self.assertEqual(order_by, business_expense.DEFAULT_BUSINESS_EXPENSE_ORDER)

	def test_business_expense_valid_sort_is_deterministic(self):
		normalized, order_by = business_expense._normalise_business_expense_sort(
			{"field": "amount", "direction": "asc"}
		)
		self.assertEqual(normalized, {"field": "amount", "direction": "asc"})
		self.assertEqual(order_by, "amount asc, modified desc, name desc")

		normalized, order_by = business_expense._normalise_business_expense_sort(
			'{"field":"expense_date","direction":"desc"}'
		)
		self.assertEqual(normalized, {"field": "expense_date", "direction": "desc"})
		self.assertEqual(order_by, "expense_date desc, modified desc, name desc")

	def test_business_expense_endpoint_uses_normalized_sort_only(self):
		source = _read(ROOT / "business_expense.py")
		self.assertIn("sort: dict[str, Any] | str | None = None", source)
		self.assertIn("normalized_sort, order_by = _normalise_business_expense_sort(sort)", source)
		self.assertIn("order_by=order_by", source)
		self.assertIn('"sort": normalized_sort', source)
		self.assertNotIn('order_by=f"{', source)

	def test_business_expense_ui_sends_sort_and_resets_page(self):
		source = _read(BUSINESS_UI)
		self.assertIn("listSort: null", source)
		self.assertIn("sort: this.listSort", source)
		self.assertIn("sortBusinessExpenses(field)", source)
		self.assertIn("this.pagination.page = 1", source)
		self.assertIn('sortBusinessExpenses("expense_date")', source)
		self.assertIn('sortBusinessExpenses("amount")', source)
		self.assertIn('v-for="row in rows"', source)

	def test_business_expense_visible_data_headers_are_sortable(self):
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
			self.assertIn(f'sortBusinessExpenses("{field}")', source)
		self.assertIn("sortBusinessExpenseMark(field)", source)

	def test_payment_management_has_separate_bounded_table_sort_state(self):
		source = _read(PAYMENT_UI)
		for marker in (
			"draftPaymentSort: null",
			"settlementAdvanceSort: null",
			"customerAdvanceSort: null",
			"sortedDraftPayments()",
			"sortedSettlementAdvances()",
			"sortedCustomerAdvances()",
		):
			self.assertIn(marker, source)

	def test_payment_management_renders_sorted_rows_and_non_sortable_action_columns(self):
		source = _read(PAYMENT_UI)
		self.assertIn('v-for="row in sortedDraftPayments"', source)
		self.assertIn('v-for="row in sortedSettlementAdvances"', source)
		self.assertIn('v-for="row in sortedCustomerAdvances"', source)
		self.assertIn("<th>Action</th>", source)
		self.assertIn('<th class="num">Apply</th>', source)
		self.assertIn("<th>Actions</th>", source)
		for marker in (
			"sortDraftPaymentsBy(field)",
			"sortSettlementAdvancesBy(field)",
			"sortCustomerAdvancesBy(field)",
			"nextLocalSort(",
			"sortedCopy(",
		):
			self.assertIn(marker, source)

	def test_payment_sort_comparator_is_type_aware_and_empty_last(self):
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
			self.assertIn(marker, source)

	def test_settlement_allocations_remain_payment_entry_keyed(self):
		source = _read(PAYMENT_UI)
		self.assertIn("settlement.allocations[row.name]", source)
		self.assertIn("Object.entries(this.settlement.allocations || {})", source)

	def test_professional_purchasing_draft_queue_is_locally_sortable_and_bounded(self):
		source = _read(PURCHASING_UI)
		self.assertIn("draftInvoiceSort: null", source)
		self.assertIn("sortedDraftPurchaseInvoices()", source)
		self.assertIn('v-for="row in sortedDraftPurchaseInvoices"', source)
		self.assertIn("sortDraftInvoicesBy(key)", source)
		self.assertIn("draftInvoiceSortMark(key)", source)
		self.assertIn("limit: 20", source)
		self.assertIn("<th>Action</th>", source)

	def test_g2b_and_g2a_contracts_remain_present(self):
		self.assertIn("get_standard_purchase_invoice_completion_queue", _read(G2B_SERVICE))
		self.assertIn("_contain_native_navigation_for_edgesuite_only", _read(G2A_MASTER))
