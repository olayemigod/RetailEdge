from __future__ import annotations

import json
import unittest
from pathlib import Path

import frappe

from retailedge.bank_transaction_matching import (
	_build_journal_entry_candidate,
	_derive_action_status,
)
from retailedge.professional_sales_invoice import get_sales_return_outstanding_policy


APP_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_JS = APP_ROOT / "public" / "js"


class _Meta:
	def __init__(self, fields: set[str]):
		self.fields = fields

	def has_field(self, fieldname: str) -> bool:
		return fieldname in self.fields


class _Doc(dict):
	def __init__(self, *args, fields: set[str] | None = None, **kwargs):
		super().__init__(*args, **kwargs)
		self.meta = _Meta(fields or set())
		self.name = self.get("name", "")

	def __getattr__(self, item):
		try:
			return self[item]
		except KeyError as exc:
			raise AttributeError(item) from exc


class WorkflowIntegrityAuditTests(unittest.TestCase):
	def test_cashier_expense_posting_is_merchant_governed_and_journal_entry_only(self):
		settings_path = (
			APP_ROOT
			/ "retailedge"
			/ "doctype"
			/ "retailedge_settings"
			/ "retailedge_settings.json"
		)
		settings = json.loads(settings_path.read_text(encoding="utf-8"))
		fields = {field["fieldname"]: field for field in settings["fields"]}
		posting_type = fields["cashier_expense_posting_document_type"]
		self.assertEqual(posting_type.get("options"), "Journal Entry")
		self.assertIn("cashier_expense_posting_roles", fields)
		self.assertEqual(
			fields["cashier_expense_posting_roles"].get("options"),
			"RetailEdge Cashier Expense Posting Role",
		)
		self.assertIn("cashier_expense_posting_workflow_state", fields)
		self.assertEqual(
			fields["cashier_expense_posting_workflow_state"].get("options"),
			"Workflow State",
		)
		posting_source = (APP_ROOT / "cashier_expense_accounting.py").read_text(encoding="utf-8")
		self.assertIn('"ledger_status": "Pending Ledger"', posting_source)
		self.assertIn("get_effective_cashier_expense_posting_roles", posting_source)
		self.assertNotIn("and posting_role", (APP_ROOT / "cashier_expense_detail.py").read_text(encoding="utf-8"))

	def test_cashier_workflow_and_ledger_statuses_remain_distinct(self):
		accounting = (APP_ROOT / "cashier_expense_accounting.py").read_text(encoding="utf-8")
		detail = (APP_ROOT / "cashier_expense_detail.py").read_text(encoding="utf-8")
		self.assertIn('workflow_active = bool(_get_active_workflow("RetailEdge Cashier Expense"))', accounting)
		self.assertIn('new_status=previous_status if workflow_active else "Posted"', accounting)
		self.assertIn('"ledger_status": "Posted"', accounting)
		self.assertIn('"workflow_status_preserved": workflow_active', accounting)
		self.assertIn("if workflow_controlled:", detail)
		self.assertIn("No Cashier Expense workflow action is currently available to this user.", detail)

	def test_cash_movement_uses_gl_truth_and_expense_journal_entries_are_money_out(self):
		source = (APP_ROOT / "cash_movement.py").read_text(encoding="utf-8")
		self.assertIn("FROM `tabGL Entry` gle", source)
		self.assertIn("tabRetailEdge Cashier Expense", source)
		self.assertIn("tabRetailEdge Business Expense", source)
		self.assertIn("ce.posting_reference = gle.voucher_no", source)
		self.assertIn("be.posting_reference = gle.voucher_no", source)
		expense_money_out = source.index("AND gle.credit > 0 THEN 'Money Out'")
		generic_adjustment = source.index("WHEN gle.voucher_type = 'Journal Entry' THEN 'Adjustment'")
		self.assertLess(expense_money_out, generic_adjustment)

	def test_bank_match_queue_requires_submitted_bank_truth_and_supports_outflows(self):
		source = (APP_ROOT / "bank_transaction_matching.py").read_text(encoding="utf-8")
		self.assertIn('filters_payload = {"docstatus": 1}', source)
		self.assertIn('filters_payload["clearance_date"] = ["is", "not set"]', source)
		self.assertIn("journal_entries_by_bank_transaction", source)
		self.assertIn("find_journal_entry_candidates_for_bank_transaction", source)
		self.assertIn('"journal_entry_match": "Journal Entry Match"', source)
		self.assertIn('"Journal Entry"', source.split("def get_review_creation_block_reason", 1)[1].split("return", 1)[0])
		self.assertNotIn(
			"Outflow transactions are not eligible for customer receipt bank matching in this phase.",
			source,
		)

	def test_operational_reconciliation_readiness_preserves_direction_and_journal_entries(self):
		source = (APP_ROOT / "bank_matching_operational_reports.py").read_text(encoding="utf-8")
		self.assertIn("find_journal_entry_candidates_for_bank_transaction", source)
		self.assertIn('"journal_entry_match"', source)
		self.assertIn('"bank_direction"', source)
		self.assertIn('"candidate_docstatus"', source)
		self.assertIn('loaded.get("bank_context")', source)
		self.assertIn('loaded.get("candidate_context")', source)
		self.assertNotIn('"direction": "Inflow",\n\t\t\t"is_reconciled"', source)

	def test_journal_entry_candidate_is_payment_event_but_not_sales_invoice_context(self):
		candidate = _build_journal_entry_candidate(
			{
				"amount": 7500,
				"direction": "Outflow",
			},
			frappe._dict(
				{
					"name": "JV-TEST-1",
					"posting_date": "2026-10-01",
					"_bank_line_amount": 7500,
					"_bank_account": "Bank - TC",
					"_party_type": "Supplier",
					"_party": "SUP-1",
				}
			),
		)
		self.assertEqual(candidate["document_type"], "Journal Entry")
		self.assertEqual(candidate["candidate_category"], "journal_entry_match")
		self.assertEqual(candidate["amount_scenario"], "Submitted Journal Entry Amount")
		self.assertEqual(candidate["payment_event_found"], 1)
		self.assertEqual(candidate["payment_account"], "Bank - TC")

	def test_outflow_payment_candidate_can_be_suggested(self):
		status = _derive_action_status(
			{"direction": "Outflow", "is_reconciled": False},
			{"document_type": "Payment Entry", "confidence": "Strong Match"},
		)
		self.assertEqual(status, "Suggested")

	def test_internal_transfer_bank_matching_is_leg_aware_and_manual_review_first(self):
		matching = (APP_ROOT / "bank_transaction_matching.py").read_text(encoding="utf-8")
		workflow = (APP_ROOT / "bank_transaction_match_workflow.py").read_text(encoding="utf-8")
		self.assertIn("def payment_entry_active_match_conflict(", matching)
		self.assertIn('payment_type != "Internal Transfer"', matching)
		self.assertIn("current_account", matching)
		self.assertIn("resolved_bank_account", matching)
		self.assertIn('"payment_entry_payment_type": payment_entry.get("payment_type")', matching)
		self.assertIn("Internal Transfer Payment Entries require human review", matching)
		self.assertIn("payment_entry_active_match_conflict(", workflow)
		self.assertIn("Payment Entry bank leg already has a confirmed bank match", workflow)

	def test_journal_entry_candidates_can_reach_review_with_live_revalidation(self):
		workflow = (APP_ROOT / "bank_transaction_match_workflow.py").read_text(encoding="utf-8")
		self.assertIn("find_journal_entry_candidates_for_bank_transaction", workflow)
		self.assertIn('candidate_doctype not in {"Sales Invoice", "Payment Entry", "Journal Entry"}', workflow)
		self.assertIn('elif candidate_doctype == "Journal Entry":', workflow)
		self.assertIn('"Journal Entry Account"', workflow)
		self.assertIn('"Submitted Journal Entry Amount"', workflow)
		self.assertIn('"journal_entry_match"', workflow)
		self.assertIn('cstr(candidate.get("document_type")).strip() not in {"Sales Invoice", "Payment Entry", "Journal Entry"}', workflow)
		self.assertIn("doc.payment_event_source = candidate.get", workflow)
		self.assertIn("doc.payment_account = candidate.get", workflow)

	def test_exact_payment_draft_reuse_is_bounded_and_never_rewrites_other_drafts(self):
		source = (APP_ROOT / "guided_payment.py").read_text(encoding="utf-8")
		self.assertIn("def _find_exact_reusable_payment_draft(", source)
		self.assertIn("limit_page_length=10", source)
		self.assertIn("Multiple compatible draft Payment Entries already exist", source)
		self.assertIn('"existing": bool(existing)', source)
		self.assertIn('"reused": bool(existing)', source)
		reuse_body = source.split("def _find_exact_reusable_payment_draft(", 1)[1].split("@frappe.whitelist", 1)[0]
		self.assertNotIn(".save()", reuse_body)
		self.assertNotIn(".submit()", reuse_body)

	def test_bank_referenced_internal_transfer_reuses_exact_draft(self):
		source = (APP_ROOT / "guided_cash_transfer.py").read_text(encoding="utf-8")
		self.assertIn("def _existing_internal_transfer_draft(", source)
		self.assertIn('"payment_type": "Internal Transfer"', source)
		self.assertIn('"reference_no": reference_no', source)
		self.assertIn("limit_page_length=3", source)
		self.assertIn('"reused": bool(reused)', source)
		self.assertIn("Multiple matching draft Internal Transfer Payment Entries already exist", source)

	def test_credit_note_policy_matches_erpnext_outstanding_semantics(self):
		source = _Doc(
			{"name": "ACC-SINV-1", "outstanding_amount": 5000},
			fields={"outstanding_amount"},
		)
		full_credit = _Doc(
			{"grand_total": -3000},
			fields={"update_outstanding_for_self"},
		)
		policy = get_sales_return_outstanding_policy(source, full_credit)
		self.assertEqual(policy["mode"], "reduce_source_outstanding")
		self.assertEqual(policy["update_outstanding_for_self"], 0)

		excess_credit = _Doc(
			{"grand_total": -7000},
			fields={"update_outstanding_for_self"},
		)
		policy = get_sales_return_outstanding_policy(source, excess_credit)
		self.assertEqual(policy["mode"], "credit_note_outstanding")
		self.assertEqual(policy["update_outstanding_for_self"], 1)

	def test_credit_note_completion_explains_outstanding_treatment(self):
		ui = (PUBLIC_JS / "professional_selling" / "StandardSalesInvoiceCompletionDialog.vue").read_text(encoding="utf-8")
		self.assertIn("Credit Note outstanding treatment", ui)
		self.assertIn("preview.return_outstanding_policy?.message", ui)
		self.assertIn("Update Outstanding for Self turned off", ui)
		self.assertIn("later reconciliation or refund", ui)

	def test_selling_lineage_routes_existing_documents_and_reuses_drafts(self):
		source = (APP_ROOT / "professional_selling.py").read_text(encoding="utf-8")
		self.assertIn('"value": "open-existing-document"', source)
		self.assertIn("has_draft_delivery", source)
		self.assertIn("has_draft_invoice", source)
		self.assertIn("has_draft_return", source)
		ui = (PUBLIC_JS / "professional_selling" / "ProfessionalSelling.vue").read_text(encoding="utf-8")
		self.assertIn('action === "open-existing-document"', ui)
		self.assertIn("openExistingLinkedDocument", ui)

	def test_completion_draft_save_action_is_in_footer_only(self):
		ui = (PUBLIC_JS / "professional_selling" / "StandardSellingCompletionDialog.vue").read_text(encoding="utf-8")
		self.assertEqual(ui.count("Save Draft Changes"), 1)
		footer = ui.split("<template #footer>", 1)[1]
		self.assertIn("Save Draft Changes", footer)

	def test_print_share_navigation_has_direct_route_fallback(self):
		source = (PUBLIC_JS / "documentOutputNavigation.js").read_text(encoding="utf-8")
		self.assertIn("window.retailedgeDocumentOutputTarget", source)
		self.assertIn('mode: "share"', source)
		self.assertIn('frappe.set_route("document-output-sharing")', source)
		self.assertIn('typeof shared === "function"', source)

	def test_payment_mode_dialog_no_longer_calls_missing_dialog_refresh_field(self):
		ui = (PUBLIC_JS / "payment_management" / "PaymentManagement.vue").read_text(encoding="utf-8")
		self.assertNotIn("dialog.refresh_field(", ui)
		self.assertIn('dialog.get_field?.("reference_no")?.refresh?.()', ui)
		self.assertIn('dialog.get_field?.("reference_date")?.refresh?.()', ui)

	def test_growing_purchasing_histories_are_persistent_pages(self):
		for page_name in ("purchase_receipt_history", "rfq_history", "supplier_quotation_history"):
			page_dir = APP_ROOT / "retailedge" / "page" / page_name
			self.assertTrue((page_dir / f"{page_name}.json").exists())
			self.assertTrue((page_dir / f"{page_name}.js").exists())
		purchasing_ui = (PUBLIC_JS / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text(encoding="utf-8")
		self.assertIn('frappe.set_route("purchase-receipt-history")', purchasing_ui)
		self.assertIn('frappe.set_route("rfq-history")', purchasing_ui)
		self.assertIn('frappe.set_route("supplier-quotation-history")', purchasing_ui)


if __name__ == "__main__":
	unittest.main()
