from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.bank_matching_operational_reports import (
    get_bank_match_reconciliation_readiness_rows,
    get_unmatched_bank_payment_event_rows,
    get_unmatched_bank_transaction_rows,
)
from retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness.retailedge_bank_match_reconciliation_readiness import (
    execute as execute_readiness_report,
)
from retailedge.retailedge.report.retailedge_unmatched_bank_payment_events.retailedge_unmatched_bank_payment_events import (
    execute as execute_unmatched_payment_events_report,
)
from retailedge.retailedge.report.retailedge_unmatched_bank_transactions.retailedge_unmatched_bank_transactions import (
    execute as execute_unmatched_bank_transactions_report,
)


class BankMatchingOperationalReportsTests(unittest.TestCase):
    def test_r53_report_jsons_disable_prepared_report_mode(self):
        report_paths = [
            "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_unmatched_bank_transactions/retailedge_unmatched_bank_transactions.json",
            "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_unmatched_bank_payment_events/retailedge_unmatched_bank_payment_events.json",
            "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_bank_match_reconciliation_readiness/retailedge_bank_match_reconciliation_readiness.json",
        ]
        for report_path in report_paths:
            with self.subTest(report_path=report_path):
                with open(report_path, encoding="utf-8") as handle:
                    report_json = json.load(handle)
                self.assertEqual(report_json.get("disable_prepared_report"), 1)
                self.assertEqual(report_json.get("prepared_report"), 0)

    def test_r53_report_js_forces_live_refresh_behavior(self):
        report_paths = [
            "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_unmatched_bank_transactions/retailedge_unmatched_bank_transactions.js",
            "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_unmatched_bank_payment_events/retailedge_unmatched_bank_payment_events.js",
            "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_bank_match_reconciliation_readiness/retailedge_bank_match_reconciliation_readiness.js",
        ]
        for report_path in report_paths:
            with self.subTest(report_path=report_path):
                script = open(report_path, encoding="utf-8").read()
                self.assertIn("report.ignore_prepared_report = true;", script)
                self.assertIn("report.prepared_report = false;", script)
                self.assertIn('__("Refresh Report")', script)

    @patch("retailedge.bank_matching_operational_reports._build_unmatched_bank_transaction_row")
    @patch("retailedge.bank_matching_operational_reports._get_existing_matches_by_bank_transaction")
    @patch("retailedge.bank_matching_operational_reports.normalize_bank_transaction")
    @patch("retailedge.bank_matching_operational_reports._get_bank_transaction_rows")
    def test_unmatched_bank_transactions_exclude_active_and_confirmed_by_default(self, mock_rows, mock_normalize, mock_matches, mock_build):
        mock_rows.return_value = [
            {"name": "BT-OPEN"},
            {"name": "BT-ACTIVE"},
            {"name": "BT-CONFIRMED"},
        ]
        normalized = {
            "BT-OPEN": {"bank_transaction": "BT-OPEN", "is_reconciled": 0, "direction": "Inflow", "amount": 100},
            "BT-ACTIVE": {"bank_transaction": "BT-ACTIVE", "is_reconciled": 0, "direction": "Inflow", "amount": 100},
            "BT-CONFIRMED": {"bank_transaction": "BT-CONFIRMED", "is_reconciled": 0, "direction": "Inflow", "amount": 100},
        }
        mock_normalize.side_effect = lambda row: normalized[row.get("name")]
        mock_matches.return_value = {
            "BT-ACTIVE": [{"decision_status": "Needs Review"}],
            "BT-CONFIRMED": [{"decision_status": "Confirmed"}],
        }
        mock_build.side_effect = lambda bank_transaction, matches, filters: {"bank_transaction": bank_transaction.get("bank_transaction")}

        rows = get_unmatched_bank_transaction_rows({"from_date": "2026-05-01", "to_date": "2026-05-31"})
        self.assertEqual(rows, [{"bank_transaction": "BT-OPEN"}])

    @patch("retailedge.bank_matching_operational_reports._find_candidate_bank_transaction_for_event", return_value=None)
    @patch("retailedge.bank_matching_operational_reports._active_review_match_for_candidate", return_value=None)
    @patch("retailedge.bank_matching_operational_reports.sales_invoice_has_active_confirmed_bank_match", return_value=False)
    @patch("retailedge.bank_matching_operational_reports.get_sales_invoice_payment_rows")
    @patch("retailedge.bank_matching_operational_reports._get_sales_invoice_doc")
    @patch("retailedge.bank_matching_operational_reports._get_sales_invoice_payment_event_source_rows")
    @patch("retailedge.bank_matching_operational_reports._payment_entry_event_rows", return_value=[])
    @patch("retailedge.bank_matching_operational_reports.has_doctype", return_value=True)
    def test_unmatched_bank_payment_events_exclude_cash_rows_and_keep_non_cash_amount(self, _mock_doctype, _mock_payment_entry_events, mock_invoice_rows, mock_invoice_doc, mock_payment_rows, _mock_confirmed, _mock_active_review, _mock_find_bank):
        mock_invoice_rows.return_value = [
            {"name": "ACC-SINV-2026-00025", "posting_date": "2026-05-20", "company": "Process Edge (Demo)", "customer": "Palmer", "customer_name": "Palmer Productions", "retailedge_branch": "HQ"}
        ]
        mock_invoice_doc.return_value = SimpleNamespace(docstatus=1)
        mock_payment_rows.return_value = [
            {"payment_row_index": 1, "mode_of_payment": "Cash", "account": "Cash - PED", "base_amount": 500, "amount": 500, "payment_category": "Cash", "expected_account": "Cash - PED"},
            {"payment_row_index": 2, "mode_of_payment": "Moniepoint", "account": "Demo Bank Account - PED", "base_amount": 810, "amount": 810, "payment_category": "Bank Transfer", "expected_account": "Demo Bank Account - PED"},
        ]

        rows = get_unmatched_bank_payment_event_rows({"from_date": "2026-05-01", "to_date": "2026-05-31"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["payment_event_document"], "ACC-SINV-2026-00025")
        self.assertEqual(rows[0]["amount"], 810)
        self.assertEqual(rows[0]["mode_of_payment"], "Moniepoint")

    @patch("retailedge.bank_matching_operational_reports._sales_invoice_payment_event_rows", return_value=[])
    @patch("retailedge.bank_matching_operational_reports._get_payment_entry_sales_invoice_references", return_value={})
    @patch("retailedge.bank_matching_operational_reports._get_payment_entry_event_source_rows")
    @patch("retailedge.bank_matching_operational_reports.payment_entry_has_active_confirmed_bank_match", return_value=True)
    @patch("retailedge.bank_matching_operational_reports.has_doctype", return_value=True)
    def test_confirmed_payment_entry_is_excluded_from_unmatched_events_by_default(self, _mock_doctype, _mock_confirmed, mock_rows, _mock_refs, _mock_sales_invoice_events):
        mock_rows.return_value = [
            {"name": "ACC-PAY-2026-00008", "posting_date": "2026-05-21", "company": "Process Edge (Demo)", "party": "West View", "party_type": "Customer", "paid_to": "Demo Bank Account - PED", "received_amount": 1000, "mode_of_payment": "Bank Transfer"}
        ]
        rows = get_unmatched_bank_payment_event_rows({"from_date": "2026-05-01", "to_date": "2026-05-31"})
        self.assertEqual(rows, [])

    @patch("retailedge.bank_matching_operational_reports._hydrate_match_candidate_context")
    @patch("retailedge.bank_matching_operational_reports._resolve_account_match_payload")
    @patch("retailedge.bank_matching_operational_reports.has_doctype", return_value=True)
    @patch("retailedge.bank_matching_operational_reports.frappe.get_all")
    def test_reconciliation_readiness_marks_confirmed_exact_payment_entry_match_ready(self, mock_get_all, _mock_doctype, mock_account_payload, mock_hydrate):
        mock_get_all.return_value = [
            {
                "name": "RE-BTM-0001",
                "bank_transaction": "ACC-BTN-2026-00008",
                "transaction_date": "2026-05-20",
                "bank_amount": 1000,
                "bank_account": "Moniepoint - moniepoint",
                "suggested_document_type": "Payment Entry",
                "suggested_document": "ACC-PAY-2026-00008",
                "sales_invoice": "ACC-SINV-2026-00026",
                "payment_entry": "ACC-PAY-2026-00008",
                "candidate_amount": 1000,
                "amount_difference": 0,
                "amount_scenario": "Submitted Payment Entry Amount",
                "match_confidence": "Strong Match",
                "match_score": 95,
                "match_reason": "Matched submitted Payment Entry.",
                "decision_status": "Confirmed",
                "confirmed_by": "Administrator",
                "confirmed_on": "2026-05-21 10:00:00",
                "branch": "HQ",
                "company": "Process Edge (Demo)",
                "party": "West View",
                "customer": "West View",
                "details_json": json.dumps({
                    "candidate_category": "payment_entry_match",
                    "payment_event_source": "Payment Entry",
                    "payment_entry_paid_amount": 1000,
                    "payment_account": "Demo Bank Account - PED",
                    "branch_match": 1,
                    "branch_match_available": 1,
                    "action_status": "Confirmed",
                }),
                "modified": "2026-05-21 10:00:00",
            }
        ]
        mock_hydrate.return_value = {
            "candidate_category": "payment_entry_match",
            "payment_event_source": "Payment Entry",
            "payment_account": "Demo Bank Account - PED",
            "payment_event_amount": 1000,
            "branch": "HQ",
        }
        mock_account_payload.return_value = {
            "status": "match_via_mapping",
            "bank_canonical_account": "Demo Bank Account - PED",
            "candidate_canonical_account": "Demo Bank Account - PED",
        }
        rows = get_bank_match_reconciliation_readiness_rows({"from_date": "2026-05-01", "to_date": "2026-05-31"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reconciliation_readiness_status"], "Ready for Reconciliation")

    @patch("retailedge.bank_matching_operational_reports._hydrate_match_candidate_context")
    @patch("retailedge.bank_matching_operational_reports._resolve_account_match_payload")
    @patch("retailedge.bank_matching_operational_reports.has_doctype", return_value=True)
    @patch("retailedge.bank_matching_operational_reports.frappe.get_all")
    def test_reconciliation_readiness_flags_account_mismatch_as_exception(self, mock_get_all, _mock_doctype, mock_account_payload, mock_hydrate):
        mock_get_all.return_value = [
            {
                "name": "RE-BTM-0002",
                "bank_transaction": "ACC-BTN-2026-00007",
                "transaction_date": "2026-05-26",
                "bank_amount": 1090,
                "bank_account": "Moniepoint - moniepoint",
                "suggested_document_type": "Payment Entry",
                "suggested_document": "ACC-PAY-2026-00012",
                "sales_invoice": "ACC-SINV-2026-00027",
                "payment_entry": "ACC-PAY-2026-00012",
                "candidate_amount": 1090,
                "amount_difference": 0,
                "amount_scenario": "Submitted Payment Entry Amount",
                "match_confidence": "Strong Match",
                "match_score": 95,
                "match_reason": "Matched submitted Payment Entry.",
                "decision_status": "Confirmed",
                "confirmed_by": "Administrator",
                "confirmed_on": "2026-05-26 10:00:00",
                "branch": "HQ",
                "company": "Process Edge (Demo)",
                "party": "West View",
                "customer": "West View",
                "details_json": json.dumps({
                    "candidate_category": "payment_entry_match",
                    "payment_event_source": "Payment Entry",
                    "payment_entry_paid_amount": 1090,
                    "payment_account": "Other Bank - PED",
                    "branch_match": 1,
                    "branch_match_available": 1,
                    "action_status": "Confirmed",
                }),
                "modified": "2026-05-26 10:00:00",
            }
        ]
        mock_hydrate.return_value = {
            "candidate_category": "payment_entry_match",
            "payment_event_source": "Payment Entry",
            "payment_account": "Other Bank - PED",
            "payment_event_amount": 1090,
            "branch": "HQ",
        }
        mock_account_payload.return_value = {
            "status": "mismatch",
            "bank_canonical_account": "Demo Bank Account - PED",
            "candidate_canonical_account": "Other Bank - PED",
        }
        rows = get_bank_match_reconciliation_readiness_rows({"from_date": "2026-05-01", "to_date": "2026-05-31"})
        self.assertEqual(rows[0]["reconciliation_readiness_status"], "Exception")
        self.assertEqual(rows[0]["exception_reason"], "Account mismatch")

    @patch("retailedge.retailedge.report.retailedge_unmatched_bank_transactions.retailedge_unmatched_bank_transactions.get_unmatched_bank_transaction_rows")
    def test_unmatched_bank_transactions_report_executes_from_current_helper_data(self, mock_rows):
        mock_rows.return_value = [{"bank_transaction": "ACC-BTN-2026-00008"}]
        _columns, rows, _message, _chart, _summary = execute_unmatched_bank_transactions_report({"from_date": "2026-05-01", "to_date": "2026-05-31"})
        self.assertEqual(rows, [{"bank_transaction": "ACC-BTN-2026-00008"}])

    @patch("retailedge.retailedge.report.retailedge_unmatched_bank_payment_events.retailedge_unmatched_bank_payment_events.get_unmatched_bank_payment_event_rows")
    def test_unmatched_bank_payment_events_report_executes_from_current_helper_data(self, mock_rows):
        mock_rows.return_value = [{"payment_event_document": "ACC-PAY-2026-00008"}]
        _columns, rows, _message, _chart, _summary = execute_unmatched_payment_events_report({"from_date": "2026-05-01", "to_date": "2026-05-31"})
        self.assertEqual(rows, [{"payment_event_document": "ACC-PAY-2026-00008"}])

    @patch("retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness.retailedge_bank_match_reconciliation_readiness.get_bank_match_reconciliation_readiness_rows")
    def test_reconciliation_readiness_report_executes_from_current_helper_data(self, mock_rows):
        mock_rows.return_value = [{"bank_match_review": "RE-BTM-0001"}]
        _columns, rows, _message, _chart, _summary = execute_readiness_report({"from_date": "2026-05-01", "to_date": "2026-05-31"})
        self.assertEqual(rows, [{"bank_match_review": "RE-BTM-0001"}])
