# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch
from retailedge.services.edgepay_reconciliation_readiness import (
	get_edgepay_reconciliation_readiness,
	mark_edgepay_evidence_reconciliation_ready,
	mark_edgepay_evidence_reconciliation_blocked,
	find_edgepay_payment_entry_bank_match_candidates
)

class TestEdgePayReconciliationReadiness(FrappeTestCase):
	def setUp(self):
		super(TestEdgePayReconciliationReadiness, self).setUp()
		self.original_exists = frappe.db.exists
		self.original_get_doc = frappe.get_doc
		self.original_get_value = frappe.db.get_value
		
		# Start patchers
		self.exists_patcher = patch("frappe.db.exists", side_effect=self.mock_exists)
		self.mocked_exists = self.exists_patcher.start()
		
		self.get_doc_patcher = patch("frappe.get_doc", side_effect=self.mock_get_doc)
		self.mocked_get_doc = self.get_doc_patcher.start()
		
		self.get_value_patcher = patch("frappe.db.get_value", side_effect=self.mock_get_value)
		self.mocked_get_value = self.get_value_patcher.start()
		
		frappe.db.delete("RetailEdge EdgePay Payment Evidence")
		frappe.db.delete("Payment Entry")
		frappe.db.delete("Bank Transaction")
		frappe.db.delete("RetailEdge Bank Transaction Match")
		
		frappe.set_user("Administrator")

	def tearDown(self):
		self.get_value_patcher.stop()
		self.get_doc_patcher.stop()
		self.exists_patcher.stop()
		
		frappe.db.delete("RetailEdge EdgePay Payment Evidence")
		frappe.db.delete("Payment Entry")
		frappe.db.delete("Bank Transaction")
		frappe.db.delete("RetailEdge Bank Transaction Match")
		frappe.db.commit()
		frappe.set_user("Administrator")
		super(TestEdgePayReconciliationReadiness, self).tearDown()

	def mock_exists(self, *args, **kwargs):
		if args:
			dt = args[0]
			dn = args[1] if len(args) > 1 else None
		else:
			dt = kwargs.get("dt")
			dn = kwargs.get("dn")

		if dt == "Sales Invoice" and isinstance(dn, str) and dn.startswith("SINV-RE-"):
			if dn == "SINV-RE-MISSING":
				return False
			return True
		if dt in ("Customer", "Account", "Company", "Mode of Payment", "EdgePay Status Handoff Event", "EdgePay Payment Request", "EdgePay Payment Transaction"):
			return True
		return self.original_exists(*args, **kwargs)

	def mock_get_value(self, *args, **kwargs):
		if args:
			dt = args[0]
			dn = args[1] if len(args) > 1 else None
			flds = args[2] if len(args) > 2 else "name"
		else:
			dt = kwargs.get("doctype")
			dn = kwargs.get("name")
			flds = kwargs.get("fieldname") or "name"

		if dt in ("Customer", "Account", "Company", "Mode of Payment", "Sales Invoice", "EdgePay Status Handoff Event", "EdgePay Payment Request", "EdgePay Payment Transaction") and (not dn or isinstance(dn, str | int)):
			if dt == "Sales Invoice" and flds == "customer":
				return "Test Customer"
			if flds != "name":
				return None
			as_dict = kwargs.get("as_dict") or (len(args) > 3 and args[3])
			if as_dict:
				res = frappe._dict({"name": dn})
				return res
			return dn
		if dt == "Bank Account" and isinstance(dn, dict) and dn.get("account") == "Cash - PE":
			return "Test Bank Account"

		return self.original_get_value(*args, **kwargs)

	def mock_get_doc(self, *args, **kwargs):
		if args:
			dt = args[0]
			name = args[1] if len(args) > 1 else None
		else:
			dt = kwargs.get("doctype")
			name = kwargs.get("name")

		if isinstance(dt, str) and dt == "Sales Invoice" and isinstance(name, str) and name.startswith("SINV-RE-"):
			return frappe._dict({
				"doctype": "Sales Invoice",
				"name": name,
				"grand_total": 1500.0,
				"outstanding_amount": 1500.0,
				"currency": "NGN",
				"customer": "Test Customer",
				"docstatus": 1
			})
		return self.original_get_doc(*args, **kwargs)

	def create_evidence(self, name, review_status="Reviewed", posting_status="Submitted", submission_status="Submitted", amount=1500.0, currency="NGN", provider_ref="test-prov-ref-123"):
		doc = frappe.get_doc({
			"doctype": "RetailEdge EdgePay Payment Evidence",
			"name": name,
			"edgepay_handoff_event": "EV-TEST-123",
			"edgepay_payment_request": "EP-PRQ-123",
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-RE-0001",
			"provider": "Test Posting Provider",
			"provider_reference": provider_ref,
			"amount": amount,
			"currency": currency,
			"request_status": "Paid",
			"transaction_status": "SUCCESS",
			"processing_status": "Evidence Created",
			"review_status": review_status,
			"posting_status": posting_status,
			"submission_status": submission_status,
			"idempotency_key": name + "-idemp"
		})
		doc.flags.name_set = True
		return doc.insert(ignore_permissions=True, ignore_links=True)

	def create_payment_entry(self, name, docstatus=1, amount=1500.0, currency="NGN", reference_no="test-prov-ref-123"):
		pe = frappe.new_doc("Payment Entry")
		pe.name = name
		pe.payment_type = "Receive"
		pe.party_type = "Customer"
		pe.party = "Test Customer"
		pe.company = "Process Edge (Demo)"
		pe.paid_from = "Debtors - PE"
		pe.paid_to = "Cash - PE"
		pe.paid_from_account_currency = currency
		pe.paid_to_account_currency = currency
		pe.source_exchange_rate = 1.0
		pe.target_exchange_rate = 1.0
		pe.paid_amount = amount
		pe.received_amount = amount
		pe.base_paid_amount = amount
		pe.base_received_amount = amount
		pe.reference_no = reference_no
		pe.reference_date = "2026-06-13"
		pe.docstatus = 0
		pe.flags.ignore_validate = True
		pe.append("references", {
			"reference_doctype": "Sales Invoice",
			"reference_name": "SINV-RE-0001",
			"allocated_amount": amount
		})
		pe.flags.name_set = True
		pe.insert(ignore_permissions=True, ignore_links=True)
		
		if docstatus == 1:
			pe.db_set("docstatus", 1)
		elif docstatus == 2:
			pe.db_set("docstatus", 2)
			
		return pe

	def create_bank_transaction(self, name, deposit=1500.0, currency="NGN", ref_no="test-prov-ref-123", status="Unreconciled", payment_entries=None):
		bt = frappe.new_doc("Bank Transaction")
		bt.name = name
		bt.date = "2026-06-13"
		bt.status = status
		bt.bank_account = "Test Bank Account"
		bt.deposit = deposit
		bt.withdrawal = 0.0
		bt.currency = currency
		bt.reference_number = ref_no
		bt.description = f"Incoming payment from reference {ref_no}"
		bt.docstatus = 1
		bt.flags.ignore_validate = True
		bt.flags.name_set = True
		
		if payment_entries:
			for pe in payment_entries:
				bt.append("payment_entries", pe)
				
		return bt.insert(ignore_permissions=True, ignore_links=True)

	def test_unsubmitted_evidence_fails_readiness(self):
		self.create_evidence("EPE-REC-001", posting_status="Draft Created", submission_status="Not Submitted")
		res = get_edgepay_reconciliation_readiness("EPE-REC-001")
		self.assertFalse(res["ok"])
		self.assertEqual(res["status"], "Not Ready")

	def test_submitted_evidence_with_submitted_payment_entry_passes_readiness(self):
		ev = self.create_evidence("EPE-REC-002", provider_ref="ref-rec-2")
		pe = self.create_payment_entry("ACC-PAY-REC-2", docstatus=1, reference_no="ref-rec-2")
		ev.db_set("payment_entry", pe.name)
		
		res = get_edgepay_reconciliation_readiness("EPE-REC-002")
		self.assertTrue(res["ok"])
		self.assertEqual(res["status"], "Ready")

	def test_missing_payment_entry_blocks_readiness(self):
		ev = self.create_evidence("EPE-REC-003")
		res = get_edgepay_reconciliation_readiness("EPE-REC-003")
		self.assertFalse(res["ok"])
		self.assertEqual(res["status"], "Blocked")
		self.assertIn("No linked Payment Entry", res["message"])

	def test_draft_payment_entry_blocks_readiness(self):
		ev = self.create_evidence("EPE-REC-004", provider_ref="ref-rec-4")
		pe = self.create_payment_entry("ACC-PAY-REC-4", docstatus=0, reference_no="ref-rec-4")
		ev.db_set("payment_entry", pe.name)
		
		res = get_edgepay_reconciliation_readiness("EPE-REC-004")
		self.assertFalse(res["ok"])
		self.assertEqual(res["status"], "Blocked")
		self.assertIn("is not submitted", res["message"])

	def test_cancelled_payment_entry_blocks_readiness(self):
		ev = self.create_evidence("EPE-REC-005", provider_ref="ref-rec-5")
		pe = self.create_payment_entry("ACC-PAY-REC-5", docstatus=2, reference_no="ref-rec-5")
		ev.db_set("payment_entry", pe.name)
		
		res = get_edgepay_reconciliation_readiness("EPE-REC-005")
		self.assertFalse(res["ok"])
		self.assertEqual(res["status"], "Blocked")
		self.assertIn("is cancelled", res["message"])

	def test_amount_mismatch_blocks_readiness(self):
		ev = self.create_evidence("EPE-REC-006", provider_ref="ref-rec-6", amount=1500.0)
		pe = self.create_payment_entry("ACC-PAY-REC-6", docstatus=1, amount=2000.0, reference_no="ref-rec-6")
		ev.db_set("payment_entry", pe.name)
		
		res = get_edgepay_reconciliation_readiness("EPE-REC-006")
		self.assertFalse(res["ok"])
		self.assertEqual(res["status"], "Blocked")
		self.assertIn("Amount mismatch", res["message"])

	def test_currency_mismatch_blocks_readiness(self):
		ev = self.create_evidence("EPE-REC-007", provider_ref="ref-rec-7", currency="USD")
		pe = self.create_payment_entry("ACC-PAY-REC-7", docstatus=1, reference_no="ref-rec-7", currency="NGN")
		ev.db_set("payment_entry", pe.name)
		
		res = get_edgepay_reconciliation_readiness("EPE-REC-007")
		self.assertFalse(res["ok"])
		self.assertEqual(res["status"], "Blocked")
		self.assertIn("Currency mismatch", res["message"])

	def test_conflicting_payment_entry_blocks_readiness(self):
		ev = self.create_evidence("EPE-REC-008", provider_ref="ref-rec-8")
		pe = self.create_payment_entry("ACC-PAY-REC-8", docstatus=1, reference_no="ref-rec-8")
		ev.db_set("payment_entry", pe.name)
		
		# Create another submitted Payment Entry with same reference number
		self.create_payment_entry("ACC-PAY-REC-8-DUP", docstatus=1, reference_no="ref-rec-8")
		
		res = get_edgepay_reconciliation_readiness("EPE-REC-008")
		self.assertFalse(res["ok"])
		self.assertEqual(res["status"], "Blocked")
		self.assertIn("Conflicting submitted Payment Entry", res["message"])

	def test_readiness_marking_is_idempotent(self):
		ev = self.create_evidence("EPE-REC-009", provider_ref="ref-rec-9")
		pe = self.create_payment_entry("ACC-PAY-REC-9", docstatus=1, reference_no="ref-rec-9")
		ev.db_set("payment_entry", pe.name)
		
		# First marking
		res1 = mark_edgepay_evidence_reconciliation_ready("EPE-REC-009")
		self.assertTrue(res1["ok"])
		self.assertEqual(res1["status"], "Ready")
		
		# Second marking
		res2 = mark_edgepay_evidence_reconciliation_ready("EPE-REC-009")
		self.assertTrue(res2["ok"])
		self.assertEqual(res2["status"], "Ready")

	def test_completed_reconciliation_updates_status(self):
		ev = self.create_evidence("EPE-REC-010", provider_ref="ref-rec-10")
		pe = self.create_payment_entry("ACC-PAY-REC-10", docstatus=1, reference_no="ref-rec-10")
		ev.db_set("payment_entry", pe.name)
		
		# Create reconciled Bank Transaction with child entries
		bt = self.create_bank_transaction("BT-REC-10", ref_no="ref-rec-10", status="Reconciled", payment_entries=[{
			"payment_document": "Payment Entry",
			"payment_entry": pe.name,
			"allocated_amount": 1500.0,
			"clearance_date": "2026-06-13"
		}])
		frappe.db.commit()
		
		res = get_edgepay_reconciliation_readiness("EPE-REC-010")
		self.assertTrue(res["ok"])
		self.assertEqual(res["status"], "Reconciled")
		self.assertEqual(res["linked_bank_transaction"], bt.name)

	def test_confirmed_match_review_updates_status(self):
		ev = self.create_evidence("EPE-REC-011", provider_ref="ref-rec-11")
		pe = self.create_payment_entry("ACC-PAY-REC-11", docstatus=1, reference_no="ref-rec-11")
		ev.db_set("payment_entry", pe.name)
		
		# Create confirmed RetailEdge Bank Transaction Match doc
		bt = self.create_bank_transaction("BT-REC-11", ref_no="ref-rec-11")
		match_doc = frappe.get_doc({
			"doctype": "RetailEdge Bank Transaction Match",
			"bank_transaction": bt.name,
			"suggested_document_type": "Payment Entry",
			"suggested_document": pe.name,
			"payment_entry": pe.name,
			"decision_status": "Confirmed"
		})
		match_doc.insert(ignore_permissions=True, ignore_links=True)
		frappe.db.commit()
		
		res = get_edgepay_reconciliation_readiness("EPE-REC-011")
		self.assertTrue(res["ok"])
		self.assertEqual(res["status"], "Matched")
		self.assertEqual(res["linked_bank_transaction"], bt.name)
		self.assertEqual(res["linked_bank_match_review"], match_doc.name)

	def test_candidate_search_is_read_only(self):
		ev = self.create_evidence("EPE-REC-012", provider_ref="ref-rec-12")
		pe = self.create_payment_entry("ACC-PAY-REC-12", docstatus=1, reference_no="ref-rec-12")
		ev.db_set("payment_entry", pe.name)
		
		self.create_bank_transaction("BT-REC-12-CAND", ref_no="ref-rec-12")
		
		bt_count_before = frappe.db.count("Bank Transaction")
		pe_count_before = frappe.db.count("Payment Entry")
		match_count_before = frappe.db.count("RetailEdge Bank Transaction Match")
		
		candidates = find_edgepay_payment_entry_bank_match_candidates("EPE-REC-012")
		
		# Candidate search must be read-only and not mutate databases
		self.assertEqual(frappe.db.count("Bank Transaction"), bt_count_before)
		self.assertEqual(frappe.db.count("Payment Entry"), pe_count_before)
		self.assertEqual(frappe.db.count("RetailEdge Bank Transaction Match"), match_count_before)
		
		self.assertEqual(len(candidates), 1)
		self.assertEqual(candidates[0]["bank_transaction"], "BT-REC-12-CAND")
		self.assertEqual(candidates[0]["confidence"], "High")

	def test_no_bank_transaction_is_created_or_mutated(self):
		ev = self.create_evidence("EPE-REC-013", provider_ref="ref-rec-13")
		pe = self.create_payment_entry("ACC-PAY-REC-13", docstatus=1, reference_no="ref-rec-13")
		ev.db_set("payment_entry", pe.name)
		
		bt_count_before = frappe.db.count("Bank Transaction")
		
		# Call get and mark readiness
		get_edgepay_reconciliation_readiness("EPE-REC-013")
		mark_edgepay_evidence_reconciliation_ready("EPE-REC-013")
		
		# Verify no mutation on Bank Transaction table
		self.assertEqual(frappe.db.count("Bank Transaction"), bt_count_before)
