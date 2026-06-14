# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch
import json
from retailedge.services.edgepay_bank_match_review import (
	get_edgepay_bank_match_review_preflight,
	create_edgepay_bank_match_review,
	mark_edgepay_evidence_match_review_created
)

class TestEdgePayBankMatchReview(FrappeTestCase):
	def setUp(self):
		super(TestEdgePayBankMatchReview, self).setUp()
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
		frappe.db.delete("RetailEdge Bank Transaction Match Action Log")
		
		frappe.set_user("Administrator")

	def tearDown(self):
		self.get_value_patcher.stop()
		self.get_doc_patcher.stop()
		self.exists_patcher.stop()
		
		frappe.db.delete("RetailEdge EdgePay Payment Evidence")
		frappe.db.delete("Payment Entry")
		frappe.db.delete("Bank Transaction")
		frappe.db.delete("RetailEdge Bank Transaction Match")
		frappe.db.delete("RetailEdge Bank Transaction Match Action Log")
		frappe.db.commit()
		frappe.set_user("Administrator")
		super(TestEdgePayBankMatchReview, self).tearDown()

	def mock_exists(self, *args, **kwargs):
		if args:
			dt = args[0]
			dn = args[1] if len(args) > 1 else None
		else:
			dt = kwargs.get("dt")
			dn = kwargs.get("dn")

		if dt == "Sales Invoice" and isinstance(dn, str) and dn.startswith("SINV-RE-"):
			return True
		if dt in ("Customer", "Account", "Company", "Mode of Payment", "EdgePay Status Handoff Event", "EdgePay Payment Request", "EdgePay Payment Transaction", "Branch", "Bank Account"):
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

		if dt in ("Customer", "Account", "Company", "Mode of Payment", "Sales Invoice", "EdgePay Status Handoff Event", "EdgePay Payment Request", "EdgePay Payment Transaction", "Branch", "Bank Account") and (not dn or isinstance(dn, str | int)):
			if dt == "Sales Invoice" and flds == "customer":
				return "Test Customer"
			as_dict = kwargs.get("as_dict") or (len(args) > 3 and args[3])
			if as_dict:
				res = frappe._dict({"name": dn})
				if isinstance(flds, (tuple, list, set)):
					for f in flds:
						if f != "name":
							res[f] = None
				return res
			if isinstance(flds, (tuple, list, set)):
				return tuple(dn if f == "name" else None for f in flds)
			if flds != "name":
				return None
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

	def create_bank_transaction(self, name, deposit=1500.0, currency="NGN", ref_no="test-prov-ref-123", status="Unreconciled", docstatus=1):
		bt = frappe.new_doc("Bank Transaction")
		bt.name = name
		bt.date = "2026-06-13"
		bt.status = status
		bt.bank_account = "Test Bank Account"
		bt.company = "Process Edge (Demo)"
		bt.deposit = deposit
		bt.withdrawal = 0.0
		bt.currency = currency
		bt.reference_number = ref_no
		bt.description = f"Incoming payment from reference {ref_no}"
		bt.docstatus = docstatus
		bt.flags.ignore_validate = True
		bt.flags.name_set = True
		return bt.insert(ignore_permissions=True, ignore_links=True)

	def test_evidence_not_reviewed_blocks_review_creation(self):
		ev = self.create_evidence("EPE-MTR-001", review_status="Pending Review")
		res = get_edgepay_bank_match_review_preflight(ev.name)
		self.assertFalse(res["ok"])
		self.assertIn("is not Reviewed", res["message"])

	def test_evidence_not_submitted_blocks_review_creation(self):
		ev = self.create_evidence("EPE-MTR-002", submission_status="Not Submitted")
		res = get_edgepay_bank_match_review_preflight(ev.name)
		self.assertFalse(res["ok"])
		self.assertIn("submission status is not Submitted", res["message"])

	def test_missing_payment_entry_blocks_review_creation(self):
		ev = self.create_evidence("EPE-MTR-003")
		res = get_edgepay_bank_match_review_preflight(ev.name)
		self.assertFalse(res["ok"])
		self.assertIn("No linked Payment Entry", res["message"])

	def test_missing_bank_transaction_blocks_review_creation(self):
		ev = self.create_evidence("EPE-MTR-004")
		pe = self.create_payment_entry("ACC-PAY-MTR-004", docstatus=1)
		ev.db_set("payment_entry", pe.name)
		
		# Preflight with a non-existent bank transaction name
		res = get_edgepay_bank_match_review_preflight(ev.name, "BT-MISSING-123")
		self.assertFalse(res["ok"])
		self.assertIn("does not exist", res["message"])

	def test_reconciled_bank_transaction_blocks_review_creation(self):
		ev = self.create_evidence("EPE-MTR-005")
		pe = self.create_payment_entry("ACC-PAY-MTR-005", docstatus=1)
		ev.db_set("payment_entry", pe.name)
		bt = self.create_bank_transaction("BT-MTR-005", status="Reconciled")
		
		res = get_edgepay_bank_match_review_preflight(ev.name, bt.name)
		self.assertFalse(res["ok"])
		self.assertIn("is already reconciled", res["message"])

	def test_amount_mismatch_blocks_review_creation(self):
		ev = self.create_evidence("EPE-MTR-006", amount=1500.0)
		pe = self.create_payment_entry("ACC-PAY-MTR-006", docstatus=1, amount=1500.0)
		ev.db_set("payment_entry", pe.name)
		bt = self.create_bank_transaction("BT-MTR-006", deposit=2000.0) # different amount
		
		res = get_edgepay_bank_match_review_preflight(ev.name, bt.name)
		self.assertFalse(res["ok"])
		self.assertIn("Amount mismatch", res["message"])

	def test_currency_mismatch_blocks_review_creation(self):
		ev = self.create_evidence("EPE-MTR-007", currency="USD")
		pe = self.create_payment_entry("ACC-PAY-MTR-007", docstatus=1, currency="USD")
		ev.db_set("payment_entry", pe.name)
		bt = self.create_bank_transaction("BT-MTR-007", currency="NGN") # different currency
		
		res = get_edgepay_bank_match_review_preflight(ev.name, bt.name)
		self.assertFalse(res["ok"])
		self.assertIn("Currency mismatch", res["message"])

	def test_valid_evidence_and_candidate_creates_match_review(self):
		ev = self.create_evidence("EPE-MTR-008", amount=1500.0)
		pe = self.create_payment_entry("ACC-PAY-MTR-008", docstatus=1, amount=1500.0)
		ev.db_set("payment_entry", pe.name)
		bt = self.create_bank_transaction("BT-MTR-008", deposit=1500.0)
		
		res = create_edgepay_bank_match_review(ev.name, bt.name)
		self.assertTrue(res["ok"])
		self.assertTrue(res["created"])
		
		# Verify RetailEdge Bank Transaction Match record is created
		self.assertTrue(frappe.db.exists("RetailEdge Bank Transaction Match", res["review_name"]))
		
		# Verify Payment Evidence is updated with linked_bank_transaction and linked_bank_match_review
		ev_updated = frappe.get_doc("RetailEdge EdgePay Payment Evidence", ev.name)
		self.assertEqual(ev_updated.reconciliation_status, "Matched")
		self.assertEqual(ev_updated.linked_bank_transaction, bt.name)
		self.assertEqual(ev_updated.linked_bank_match_review, res["review_name"])
		
		# Verify review is NOT auto-confirmed (decision_status must be Suggested or Draft, not Confirmed)
		match_doc = frappe.get_doc("RetailEdge Bank Transaction Match", res["review_name"])
		self.assertNotEqual(match_doc.decision_status, "Confirmed")
		self.assertEqual(match_doc.payment_entry, pe.name)
		
		# Verify no Bank Transaction is mutated (e.g. status remains Unreconciled)
		bt_updated = frappe.get_doc("Bank Transaction", bt.name)
		self.assertEqual(bt_updated.status, "Unreconciled")

	def test_duplicate_call_returns_existing_review_safely(self):
		ev = self.create_evidence("EPE-MTR-009", amount=1500.0)
		pe = self.create_payment_entry("ACC-PAY-MTR-009", docstatus=1, amount=1500.0)
		ev.db_set("payment_entry", pe.name)
		bt = self.create_bank_transaction("BT-MTR-009", deposit=1500.0)
		
		res1 = create_edgepay_bank_match_review(ev.name, bt.name)
		self.assertTrue(res1["ok"])
		self.assertTrue(res1["created"])
		review_name1 = res1["review_name"]
		
		res2 = create_edgepay_bank_match_review(ev.name, bt.name)
		self.assertTrue(res2["ok"])
		self.assertFalse(res2["created"]) # was not created again
		self.assertEqual(res2["review_name"], review_name1)

	def test_no_direct_accounting_entries_created(self):
		# No GL entries or Journal entries should be created during review creation
		gl_count_before = frappe.db.count("GL Entry")
		je_count_before = frappe.db.count("Journal Entry")
		
		ev = self.create_evidence("EPE-MTR-010", amount=1500.0)
		pe = self.create_payment_entry("ACC-PAY-MTR-010", docstatus=1, amount=1500.0)
		ev.db_set("payment_entry", pe.name)
		bt = self.create_bank_transaction("BT-MTR-010", deposit=1500.0)
		
		create_edgepay_bank_match_review(ev.name, bt.name)
		
		self.assertEqual(frappe.db.count("GL Entry"), gl_count_before)
		self.assertEqual(frappe.db.count("Journal Entry"), je_count_before)
