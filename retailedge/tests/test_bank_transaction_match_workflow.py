from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.bank_transaction_match_workflow import (
	_revalidate_suggestion_row,
	bulk_confirm_bank_transaction_matches,
	bulk_mark_bank_transaction_matches_needs_review,
	cancel_bank_transaction_match,
	confirm_bank_transaction_match,
	create_bank_match_reviews_from_suggestions,
	create_or_get_bank_transaction_match,
	get_bank_match_review_queue_summary,
	preview_bulk_confirm_bank_transaction_matches,
	run_bank_transaction_auto_match,
)
from retailedge.bank_transaction_matching import get_bank_transaction_matching_rows
from retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match import (
	RetailEdgeBankTransactionMatch,
)
from retailedge.retailedge.doctype.retailedge_settings.retailedge_settings import RetailEdgeSettings


class _FakeMatchDoc(SimpleNamespace):
	def get(self, key, default=None):
		return getattr(self, key, default)

	def append(self, fieldname, value):
		current = getattr(self, fieldname, None)
		if current is None:
			current = []
			setattr(self, fieldname, current)
		current.append(value)

	def insert(self, ignore_permissions=True):
		self.name = getattr(self, "name", None) or "RE-BTM-2026-0001"
		self.insert_called = True
		return self

	def save(self, ignore_permissions=True):
		self.save_called = True
		return self

	def has_permission(self, perm):
		return True


class BankTransactionMatchWorkflowTests(unittest.TestCase):
	def _bind_match_validate(self, doc, validate_candidate=False):
		if validate_candidate:
			doc._validate_candidate_fields = RetailEdgeBankTransactionMatch._validate_candidate_fields.__get__(doc, object)
		else:
			doc._validate_candidate_fields = (lambda: None)
		doc._validate_party_fields = RetailEdgeBankTransactionMatch._validate_party_fields.__get__(doc, object)
		doc._sync_sales_invoice_party_fields = RetailEdgeBankTransactionMatch._sync_sales_invoice_party_fields.__get__(doc, object)
		doc._set_amount_difference = RetailEdgeBankTransactionMatch._set_amount_difference.__get__(doc, object)
		doc._set_review_classification = RetailEdgeBankTransactionMatch._set_review_classification.__get__(doc, object)
		doc._set_readable_summaries = RetailEdgeBankTransactionMatch._set_readable_summaries.__get__(doc, object)
		doc._build_amount_breakdown_summary = RetailEdgeBankTransactionMatch._build_amount_breakdown_summary.__get__(doc, object)
		doc._refresh_sync_readiness = RetailEdgeBankTransactionMatch._refresh_sync_readiness.__get__(doc, object)
		return doc

	def test_party_type_defaults_to_customer(self):
		doc = self._bind_match_validate(
			SimpleNamespace(
				party_type=None,
				party=None,
				sales_invoice=None,
				bank_amount=100,
				candidate_amount=100,
				decision_status="Suggested",
				synced_to_sales_invoice=0,
				sales_invoice_sync_ready=0,
				sync_blocked_reason=None,
			)
		)

		RetailEdgeBankTransactionMatch.validate(doc)
		self.assertEqual(doc.party_type, "Customer")
		self.assertIn("Bank amount", doc.match_summary)
		self.assertIn("Candidate amount", doc.match_summary)
		self.assertEqual(doc.review_status, "Pending Review")
		self.assertEqual(doc.risk_level, "High")
		self.assertEqual(doc.decision_summary, "Suggested - awaiting review.")

	def test_settings_compute_bank_auto_match_mode_and_guidance(self):
		doc = SimpleNamespace(
			enable_bank_auto_match=1,
			auto_prepare_exact_bank_matches=1,
			auto_confirm_exact_bank_matches=0,
			bank_auto_match_mode=None,
			bank_auto_match_guidance=None,
		)
		RetailEdgeSettings._set_bank_auto_match_guidance(doc)
		self.assertEqual(doc.bank_auto_match_mode, "Auto-Prepare Only")
		self.assertIn("does not reconcile Bank Transactions", doc.bank_auto_match_guidance)
		self.assertIn("create Payment Entries", doc.bank_auto_match_guidance)

	@patch("retailedge.retailedge.doctype.retailedge_settings.retailedge_settings.clear_retailedge_settings_cache")
	def test_settings_on_update_clears_cached_auto_match_snapshot(self, mock_clear_cache):
		doc = SimpleNamespace()
		RetailEdgeSettings.on_update(doc)
		mock_clear_cache.assert_called_once_with()

	def test_match_doctype_hides_details_json_and_defines_summaries(self):
		import json
		from pathlib import Path

		path = Path(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_bank_transaction_match/retailedge_bank_transaction_match.json"
		)
		data = json.loads(path.read_text())
		fields = {row.get("fieldname"): row for row in data.get("fields", [])}
		self.assertEqual(fields["details_json"].get("hidden"), 1)
		self.assertEqual(fields["details_json"].get("read_only"), 1)
		self.assertEqual(fields["details_json"].get("no_copy"), 1)
		self.assertIn("match_summary", fields)
		self.assertIn("amount_scenario", fields)
		self.assertIn("amount_breakdown_summary", fields)
		self.assertIn("match_reason_summary", fields)
		self.assertIn("decision_summary", fields)

	def test_form_js_groups_review_buttons(self):
		from pathlib import Path

		path = Path(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_bank_transaction_match/retailedge_bank_transaction_match.js"
		)
		source = path.read_text()
		self.assertIn('__("Review Actions")', source)
		self.assertIn('__("More Actions")', source)
		self.assertIn("set_inner_btn_group_as_primary", source)

	def test_list_js_exposes_bulk_review_actions(self):
		from pathlib import Path

		path = Path(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_bank_transaction_match/retailedge_bank_transaction_match_list.js"
		)
		source = path.read_text()
		self.assertIn("Preview Bulk Confirm", source)
		self.assertIn("Bulk Confirm Selected", source)
		self.assertIn("Bulk Mark Needs Review", source)
		self.assertIn("get_indicator", source)
		self.assertIn("Review Queue Summary", source)
		self.assertIn("review_status,=,", source)

	def test_invalid_party_type_is_rejected(self):
		doc = self._bind_match_validate(
			SimpleNamespace(
				party_type="User",
				party=None,
				sales_invoice=None,
				bank_amount=100,
				candidate_amount=100,
				decision_status="Suggested",
				synced_to_sales_invoice=0,
				sales_invoice_sync_ready=0,
				sync_blocked_reason=None,
			)
		)
		with self.assertRaises(frappe.ValidationError):
			RetailEdgeBankTransactionMatch.validate(doc)

	def test_manual_save_blocks_match_without_candidate_document(self):
		doc = self._bind_match_validate(
			SimpleNamespace(
				bank_transaction="ACC-BTN-0001",
				suggested_document_type=None,
				suggested_document=None,
				party_type="Customer",
				party=None,
				sales_invoice=None,
				bank_amount=100,
				candidate_amount=100,
				decision_status="Suggested",
				synced_to_sales_invoice=0,
				sales_invoice_sync_ready=0,
				sync_blocked_reason=None,
			),
			validate_candidate=True,
		)
		with self.assertRaises(frappe.ValidationError):
			RetailEdgeBankTransactionMatch.validate(doc)

	@patch("retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.frappe.db.exists", return_value=True)
	def test_supplier_party_type_is_allowed(self, _mock_exists):
		doc = self._bind_match_validate(
			SimpleNamespace(
				party_type="Supplier",
				party="SUP-0001",
				sales_invoice=None,
				bank_amount=100,
				candidate_amount=100,
				decision_status="Suggested",
				synced_to_sales_invoice=0,
				sales_invoice_sync_ready=0,
				sync_blocked_reason=None,
			)
		)
		RetailEdgeBankTransactionMatch.validate(doc)
		self.assertEqual(doc.party_type, "Supplier")
		self.assertEqual(doc.party, "SUP-0001")

	@patch("retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.frappe.db.get_value", return_value="CUST-0001")
	def test_sales_invoice_forces_customer_party(self, _mock_customer):
		doc = self._bind_match_validate(
			SimpleNamespace(
				party_type="Supplier",
				party="SUP-0001",
				sales_invoice="SINV-0001",
				customer=None,
				bank_amount=100,
				candidate_amount=90,
				decision_status="Confirmed",
				synced_to_sales_invoice=0,
				sales_invoice_sync_ready=0,
				sync_blocked_reason=None,
			)
		)
		RetailEdgeBankTransactionMatch.validate(doc)
		self.assertEqual(doc.party_type, "Customer")
		self.assertEqual(doc.party, "CUST-0001")
		self.assertEqual(doc.customer, "CUST-0001")

	def test_strong_exact_match_sets_ready_to_confirm_low_risk(self):
		doc = self._bind_match_validate(
			SimpleNamespace(
				party_type="Customer",
				party=None,
				sales_invoice=None,
				suggested_document_type="Sales Invoice",
				bank_amount=100,
				candidate_amount=100,
				amount_difference=0,
				match_confidence="Strong Match",
				match_score=92,
				match_reason="Exact amount and reference match.",
				decision_status="Suggested",
				synced_to_sales_invoice=0,
				sales_invoice_sync_ready=0,
				sync_blocked_reason=None,
			)
		)
		RetailEdgeBankTransactionMatch.validate(doc)
		self.assertEqual(doc.review_status, "Ready to Confirm")
		self.assertEqual(doc.match_status, "Strong Match")
		self.assertEqual(doc.risk_level, "Low")
		self.assertEqual(doc.candidate_type, "Sales Invoice")

	@patch("retailedge.bank_transaction_match_workflow._select_candidate_for_queue")
	@patch("retailedge.bank_transaction_match_workflow.find_payment_entry_candidates_for_bank_transaction")
	@patch("retailedge.bank_transaction_match_workflow.find_sales_invoice_candidates_for_bank_transaction")
	@patch("retailedge.bank_transaction_match_workflow.normalize_bank_transaction")
	def test_revalidate_suggestion_row_uses_current_backend_candidate(
		self,
		mock_normalize,
		mock_sales_candidates,
		mock_payment_candidates,
		mock_select,
	):
		mock_normalize.return_value = {
			"bank_transaction": "BTN-1",
			"transaction_date": "2026-05-20",
			"bank_account": "Moniepoint - moniepoint",
			"amount": 810.0,
			"direction": "Inflow",
			"description": "Moniepoint inflow",
		}
		mock_sales_candidates.return_value = []
		mock_payment_candidates.return_value = []
		mock_select.return_value = ({
			"document_type": "Sales Invoice",
			"document_name": "ACC-SINV-2026-00025",
			"suggested_sales_invoice": "ACC-SINV-2026-00025",
			"candidate_amount": 810.0,
			"amount_difference": 0.0,
			"confidence": "Possible Match",
			"score": 70,
			"candidate_category": "invoice_payment_row_match",
			"candidate_category_label": "Invoice Payment Row Match",
			"payment_event_found": 1,
			"payment_event_source": "Invoice Payment Row",
			"payment_row_index": 1,
			"payment_row_amount": 810.0,
			"payment_mode": "Moniepoint",
			"payment_account": "Demo Bank Account - PED",
			"payment_category": "Bank Transfer",
			"amount_scenario": "Exact Invoice Payment Row Amount",
			"amount_scenario_label": "Exact Invoice Payment Row Amount",
			"customer": "Palmer Productions Ltd.",
			"party": "Palmer Productions Ltd.",
			"party_type": "Customer",
			"reasons": ["Matched invoice payment row."],
		}, None)
		row = _revalidate_suggestion_row(
			{
				"bank_transaction": "BTN-1",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "ACC-PAY-OLD",
			}
		)
		self.assertEqual(row["suggested_document_type"], "Sales Invoice")
		self.assertEqual(row["suggested_document"], "ACC-SINV-2026-00025")
		self.assertEqual(row["candidate_revalidated"], 1)

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow._revalidate_suggestion_row")
	@patch("retailedge.bank_transaction_match_workflow._auto_prepare_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.create_or_get_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_auto_match_selected_rows_uses_selected_subset(
		self,
		mock_settings,
		mock_create_or_get,
		mock_auto_prepare,
		mock_revalidate,
		_mock_confirmed_payment,
		_mock_roles,
		_mock_access,
	):
		mock_settings.return_value = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 0,
			"minimum_auto_match_score": 95,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		mock_create_or_get.return_value = {"name": "RE-BTM-2026-0001", "created": True}
		rows = [
			{
				"bank_transaction": "BTN-1",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "PE-1",
				"candidate_category": "Payment Entry Match",
				"match_confidence": "Strong Match",
				"match_score": 99,
				"amount_scenario": "Submitted Payment Entry Amount",
				"amount_difference": 0,
				"reference_match_exact": 1,
				"account_match_available": 1,
				"account_match": 1,
			},
			{
				"bank_transaction": "BTN-2",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "PE-2",
				"candidate_category": "Payment Entry Match",
				"match_confidence": "Strong Match",
				"match_score": 99,
				"amount_scenario": "Submitted Payment Entry Amount",
				"amount_difference": 0,
				"reference_match_exact": 1,
				"account_match_available": 1,
				"account_match": 1,
			},
		]

		mock_revalidate.side_effect = lambda row, filters=None: {
			**row,
			"suggested_document_type": "Payment Entry" if row.get("bank_transaction") == "BTN-2" else row.get("suggested_document_type"),
			"suggested_document": "PE-CURRENT" if row.get("bank_transaction") == "BTN-2" else row.get("suggested_document"),
			"suggested_sales_invoice": "" if row.get("bank_transaction") == "BTN-2" else row.get("suggested_document"),
			"candidate_category": "Payment Entry Match" if row.get("bank_transaction") == "BTN-2" else row.get("candidate_category"),
			"payment_event_found": 1,
			"payment_event_source": "Payment Entry" if row.get("bank_transaction") == "BTN-2" else row.get("payment_event_source"),
		}
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = run_bank_transaction_auto_match(
				rows=rows,
				selected_keys=['BTN-2|Payment Entry|PE-2'],
			)

		self.assertEqual(result["checked_count"], 1)
		self.assertEqual(result["auto_prepared_count"], 1)
		mock_create_or_get.assert_called_once()
		self.assertEqual(mock_create_or_get.call_args.kwargs["bank_transaction_name"], "BTN-2")
		self.assertEqual(mock_create_or_get.call_args.kwargs["suggested_document_type"], "Payment Entry")
		self.assertEqual(mock_create_or_get.call_args.kwargs["suggested_document"], "PE-CURRENT")
		mock_auto_prepare.assert_called_once()

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow._auto_confirm_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.create_or_get_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_auto_match_can_auto_confirm_only_when_enabled(
		self,
		mock_settings,
		mock_create_or_get,
		mock_auto_confirm,
		_mock_confirmed_payment,
		_mock_roles,
		_mock_access,
	):
		mock_settings.return_value = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 95,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		mock_create_or_get.return_value = {"name": "RE-BTM-2026-0002", "created": True}
		mock_auto_confirm.return_value = {"message": "auto confirmed"}
		rows = [
			{
				"bank_transaction": "BTN-1",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "PE-1",
				"candidate_category": "Payment Entry Match",
				"match_confidence": "Strong Match",
				"match_score": 99,
				"amount_scenario": "Submitted Payment Entry Amount",
				"amount_difference": 0,
				"reference_match_exact": 1,
				"account_match_available": 1,
				"account_match": 1,
				"payment_entry_invoice_context": "SINV-1",
			}
		]
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = run_bank_transaction_auto_match(rows=rows)
		self.assertEqual(result["auto_confirmed_count"], 1)
		mock_auto_confirm.assert_called_once()
		self.assertIn("RetailEdge review records auto-confirmed", result["message"])

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.create_or_get_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_auto_match_revalidates_backend_settings_and_blocks_disabled_auto_match(
		self,
		mock_settings,
		mock_create_or_get,
		_mock_confirmed_payment,
		_mock_roles,
		_mock_access,
	):
		mock_settings.return_value = {
			"enable_bank_auto_match": 0,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 65,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		rows = [{
			"bank_transaction": "BTN-1",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "PE-1",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 99,
			"amount_scenario": "Submitted Payment Entry Amount",
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 1,
			"account_match": 1,
			"auto_match_status": "Eligible for Auto-Confirm",
		}]
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = run_bank_transaction_auto_match(rows=rows)
		self.assertEqual(result["auto_prepared_count"], 0)
		self.assertEqual(result["auto_confirmed_count"], 0)
		self.assertEqual(result["manual_review_count"], 1)
		self.assertIn("disabled in Settings", result["manual_review"][0]["reason"])
		mock_create_or_get.assert_not_called()

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow._auto_prepare_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.create_or_get_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_next_auto_match_run_uses_latest_saved_settings(
		self,
		mock_settings,
		mock_create_or_get,
		mock_auto_prepare,
		_mock_confirmed_payment,
		_mock_roles,
		_mock_access,
	):
		mock_settings.side_effect = [
			{
				"enable_bank_auto_match": 1,
				"auto_prepare_exact_bank_matches": 1,
				"auto_confirm_exact_bank_matches": 0,
				"minimum_auto_match_score": 95,
				"require_exact_reference_for_auto_match": 1,
				"require_same_bank_account_for_auto_match": 1,
				"require_same_branch_for_auto_match": 0,
				"allow_auto_match_payment_entry": 1,
				"allow_auto_match_sales_invoice": 0,
				"require_no_duplicate_candidate_for_auto_match": 1,
				"require_no_active_review_for_auto_match": 1,
			},
			{
				"enable_bank_auto_match": 1,
				"auto_prepare_exact_bank_matches": 1,
				"auto_confirm_exact_bank_matches": 0,
				"minimum_auto_match_score": 80,
				"require_exact_reference_for_auto_match": 1,
				"require_same_bank_account_for_auto_match": 1,
				"require_same_branch_for_auto_match": 0,
				"allow_auto_match_payment_entry": 1,
				"allow_auto_match_sales_invoice": 0,
				"require_no_duplicate_candidate_for_auto_match": 1,
				"require_no_active_review_for_auto_match": 1,
			},
		]
		mock_create_or_get.return_value = {"name": "RE-BTM-2026-0003", "created": True}
		rows = [{
			"bank_transaction": "BTN-1",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "PE-1",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 90,
			"amount_scenario": "Submitted Payment Entry Amount",
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 1,
			"account_match": 1,
		}]
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			first_result = run_bank_transaction_auto_match(rows=rows)
			second_result = run_bank_transaction_auto_match(rows=rows)
		self.assertEqual(first_result["auto_prepared_count"], 0)
		self.assertEqual(first_result["manual_review_count"], 1)
		self.assertEqual(second_result["auto_prepared_count"], 1)
		mock_create_or_get.assert_called_once()
		mock_auto_prepare.assert_called_once()

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_partial_payment_is_blocked_from_workflow_auto_match(self, mock_settings, _mock_confirmed_invoice, _mock_roles, _mock_access):
		mock_settings.return_value = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 0,
			"minimum_auto_match_score": 95,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		rows = [
			{
				"bank_transaction": "BTN-1",
				"suggested_document_type": "Sales Invoice",
				"suggested_document": "SINV-1",
				"suggested_sales_invoice": "SINV-1",
				"candidate_category": "Invoice Payment Row Match",
				"payment_event_found": 1,
				"payment_event_source": "Invoice Payment Row",
				"match_confidence": "Possible Match",
				"match_score": 80,
				"amount_scenario": "Partial Payment",
				"amount_difference": 100,
			}
		]
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = run_bank_transaction_auto_match(rows=rows)
		self.assertEqual(result["auto_prepared_count"], 0)
		self.assertEqual(result["manual_review_count"], 1)
		self.assertIn("Partial Payment", result["manual_review"][0]["reason"])

	def test_auto_confirm_success_message_is_review_layer_only(self):
		message = "Exact high-confidence RetailEdge Bank Match Review record auto-confirmed by RetailEdge settings only. No reconciliation or accounting posting was performed."
		self.assertIn("RetailEdge Bank Match Review record auto-confirmed", message)
		self.assertIn("No reconciliation or accounting posting was performed", message)

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_rows")
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_auto_match_uses_visible_rows_when_rows_not_supplied(
		self,
		mock_settings,
		mock_get_rows,
		_mock_confirmed_payment,
		_mock_roles,
		_mock_access,
	):
		mock_settings.return_value = {
			"enable_bank_auto_match": 0,
			"auto_prepare_exact_bank_matches": 0,
			"auto_confirm_exact_bank_matches": 0,
			"minimum_auto_match_score": 95,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		mock_get_rows.return_value = [
			{
				"bank_transaction": "BTN-1",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "PE-1",
				"candidate_category": "Payment Entry Match",
				"match_confidence": "Strong Match",
				"match_score": 99,
				"amount_scenario": "Submitted Payment Entry Amount",
				"amount_difference": 0,
			}
		]
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = run_bank_transaction_auto_match(filters={"company": "Process Edge (Demo)"})
		mock_get_rows.assert_called_once()
		self.assertEqual(result["checked_count"], 1)
		self.assertEqual(result["manual_review_count"], 1)

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch(
		"retailedge.bank_transaction_match_workflow.find_payment_entry_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Payment Entry",
				"document_name": "PE-0001",
				"suggested_document": "PE-0001",
				"suggested_sales_invoice": "SINV-0001",
				"customer": "CUST-0001",
				"customer_display": "ABC Stores",
				"party": "CUST-0001",
				"party_type": "Customer",
				"candidate_amount": 10000,
				"score": 95,
				"confidence": "Strong Match",
				"candidate_category": "payment_entry_match",
				"payment_event_found": 1,
				"payment_event_source": "Payment Entry",
				"reasons": ["Matched submitted Payment Entry."],
			}
		],
	)
	@patch(
		"retailedge.bank_transaction_match_workflow.find_sales_invoice_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Sales Invoice",
				"document_name": "SINV-0001",
				"suggested_sales_invoice": "SINV-0001",
				"customer": "CUST-0001",
				"customer_display": "ABC Stores",
				"party": "CUST-0001",
				"party_type": "Customer",
				"candidate_amount": 10000,
				"score": 90,
				"confidence": "Strong Match",
				"candidate_category": "invoice_context_only",
				"payment_event_found": 0,
				"reasons": ["Amount and reference match."],
			}
		],
	)
	@patch(
		"retailedge.bank_transaction_match_workflow.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"branch": "Airport Branch",
			"bank_account": "Moniepoint - moniepoint",
			"transaction_date": "2026-05-24",
			"amount": 10000,
			"reference": "TRF123",
			"description": "ABC Stores transfer",
		},
	)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None)
	@patch("retailedge.bank_transaction_match_workflow.frappe.session", SimpleNamespace(user="auditor@example.com"))
	def test_create_or_get_match_creates_retailedge_record(
		self,
		_mock_existing,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		_mock_roles,
		_mock_access,
	):
		fake_doc = _FakeMatchDoc(
			doctype="RetailEdge Bank Transaction Match",
			decision_status=None,
			action_logs=[],
			synced_to_sales_invoice=0,
		)
		def fake_get_doc(payload, *args, **kwargs):
			if isinstance(payload, dict) and payload.get("doctype") == "RetailEdge Bank Transaction Match":
				return fake_doc
			raise AssertionError(f"Unexpected get_doc payload: {payload}")

		with patch("retailedge.bank_transaction_match_workflow.frappe.get_doc", side_effect=fake_get_doc), patch(
			"retailedge.bank_transaction_match_workflow.now_datetime", return_value="2026-05-24 10:00:00"
		):
			result = create_or_get_bank_transaction_match("ACC-BTN-0001")

		self.assertTrue(result["created"])
		self.assertEqual(fake_doc.bank_transaction, "ACC-BTN-0001")
		self.assertEqual(fake_doc.payment_entry, "PE-0001")
		self.assertEqual(fake_doc.suggested_document_type, "Payment Entry")
		self.assertEqual(fake_doc.party, "CUST-0001")
		self.assertEqual(fake_doc.party_type, "Customer")
		self.assertEqual(fake_doc.decision_status, "Suggested")
		self.assertTrue(fake_doc.insert_called)
		self.assertTrue(fake_doc.save_called)
		self.assertEqual(fake_doc.action_logs[0]["action"], "Created")

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None)
	def test_confirm_candidate_updates_decision_status(self, mock_get_value, mock_get_doc, _mock_roles):
		doc = _FakeMatchDoc(
			doctype="RetailEdge Bank Transaction Match",
			name="RE-BTM-2026-0001",
			decision_status="Suggested",
			bank_transaction="ACC-BTN-0001",
			suggested_document="SINV-0001",
			suggested_document_type="Sales Invoice",
			sales_invoice=None,
			payment_entry=None,
			action_logs=[],
			synced_to_sales_invoice=0,
		)
		mock_get_doc.return_value = doc

		with patch("retailedge.bank_transaction_match_workflow.now_datetime", return_value="2026-05-24 10:00:00"):
			result = confirm_bank_transaction_match("RE-BTM-2026-0001", decision_note="Looks correct")

		self.assertEqual(result["decision_status"], "Confirmed")
		self.assertEqual(doc.decision_status, "Confirmed")
		self.assertEqual(doc.confirmed_by, "auditor@example.com")
		self.assertEqual(doc.action_logs[-1]["action"], "Confirmed")
		self.assertTrue(doc.save_called)

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	def test_confirmed_match_can_be_cancelled_to_release_candidate(self, mock_get_doc, _mock_roles):
		doc = _FakeMatchDoc(
			doctype="RetailEdge Bank Transaction Match",
			name="RE-BTM-2026-0001",
			decision_status="Confirmed",
			bank_transaction="ACC-BTN-0001",
			suggested_document="SINV-0001",
			suggested_document_type="Sales Invoice",
			sales_invoice="SINV-0001",
			payment_entry=None,
			action_logs=[],
			synced_to_sales_invoice=0,
		)
		mock_get_doc.return_value = doc

		with patch("retailedge.bank_transaction_match_workflow.now_datetime", return_value="2026-05-24 10:00:00"):
			result = cancel_bank_transaction_match("RE-BTM-2026-0001", decision_note="Wrong candidate")

		self.assertEqual(result["decision_status"], "Cancelled")
		self.assertEqual(doc.decision_status, "Cancelled")
		self.assertEqual(doc.action_logs[-1]["action"], "Cancelled")
		self.assertTrue(doc.save_called)

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value")
	def test_confirming_second_match_for_confirmed_sales_invoice_is_blocked(
		self,
		mock_get_value,
		mock_get_doc,
		_mock_roles,
	):
		doc = _FakeMatchDoc(
			doctype="RetailEdge Bank Transaction Match",
			name="RE-BTM-2026-0002",
			decision_status="Suggested",
			bank_transaction="ACC-BTN-0002",
			suggested_document="SINV-0001",
			suggested_document_type="Sales Invoice",
			sales_invoice="SINV-0001",
			payment_entry=None,
			action_logs=[],
			synced_to_sales_invoice=0,
		)
		mock_get_doc.return_value = doc
		mock_get_value.side_effect = ["RE-BTM-2026-0001", None]
		with self.assertRaises(frappe.ValidationError):
			confirm_bank_transaction_match("RE-BTM-2026-0002", decision_note="Conflict")

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value")
	def test_confirming_second_match_for_confirmed_payment_entry_is_blocked(
		self,
		mock_get_value,
		mock_get_doc,
		_mock_roles,
	):
		doc = _FakeMatchDoc(
			doctype="RetailEdge Bank Transaction Match",
			name="RE-BTM-2026-0002",
			decision_status="Suggested",
			bank_transaction="ACC-BTN-0002",
			suggested_document="PE-0001",
			suggested_document_type="Payment Entry",
			sales_invoice=None,
			payment_entry="PE-0001",
			action_logs=[],
			synced_to_sales_invoice=0,
		)
		mock_get_doc.return_value = doc
		mock_get_value.side_effect = ["RE-BTM-2026-0001"]
		with self.assertRaises(frappe.ValidationError):
			confirm_bank_transaction_match("RE-BTM-2026-0002", decision_note="Conflict")

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None)
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	def test_preview_bulk_confirm_returns_eligible_and_blocked_records(
		self,
		mock_get_doc,
		_mock_get_value,
		mock_exists,
		_mock_roles,
	):
		eligible = _FakeMatchDoc(
			name="RE-BTM-ELIGIBLE",
			decision_status="Suggested",
			match_confidence="Strong Match",
			match_score=90,
			bank_transaction="BT-0001",
			suggested_document_type="Sales Invoice",
			suggested_document="SINV-0001",
			sales_invoice="SINV-0001",
			payment_entry=None,
			candidate_amount=10000,
			amount_difference=0,
			amount_scenario="Exact Outstanding Match",
			synced_to_sales_invoice=0,
		)
		blocked = _FakeMatchDoc(
			name="RE-BTM-BLOCKED",
			decision_status="Suggested",
			match_confidence="Weak Match",
			match_score=40,
			bank_transaction="BT-0002",
			suggested_document_type="Sales Invoice",
			suggested_document="SINV-0002",
			sales_invoice="SINV-0002",
			payment_entry=None,
			candidate_amount=10000,
			amount_difference=0,
			amount_scenario="Weak Match",
			synced_to_sales_invoice=0,
		)
		docs = {eligible.name: eligible, blocked.name: blocked}
		mock_get_doc.side_effect = lambda _doctype, name: docs[name]
		mock_exists.return_value = True
		result = preview_bulk_confirm_bank_transaction_matches([eligible.name, blocked.name])
		self.assertEqual(result["eligible_count"], 1)
		self.assertEqual(result["blocked_count"], 1)
		self.assertEqual(result["weak_needs_review_count"], 1)
		self.assertEqual(result["eligible"][0]["name"], eligible.name)
		self.assertTrue(result["reasons"])

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None)
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	def test_bulk_confirm_blocks_manual_review_amount_scenarios(
		self,
		mock_get_doc,
		_mock_get_value,
		_mock_exists,
		_mock_roles,
	):
		partial = _FakeMatchDoc(
			name="RE-BTM-PARTIAL",
			decision_status="Suggested",
			match_confidence="Possible Match",
			match_score=79,
			bank_transaction="BT-0001",
			suggested_document_type="Sales Invoice",
			suggested_document="SINV-0001",
			sales_invoice="SINV-0001",
			payment_entry=None,
			candidate_amount=50000,
			amount_difference=-30000,
			amount_scenario="Partial Payment",
			match_reason="Partial Payment requires manual review.",
			synced_to_sales_invoice=0,
		)
		mock_get_doc.return_value = partial
		result = preview_bulk_confirm_bank_transaction_matches([partial.name])
		self.assertEqual(result["eligible_count"], 0)
		self.assertEqual(result["blocked_count"], 1)
		self.assertIn("Partial Payment", result["blocked"][0]["reason"])

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None)
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	def test_bulk_confirm_blocks_invoice_context_only_candidates(
		self,
		mock_get_doc,
		_mock_get_value,
		_mock_exists,
		_mock_roles,
	):
		context_only = _FakeMatchDoc(
			name="RE-BTM-CONTEXT",
			decision_status="Suggested",
			match_confidence="Possible Match",
			match_score=55,
			bank_transaction="BT-0003",
			suggested_document_type="Sales Invoice",
			suggested_document="SINV-0009",
			sales_invoice="SINV-0009",
			payment_entry=None,
			candidate_category="Invoice Context Only",
			candidate_amount=1000,
			amount_difference=0,
			amount_scenario="Exact Outstanding Amount",
			match_reason="Sales Invoice is context only; payment event evidence is required for auto-match.",
			synced_to_sales_invoice=0,
		)
		mock_get_doc.return_value = context_only
		result = preview_bulk_confirm_bank_transaction_matches([context_only.name])
		self.assertEqual(result["eligible_count"], 0)
		self.assertEqual(result["blocked_count"], 1)
		self.assertIn("Invoice Context Only", result["blocked"][0]["reason"])

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	def test_bulk_confirm_blocks_records_with_missing_candidate_document(self, mock_get_doc, _mock_roles):
		missing = _FakeMatchDoc(
			name="RE-BTM-MISSING",
			decision_status="Suggested",
			match_confidence="Strong Match",
			match_score=90,
			bank_transaction="BT-0001",
			suggested_document_type="",
			suggested_document="",
			sales_invoice=None,
			payment_entry=None,
			synced_to_sales_invoice=0,
		)
		mock_get_doc.return_value = missing
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = preview_bulk_confirm_bank_transaction_matches([missing.name])
		self.assertEqual(result["eligible_count"], 0)
		self.assertEqual(result["blocked_count"], 1)
		self.assertEqual(result["blocked"][0]["reason"], "No match candidate found.")

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None)
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	def test_bulk_confirm_blocks_date_account_exception_matches(
		self,
		mock_get_doc,
		_mock_get_value,
		_mock_exists,
		_mock_roles,
	):
		exception = _FakeMatchDoc(
			name="RE-BTM-EXCEPTION",
			decision_status="Needs Review",
			match_confidence="Possible Match",
			match_score=60,
			bank_transaction="ACC-BTN-2026-00002",
			suggested_document_type="Payment Entry",
			suggested_document="ACC-PAY-2026-00009",
			sales_invoice="ACC-SINV-2026-00027",
			payment_entry="ACC-PAY-2026-00009",
			candidate_amount=900,
			amount_difference=0,
			amount_scenario="Date + Account Mismatch",
			match_reason="Date/account exception candidates are for investigation only.",
			synced_to_sales_invoice=0,
		)
		mock_get_doc.return_value = exception
		result = preview_bulk_confirm_bank_transaction_matches([exception.name])
		self.assertEqual(result["eligible_count"], 0)
		self.assertEqual(result["blocked_count"], 1)
		self.assertIn("Date + Account Mismatch", result["blocked"][0]["reason"])

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None)
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	def test_confirm_blocks_date_account_exception_matches(
		self,
		mock_get_doc,
		_mock_get_value,
		_mock_roles,
	):
		exception = _FakeMatchDoc(
			name="RE-BTM-EXCEPTION",
			decision_status="Needs Review",
			bank_transaction="ACC-BTN-2026-00002",
			suggested_document_type="Payment Entry",
			suggested_document="ACC-PAY-2026-00009",
			sales_invoice="ACC-SINV-2026-00027",
			payment_entry="ACC-PAY-2026-00009",
			amount_scenario="Date + Account Mismatch",
			action_logs=[],
		)
		mock_get_doc.return_value = exception
		with self.assertRaises(frappe.ValidationError):
			confirm_bank_transaction_match(exception.name, decision_note="Force confirm")

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_auto_match_skips_invoice_total_similarity_candidates(self, mock_settings, _mock_confirmed_invoice, _mock_roles, _mock_access):
		mock_settings.return_value = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 40,
			"require_exact_reference_for_auto_match": 0,
			"require_same_bank_account_for_auto_match": 0,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		rows = [
			{
				"bank_transaction": "BTN-5",
				"suggested_document_type": "Sales Invoice",
				"suggested_document": "SINV-55",
				"suggested_sales_invoice": "SINV-55",
				"candidate_category": "Weak Invoice Total Similarity",
				"match_confidence": "Weak Match",
				"match_score": 45,
				"amount_scenario": "Exact Invoice Amount",
				"amount_difference": 0,
			}
		]
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = run_bank_transaction_auto_match(rows=rows)
		self.assertEqual(result["auto_prepared_count"], 0)
		self.assertEqual(result["auto_confirmed_count"], 0)
		self.assertEqual(result["manual_review_count"], 1)
		self.assertIn("payment entry or invoice payment row evidence", result["manual_review"][0]["reason"].lower())

	@patch("retailedge.bank_transaction_match_workflow._revalidate_suggestion_row", side_effect=lambda row, filters=None: row)
	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_auto_match_skips_rows_with_active_review_record(
		self,
		mock_settings,
		_mock_exists,
		mock_get_value,
		_mock_payment_confirmed,
		_mock_invoice_confirmed,
		_mock_roles,
		_mock_access,
		_mock_revalidate,
	):
		mock_settings.return_value = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 40,
			"require_exact_reference_for_auto_match": 0,
			"require_same_bank_account_for_auto_match": 0,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		mock_get_value.side_effect = [None, "RE-BTM-ACTIVE", "Needs Review"]
		result = run_bank_transaction_auto_match(
			rows=[
				{
					"bank_transaction": "BTN-ACTIVE",
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-ACTIVE",
					"candidate_category": "Payment Entry Match",
					"payment_event_found": 1,
					"payment_event_source": "Payment Entry",
					"match_confidence": "Strong Match",
					"match_score": 95,
				}
			]
		)
		self.assertEqual(result["auto_prepared_count"], 0)
		self.assertEqual(result["auto_confirmed_count"], 0)
		self.assertEqual(result["review_record_exists_count"], 1)
		self.assertEqual(result["review_record_exists"][0]["match_record"], "RE-BTM-ACTIVE")
		self.assertIn("Active review record already exists", result["review_record_exists"][0]["reason"])

	@patch("retailedge.bank_transaction_match_workflow._revalidate_suggestion_row", side_effect=lambda row, filters=None: row)
	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value="RE-BTM-REJECTED")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_auto_match_skips_previously_rejected_exact_pair(
		self,
		mock_settings,
		_mock_exists,
		_mock_get_value,
		_mock_payment_confirmed,
		_mock_invoice_confirmed,
		_mock_roles,
		_mock_access,
		_mock_revalidate,
	):
		mock_settings.return_value = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 40,
			"require_exact_reference_for_auto_match": 0,
			"require_same_bank_account_for_auto_match": 0,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		result = run_bank_transaction_auto_match(
			rows=[
				{
					"bank_transaction": "BT-REJECTED",
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-0001",
					"candidate_category": "Payment Entry Match",
					"payment_event_found": 1,
					"payment_event_source": "Payment Entry",
					"match_confidence": "Strong Match",
					"match_score": 95,
				}
			]
		)
		self.assertEqual(result["auto_prepared_count"], 0)
		self.assertEqual(result["auto_confirmed_count"], 0)
		self.assertEqual(result["review_record_exists_count"], 1)
		self.assertEqual(result["review_record_exists"][0]["match_record"], "RE-BTM-REJECTED")
		self.assertEqual(result["review_record_exists"][0]["reason"], "Previously rejected match pair.")

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings")
	def test_auto_match_skips_rows_with_no_candidate(self, mock_settings, _mock_roles, _mock_access):
		mock_settings.return_value = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 40,
			"require_exact_reference_for_auto_match": 0,
			"require_same_bank_account_for_auto_match": 0,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = run_bank_transaction_auto_match(
				rows=[
					{
						"bank_transaction": "BTN-NONE",
						"suggested_document_type": "",
						"suggested_document": "",
						"action_status": "No Match",
					}
				]
			)
		self.assertEqual(result["auto_prepared_count"], 0)
		self.assertEqual(result["auto_confirmed_count"], 0)
		self.assertEqual(result["manual_review_count"], 1)
		self.assertEqual(result["blocked_count"], 1)
		self.assertEqual(result["reasons"][0]["reason"], "No match candidate found.")

	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.frappe.get_all")
	@patch("retailedge.bank_transaction_match_workflow.frappe.utils.nowdate", return_value="2026-05-24")
	def test_bank_match_review_queue_summary_counts_operational_buckets(self, _mock_today, mock_get_all, _mock_roles):
		mock_get_all.return_value = [
			{
				"name": "RE-BTM-1",
				"decision_status": "Suggested",
				"review_status": "Ready to Confirm",
				"match_confidence": "Strong Match",
				"risk_level": "Low",
				"transaction_date": "2026-05-24",
			},
			{
				"name": "RE-BTM-2",
				"decision_status": "Suggested",
				"review_status": "Needs Review",
				"match_confidence": "Weak Match",
				"risk_level": "High",
				"transaction_date": "2026-05-24",
			},
			{
				"name": "RE-BTM-3",
				"decision_status": "Confirmed",
				"review_status": "Confirmed",
				"match_confidence": "Strong Match",
				"risk_level": "Low",
				"transaction_date": "2026-05-24",
			},
			{
				"name": "RE-BTM-4",
				"decision_status": "Rejected",
				"review_status": "Rejected",
				"match_confidence": "Possible Match",
				"risk_level": "Blocked",
				"transaction_date": "2026-05-23",
			},
		]
		result = get_bank_match_review_queue_summary({"company": "Process Edge (Demo)"})
		self.assertEqual(result["total"], 4)
		self.assertEqual(result["ready_to_confirm"], 1)
		self.assertEqual(result["high_confidence"], 2)
		self.assertEqual(result["weak_needs_review"], 1)
		self.assertEqual(result["confirmed_today"], 1)
		self.assertEqual(result["confirmed"], 1)
		self.assertEqual(result["needs_review"], 1)
		self.assertEqual(result["rejected"], 1)
		self.assertEqual(result["rejected_cancelled"], 1)
		self.assertEqual(result["duplicate_blocked"], 1)

	@patch("retailedge.bank_transaction_match_workflow.confirm_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.preview_bulk_confirm_bank_transaction_matches")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_bulk_confirm_confirms_only_eligible_records(self, _mock_roles, mock_preview, mock_confirm):
		mock_preview.return_value = {
			"total_selected": 2,
			"eligible_count": 1,
			"blocked_count": 1,
			"eligible": [{"name": "RE-BTM-ELIGIBLE"}],
			"blocked": [{"name": "RE-BTM-BLOCKED", "reason": "Weak Match"}],
			"warnings": [],
		}
		mock_confirm.return_value = {"decision_status": "Confirmed", "message": "Confirmed"}
		result = bulk_confirm_bank_transaction_matches(["RE-BTM-ELIGIBLE", "RE-BTM-BLOCKED"], remarks="Batch")
		self.assertEqual(result["confirmed_count"], 1)
		self.assertEqual(result["skipped_count"], 1)
		mock_confirm.assert_called_once_with("RE-BTM-ELIGIBLE", decision_note="Batch")

	@patch("retailedge.bank_transaction_match_workflow.mark_bank_transaction_match_needs_review")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_bulk_mark_needs_review_updates_selected_records_only(self, _mock_roles, mock_mark):
		mock_mark.return_value = {"decision_status": "Needs Review"}
		result = bulk_mark_bank_transaction_matches_needs_review(["RE-BTM-1", "RE-BTM-2"], remarks="Review batch")
		self.assertEqual(result["updated_count"], 2)
		self.assertEqual(mock_mark.call_count, 2)

	@patch("retailedge.bank_transaction_match_workflow._revalidate_suggestion_row")
	@patch("retailedge.bank_transaction_match_workflow._prepare_created_match_review_record")
	@patch("retailedge.bank_transaction_match_workflow.create_or_get_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_create_review_records_from_selected_suggestions(
		self,
		_mock_roles,
		_mock_access,
		_mock_exists,
		_mock_get_value,
		_mock_invoice_confirmed,
		_mock_payment_confirmed,
		mock_create,
		mock_prepare,
		mock_revalidate,
	):
		mock_create.return_value = {
			"name": "RE-BTM-2026-0001",
			"created": True,
			"decision_status": "Suggested",
		}
		rows = [
			{
				"bank_transaction": "BT-0001",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "PE-0001",
				"suggested_sales_invoice": "SINV-0001",
				"candidate_category": "Payment Entry Match",
				"payment_event_found": 1,
				"payment_event_source": "Payment Entry",
				"match_confidence": "Strong Match",
				"match_score": 90,
			}
		]
		mock_revalidate.return_value = {
			"bank_transaction": "BT-0001",
			"suggested_document_type": "Sales Invoice",
			"suggested_document": "SINV-CURRENT",
			"suggested_sales_invoice": "SINV-CURRENT",
			"candidate_category": "Invoice Payment Row Match",
			"payment_event_found": 1,
			"payment_event_source": "Invoice Payment Row",
			"match_confidence": "Possible Match",
			"match_score": 70,
		}
		result = create_bank_match_reviews_from_suggestions(rows=rows)
		self.assertEqual(result["created_count"], 1)
		self.assertEqual(result["created"][0]["match_record"], "RE-BTM-2026-0001")
		mock_create.assert_called_once()
		self.assertEqual(mock_create.call_args.kwargs["suggested_document_type"], "Sales Invoice")
		self.assertEqual(mock_create.call_args.kwargs["suggested_document"], "SINV-CURRENT")
		mock_prepare.assert_called_once_with("RE-BTM-2026-0001", mock_revalidate.return_value)

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_create_review_records_skips_rows_with_no_candidate(self, _mock_roles, _mock_access):
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = create_bank_match_reviews_from_suggestions(
				rows=[
					{
						"bank_transaction": "BT-NONE",
						"suggested_document_type": "",
						"suggested_document": "",
						"action_status": "No Match",
					}
				]
			)
		self.assertEqual(result["created_count"], 0)
		self.assertEqual(result["unsafe_count"], 1)
		self.assertEqual(result["unsafe"][0]["reason"], "No match candidate found.")

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_create_review_records_skips_invoice_context_only_rows(self, _mock_roles, _mock_access):
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = create_bank_match_reviews_from_suggestions(
				rows=[
					{
						"bank_transaction": "BT-CONTEXT",
						"suggested_document_type": "Sales Invoice",
						"suggested_document": "SINV-CONTEXT",
						"suggested_sales_invoice": "SINV-CONTEXT",
						"candidate_category": "Invoice Context Only",
						"payment_event_found": 0,
						"payment_event_source": None,
					}
				]
			)
		self.assertEqual(result["created_count"], 0)
		self.assertEqual(result["unsafe_count"], 1)
		self.assertEqual(result["unsafe"][0]["reason"], "Invoice is context only. No payment event was found.")

	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_create_review_records_skips_weak_invoice_total_similarity_rows(self, _mock_roles, _mock_access):
		with patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True):
			result = create_bank_match_reviews_from_suggestions(
				rows=[
					{
						"bank_transaction": "BT-WEAK",
						"suggested_document_type": "Sales Invoice",
						"suggested_document": "SINV-WEAK",
						"suggested_sales_invoice": "SINV-WEAK",
						"candidate_category": "Weak Invoice Total Similarity",
						"payment_event_found": 0,
						"payment_event_source": None,
					}
				]
			)
		self.assertEqual(result["created_count"], 0)
		self.assertEqual(result["unsafe_count"], 1)
		self.assertEqual(
			result["unsafe"][0]["reason"],
			"Invoice total matched, but RetailEdge requires Payment Entry or invoice payment row evidence.",
		)

	@patch("retailedge.bank_transaction_match_workflow._prepare_created_match_review_record")
	@patch("retailedge.bank_transaction_match_workflow.create_or_get_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_create_review_records_suppresses_duplicate_candidates_in_batch(
		self,
		_mock_roles,
		_mock_access,
		_mock_exists,
		_mock_get_value,
		_mock_invoice_confirmed,
		_mock_payment_confirmed,
		mock_create,
		mock_prepare,
	):
		mock_create.return_value = {
			"name": "RE-BTM-2026-0001",
			"created": True,
			"decision_status": "Suggested",
		}
		rows = [
			{
				"bank_transaction": "BT-LOW",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "PE-0001",
				"suggested_sales_invoice": "SINV-0001",
				"candidate_category": "Payment Entry Match",
				"payment_event_found": 1,
				"payment_event_source": "Payment Entry",
				"amount_scenario": "Partial Payment",
				"match_confidence": "Possible Match",
				"match_score": 70,
				"amount_difference": 500,
			},
			{
				"bank_transaction": "BT-BEST",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "PE-0001",
				"suggested_sales_invoice": "SINV-0001",
				"candidate_category": "Payment Entry Match",
				"payment_event_found": 1,
				"payment_event_source": "Payment Entry",
				"amount_scenario": "Submitted Payment Entry Amount",
				"match_confidence": "Strong Match",
				"match_score": 90,
				"amount_difference": 0,
			},
		]
		result = create_bank_match_reviews_from_suggestions(rows=rows)
		self.assertEqual(result["created_count"], 1)
		self.assertEqual(result["duplicate_candidate_skipped_count"], 1)
		self.assertIn("already suggested", result["duplicate_candidates"][0]["reason"])
		self.assertIn("BT-BEST", result["duplicate_candidates"][0]["reason"])
		self.assertEqual(result["created"][0]["bank_transaction"], "BT-BEST")
		mock_create.assert_called_once()
		mock_prepare.assert_called_once()

	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value="RE-BTM-REJECTED")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_create_review_records_skips_previously_rejected_exact_pair_by_default(
		self,
		_mock_roles,
		_mock_access,
		_mock_exists,
		_mock_get_value,
		_mock_invoice_confirmed,
		_mock_payment_confirmed,
	):
		result = create_bank_match_reviews_from_suggestions(
			rows=[
				{
					"bank_transaction": "BT-REJECTED",
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-0001",
					"candidate_category": "Payment Entry Match",
					"payment_event_found": 1,
					"payment_event_source": "Payment Entry",
				}
			]
		)
		self.assertEqual(result["created_count"], 0)
		self.assertEqual(result["duplicate_count"], 1)
		self.assertEqual(result["duplicates"][0]["match_record"], "RE-BTM-REJECTED")
		self.assertEqual(result["duplicates"][0]["reason"], "Previously rejected match pair.")

	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", side_effect=[None, None, "RE-BTM-EXISTING"])
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_create_review_records_skips_duplicate_review_record(
		self,
		_mock_roles,
		_mock_access,
		_mock_exists,
		_mock_get_value,
		_mock_invoice_confirmed,
		_mock_payment_confirmed,
	):
		result = create_bank_match_reviews_from_suggestions(
			rows=[
				{
					"bank_transaction": "BT-0001",
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-0001",
					"suggested_sales_invoice": "SINV-0001",
					"candidate_category": "Payment Entry Match",
					"payment_event_found": 1,
					"payment_event_source": "Payment Entry",
				}
			]
		)
		self.assertEqual(result["duplicate_count"], 1)
		self.assertEqual(result["duplicates"][0]["match_record"], "RE-BTM-EXISTING")

	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value")
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_existing_active_review_record_blocks_duplicate_candidate_creation(
		self,
		_mock_roles,
		_mock_access,
		_mock_exists,
		mock_get_value,
		_mock_invoice_confirmed,
		_mock_payment_confirmed,
	):
		mock_get_value.side_effect = [None, None, None, "RE-BTM-ACTIVE"]
		result = create_bank_match_reviews_from_suggestions(
			rows=[
				{
					"bank_transaction": "BT-0002",
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-0001",
					"suggested_sales_invoice": "SINV-0001",
					"candidate_category": "Payment Entry Match",
					"payment_event_found": 1,
					"payment_event_source": "Payment Entry",
				}
			]
		)
		self.assertEqual(result["duplicate_count"], 1)
		self.assertEqual(result["duplicates"][0]["match_record"], "RE-BTM-ACTIVE")

	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	def test_create_review_records_skips_already_confirmed_sales_invoice(
		self,
		_mock_roles,
		_mock_access,
		_mock_exists,
		_mock_confirmed,
	):
		result = create_bank_match_reviews_from_suggestions(
			rows=[
				{
					"bank_transaction": "BT-0001",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-0001",
					"suggested_sales_invoice": "SINV-0001",
					"candidate_category": "Invoice Payment Row Match",
					"payment_event_found": 1,
					"payment_event_source": "Invoice Payment Row",
				}
			]
		)
		self.assertEqual(result["already_matched_count"], 1)
		self.assertIn("confirmed bank match", result["already_matched"][0]["reason"])

	@patch("retailedge.bank_transaction_match_workflow.frappe.get_doc")
	@patch("retailedge.bank_transaction_match_workflow.append_bank_transaction_match_action_log")
	def test_prepare_created_weak_match_sets_needs_review(self, mock_append_log, mock_get_doc):
		from retailedge.bank_transaction_match_workflow import _prepare_created_match_review_record

		doc = _FakeMatchDoc(name="RE-BTM-2026-0001", decision_status="Suggested")
		mock_get_doc.return_value = doc
		_prepare_created_match_review_record(
			"RE-BTM-2026-0001",
			{"bank_transaction": "BT-0001", "match_confidence": "Weak Match", "match_score": 35},
		)
		self.assertEqual(doc.decision_status, "Needs Review")
		self.assertIn("weak", doc.decision_note.lower())
		mock_append_log.assert_called_once()
		self.assertTrue(doc.save_called)

	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch("retailedge.bank_transaction_matching.get_first_day", return_value="2026-05-01")
	@patch("retailedge.bank_transaction_matching.nowdate", return_value="2026-05-24")
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch(
		"retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction",
		return_value=[],
	)
	@patch(
		"retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Sales Invoice",
				"document_name": "SINV-0001",
				"suggested_sales_invoice": "SINV-0001",
				"customer": "CUST-0001",
				"customer_display": "ABC Stores",
				"party": "CUST-0001",
				"party_type": "Customer",
				"candidate_amount": 10000,
				"amount_difference": 0,
				"score": 90,
				"confidence": "Strong Match",
				"reasons": ["Amount and reference match."],
				"payment_verification_status": "Unverified",
			}
		],
	)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"branch": "Airport Branch",
			"bank_account": "Moniepoint - moniepoint",
			"transaction_date": "2026-05-24",
			"amount": 10000,
			"reference": "TRF123",
			"description": "ABC Stores transfer",
			"direction": "Inflow",
			"is_reconciled": False,
		},
	)
	@patch(
		"retailedge.bank_transaction_matching._get_bank_transaction_rows",
		return_value=[{"name": "ACC-BTN-0001"}],
	)
	def test_matching_rows_show_existing_decision_status(
		self,
		_mock_rows,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		mock_get_all,
		_mock_nowdate,
		_mock_first_day,
		_mock_doctype,
	):
		mock_get_all.return_value = [
			{
				"name": "RE-BTM-2026-0001",
				"bank_transaction": "ACC-BTN-0001",
				"suggested_document_type": "Sales Invoice",
				"suggested_document": "SINV-0001",
				"sales_invoice": "SINV-0001",
				"payment_entry": None,
				"decision_status": "Confirmed",
				"modified": "2026-05-24 10:00:00",
			}
		]
		rows = get_bank_transaction_matching_rows(
			filters={
				"from_date": "2026-05-01",
				"to_date": "2026-05-31",
				"include_confirmed_matches": 1,
			"review_queue_status": "Confirmed",
			}
		)
		self.assertEqual(rows[0]["action_status"], "Already Confirmed")
		self.assertEqual(rows[0]["decision_status"], "Confirmed")
		self.assertEqual(rows[0]["match_record"], "RE-BTM-2026-0001")
