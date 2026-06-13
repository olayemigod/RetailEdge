# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch
from retailedge.services.edgepay_payment_posting import (
	get_edgepay_evidence_posting_preflight,
	prepare_edgepay_payment_entry_draft,
	mark_edgepay_evidence_posting_ready,
	mark_edgepay_evidence_posting_blocked,
	get_edgepay_payment_entry_submission_preflight,
	submit_edgepay_payment_entry,
	mark_edgepay_evidence_submission_blocked
)
from retailedge.api import (
	get_edgepay_evidence_posting_preflight as api_get_preflight,
	prepare_edgepay_payment_entry_draft as api_prepare_draft,
	get_edgepay_payment_entry_submission_preflight as api_get_sub_preflight,
	submit_edgepay_payment_entry as api_submit_entry
)

class TestEdgePayPaymentPosting(FrappeTestCase):
	def setUp(self):
		super(TestEdgePayPaymentPosting, self).setUp()
		self.original_exists = frappe.db.exists
		self.original_get_doc = frappe.get_doc
		self.original_get_value = frappe.db.get_value
		
		# Start global patchers for tests
		self.exists_patcher = patch("frappe.db.exists", side_effect=self.mock_exists)
		self.mocked_exists = self.exists_patcher.start()
		
		self.get_doc_patcher = patch("frappe.get_doc", side_effect=self.mock_get_doc)
		self.mocked_get_doc = self.get_doc_patcher.start()
		
		self.get_value_patcher = patch("frappe.db.get_value", side_effect=self.mock_get_value)
		self.mocked_get_value = self.get_value_patcher.start()
		
		self.get_pe_patcher = patch("retailedge.services.edgepay_payment_posting.get_payment_entry", side_effect=self.mock_get_payment_entry)
		self.mocked_get_pe = self.get_pe_patcher.start()
		
		frappe.db.delete("EdgePay Status Handoff Event")
		frappe.db.delete("RetailEdge EdgePay Handoff Log")
		frappe.db.delete("EdgePay Payment Request")
		frappe.db.delete("RetailEdge EdgePay Payment Evidence")
		frappe.db.delete("Payment Entry")
		
		# Ensure test role/provider exists
		if not frappe.db.exists("EdgePay Provider", "Test Posting Provider"):
			frappe.get_doc({
				"doctype": "EdgePay Provider",
				"provider_name": "Test Posting Provider",
				"provider_code": "monnify",
				"enabled": 1,
				"sandbox_mode": 1,
				"provider_type": "Monnify",
				"status": "Active",
				"base_url": "https://sandbox.monnify.com/api",
				"api_key": "test_posting_api_key",
				"secret_key": "test_posting_secret_key"
			}).insert()
			
		frappe.set_user("Administrator")

	def tearDown(self):
		self.get_pe_patcher.stop()
		self.get_value_patcher.stop()
		self.get_doc_patcher.stop()
		self.exists_patcher.stop()
		
		frappe.db.delete("EdgePay Status Handoff Event")
		frappe.db.delete("RetailEdge EdgePay Handoff Log")
		frappe.db.delete("EdgePay Payment Request")
		frappe.db.delete("RetailEdge EdgePay Payment Evidence")
		frappe.db.delete("Payment Entry")
		if frappe.db.exists("EdgePay Provider", "Test Posting Provider"):
			frappe.db.delete("EdgePay Provider", "Test Posting Provider")
		frappe.db.commit()
		frappe.set_user("Administrator")
		super(TestEdgePayPaymentPosting, self).tearDown()

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

		if dt in ("EdgePay Status Handoff Event", "EdgePay Payment Request", "EdgePay Payment Transaction", "Customer", "Account", "Company", "Mode of Payment", "Sales Invoice") and (not dn or isinstance(dn, str | int)):
			as_dict = kwargs.get("as_dict") or (len(args) > 3 and args[3])
			if as_dict:
				res = frappe._dict({"name": dn})
				if isinstance(flds, tuple | list | set):
					for f in flds:
						if f != "name":
							res[f] = None
				return res
			return dn

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
				"docstatus": 1
			})
		if isinstance(dt, str) and dt == "Payment Entry":
			doc = self.original_get_doc(dt, name)
			if getattr(self, "_mock_submit_failure", False):
				msg = getattr(self, "_mock_submit_failure_msg", "Mock submit failure")
				def fail_submit(*args, **kwargs):
					raise frappe.ValidationError(msg)
				doc.submit = fail_submit
			else:
				def dummy_submit(*args, **kwargs):
					doc.db_set("docstatus", 1)
					return doc
				doc.submit = dummy_submit
			return doc
		return self.original_get_doc(*args, **kwargs)

	def mock_get_payment_entry(self, dt, dn, party_amount=None, bank_amount=None):
		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Receive"
		pe.party_type = "Customer"
		pe.party = "Test Customer"
		pe.company = "Process Edge (Demo)"
		pe.paid_from = "Debtors - PE"
		pe.paid_to = "Cash - PE"
		pe.paid_from_account_currency = "NGN"
		pe.paid_to_account_currency = "NGN"
		pe.source_exchange_rate = 1.0
		pe.target_exchange_rate = 1.0
		pe.paid_amount = party_amount or 1500.0
		pe.received_amount = bank_amount or 1500.0
		pe.base_paid_amount = party_amount or 1500.0
		pe.base_received_amount = bank_amount or 1500.0
		pe.flags.ignore_validate = True
		pe.append("references", {
			"reference_doctype": dt,
			"reference_name": dn,
			"allocated_amount": party_amount or 1500.0
		})
		return pe

	def create_evidence(self, name, review_status="Reviewed", processing_status="Evidence Created", request_status="Paid", amount=1500.0, currency="NGN", provider_ref="test-prov-ref-123"):
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
			"request_status": request_status,
			"transaction_status": "SUCCESS",
			"processing_status": processing_status,
			"review_status": review_status,
			"idempotency_key": name + "-idemp"
		})
		doc.flags.name_set = True
		return doc.insert(ignore_permissions=True)

	def test_unreviewed_evidence_fails_preflight(self):
		self.create_evidence("EPE-TEST-001", review_status="Pending Review")
		res = get_edgepay_evidence_posting_preflight("EPE-TEST-001")
		self.assertFalse(res["ok"])
		self.assertIn("not Reviewed", res["message"])

	def test_reviewed_valid_paid_evidence_passes_preflight(self):
		self.create_evidence("EPE-TEST-002", review_status="Reviewed")
		res = get_edgepay_evidence_posting_preflight("EPE-TEST-002")
		self.assertTrue(res["ok"])
		self.assertEqual(res["message"], "Preflight passed.")

	def test_failed_pending_expired_cancelled_evidence_fails_preflight(self):
		statuses = ["Failed", "Pending", "Expired", "Cancelled"]
		for s in statuses:
			name = f"EPE-TEST-{s}"
			self.create_evidence(name, review_status="Reviewed", request_status=s)
			res = get_edgepay_evidence_posting_preflight(name)
			self.assertFalse(res["ok"])
			self.assertIn("status is not Paid", res["message"])

	def test_amount_mismatch_blocks_preflight(self):
		# Evidence has 2000.0, but mock Sales Invoice has 1500.0
		self.create_evidence("EPE-TEST-003", review_status="Reviewed", amount=2000.0)
		res = get_edgepay_evidence_posting_preflight("EPE-TEST-003")
		self.assertFalse(res["ok"])
		self.assertIn("Amount mismatch", res["message"])

	def test_currency_mismatch_blocks_preflight(self):
		# Evidence has USD, but mock Sales Invoice has NGN
		self.create_evidence("EPE-TEST-004", review_status="Reviewed", currency="USD")
		res = get_edgepay_evidence_posting_preflight("EPE-TEST-004")
		self.assertFalse(res["ok"])
		self.assertIn("Currency mismatch", res["message"])

	def test_missing_source_document_blocks_preflight(self):
		# Using SINV-RE-MISSING which mock_exists returns False for
		doc = self.create_evidence("EPE-TEST-005", review_status="Reviewed")
		doc.db_set("source_name", "SINV-RE-MISSING")
		
		res = get_edgepay_evidence_posting_preflight("EPE-TEST-005")
		self.assertFalse(res["ok"])
		self.assertIn("does not exist", res["message"])

	def test_duplicate_provider_reference_blocks_preflight(self):
		# Create a pre-existing Payment Entry with same provider ref
		pe = self.mock_get_payment_entry("Sales Invoice", "SINV-RE-0001")
		pe.reference_no = "test-prov-ref-dup"
		pe.insert(ignore_permissions=True)

		self.create_evidence("EPE-TEST-006", review_status="Reviewed", provider_ref="test-prov-ref-dup")
		res = get_edgepay_evidence_posting_preflight("EPE-TEST-006")
		self.assertFalse(res["ok"])
		self.assertIn("Conflicting Payment Entry", res["message"])

	def test_draft_payment_entry_prepared_successfully(self):
		self.create_evidence("EPE-TEST-007", review_status="Reviewed", provider_ref="test-prov-ref-ok")
		
		pe_count = frappe.db.count("Payment Entry")
		je_count = frappe.db.count("Journal Entry") if frappe.db.exists("DocType", "Journal Entry") else 0
		
		res = prepare_edgepay_payment_entry_draft("EPE-TEST-007")
		self.assertTrue(res["ok"])
		self.assertEqual(res["message"], "Draft Payment Entry created successfully.")
		
		# Check database records
		self.assertEqual(frappe.db.count("Payment Entry"), pe_count + 1)
		if frappe.db.exists("DocType", "Journal Entry"):
			self.assertEqual(frappe.db.count("Journal Entry"), je_count)
			
		# Check Payment Entry is draft (docstatus == 0)
		pe_doc = frappe.get_doc("Payment Entry", res["payment_entry"])
		self.assertEqual(pe_doc.docstatus, 0)
		self.assertEqual(pe_doc.reference_no, "test-prov-ref-ok")
		
		# Check evidence fields are updated
		ev = frappe.get_doc("RetailEdge EdgePay Payment Evidence", "EPE-TEST-007")
		self.assertEqual(ev.payment_entry, res["payment_entry"])
		self.assertEqual(ev.posting_status, "Draft Created")
		self.assertIsNotNone(ev.posting_prepared_on)
		self.assertEqual(ev.posting_prepared_by, "Administrator")

	def test_draft_preparation_is_idempotent(self):
		self.create_evidence("EPE-TEST-008", review_status="Reviewed", provider_ref="test-prov-ref-idemp")
		
		res1 = prepare_edgepay_payment_entry_draft("EPE-TEST-008")
		self.assertTrue(res1["ok"])
		pe_name1 = res1["payment_entry"]
		
		# Second run
		res2 = prepare_edgepay_payment_entry_draft("EPE-TEST-008")
		self.assertTrue(res2["ok"])
		self.assertEqual(res2["payment_entry"], pe_name1)
		self.assertIn("Existing draft", res2["message"])

	def test_unauthorized_roles_cannot_access_apis(self):
		self.create_evidence("EPE-TEST-009", review_status="Reviewed")
		
		# Test Guest
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api_get_preflight("EPE-TEST-009")
		with self.assertRaises(frappe.PermissionError):
			api_prepare_draft("EPE-TEST-009")
			
		# Test unauthorized user
		frappe.set_user("test-user-without-roles@example.com")
		with self.assertRaises(frappe.PermissionError):
			api_get_preflight("EPE-TEST-009")
		with self.assertRaises(frappe.PermissionError):
			api_prepare_draft("EPE-TEST-009")
			
		# Restore
		frappe.set_user("Administrator")
		res = api_get_preflight("EPE-TEST-009")
		self.assertTrue(res["ok"])

	def test_manual_status_marking(self):
		self.create_evidence("EPE-TEST-010", review_status="Reviewed")
		
		res_ready = mark_edgepay_evidence_posting_ready("EPE-TEST-010")
		self.assertTrue(res_ready["ok"])
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", "EPE-TEST-010", "posting_status"), "Ready")
		
		res_blocked = mark_edgepay_evidence_posting_blocked("EPE-TEST-010", reason="Blocked for manual verification")
		self.assertTrue(res_blocked["ok"])
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", "EPE-TEST-010", "posting_status"), "Blocked")
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", "EPE-TEST-010", "posting_preflight_message"), "Blocked for manual verification")

	def test_unreviewed_evidence_submission_blocked(self):
		self.create_evidence("EPE-SUB-001", review_status="Pending Review")
		res = get_edgepay_payment_entry_submission_preflight("EPE-SUB-001")
		self.assertFalse(res["ok"])
		self.assertIn("not Reviewed", res["message"])

	def test_evidence_without_draft_payment_entry_blocked(self):
		self.create_evidence("EPE-SUB-002", review_status="Reviewed")
		frappe.db.set_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-002", "posting_status", "Ready")
		res = get_edgepay_payment_entry_submission_preflight("EPE-SUB-002")
		self.assertFalse(res["ok"])
		self.assertIn("No linked Payment Entry", res["message"])

	def test_valid_submission_preflight_passes(self):
		self.create_evidence("EPE-SUB-003", review_status="Reviewed", provider_ref="prov-sub-3")
		prepare_edgepay_payment_entry_draft("EPE-SUB-003")
		
		res = get_edgepay_payment_entry_submission_preflight("EPE-SUB-003")
		self.assertTrue(res["ok"])
		self.assertEqual(res["message"], "Submission preflight passed.")

	def test_submission_amount_mismatch_blocks(self):
		self.create_evidence("EPE-SUB-004", review_status="Reviewed", provider_ref="prov-sub-4")
		prepare_edgepay_payment_entry_draft("EPE-SUB-004")
		
		# Artificially modify the evidence amount to trigger mismatch
		frappe.db.set_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-004", "amount", 2000.0)
		res = get_edgepay_payment_entry_submission_preflight("EPE-SUB-004")
		self.assertFalse(res["ok"])
		self.assertIn("amount", res["message"])

	def test_submission_currency_mismatch_blocks(self):
		self.create_evidence("EPE-SUB-005", review_status="Reviewed", provider_ref="prov-sub-5")
		prepare_edgepay_payment_entry_draft("EPE-SUB-005")
		
		# Artificially modify currency to trigger mismatch
		frappe.db.set_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-005", "currency", "USD")
		res = get_edgepay_payment_entry_submission_preflight("EPE-SUB-005")
		self.assertFalse(res["ok"])
		self.assertIn("Currency mismatch", res["message"])

	def test_submission_missing_source_document_blocks(self):
		self.create_evidence("EPE-SUB-006", review_status="Reviewed", provider_ref="prov-sub-6")
		frappe.db.set_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-006", "source_name", "SINV-RE-MISSING")
		
		# Create Payment Entry directly referencing the MISSING invoice
		pe = self.mock_get_payment_entry("Sales Invoice", "SINV-RE-MISSING")
		pe.reference_no = "prov-sub-6"
		pe.insert(ignore_permissions=True)
		
		frappe.db.set_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-006", "payment_entry", pe.name)
		frappe.db.set_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-006", "posting_status", "Ready")
		
		res = get_edgepay_payment_entry_submission_preflight("EPE-SUB-006")
		self.assertFalse(res["ok"])
		self.assertIn("does not exist", res["message"])

	def test_submission_already_submitted_is_idempotent(self):
		self.create_evidence("EPE-SUB-007", review_status="Reviewed", provider_ref="prov-sub-7")
		prepare_edgepay_payment_entry_draft("EPE-SUB-007")
		
		# Submit
		res = submit_edgepay_payment_entry("EPE-SUB-007")
		self.assertTrue(res["ok"])
		pe_name = res["payment_entry"]
		
		# Check docstatus is 1 (submitted) in the DB
		self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "docstatus"), 1)
		
		# Submit again
		res2 = submit_edgepay_payment_entry("EPE-SUB-007")
		self.assertTrue(res2["ok"])
		self.assertEqual(res2["payment_entry"], pe_name)
		self.assertIn("already submitted", res2["message"])

	def test_duplicate_submitted_provider_reference_blocks(self):
		self.create_evidence("EPE-SUB-008", review_status="Reviewed", provider_ref="prov-sub-dup-ref")
		prepare_edgepay_payment_entry_draft("EPE-SUB-008")
		
		# Create a duplicate submitted Payment Entry in the database after draft is prepared
		pe = self.mock_get_payment_entry("Sales Invoice", "SINV-RE-0001")
		pe.reference_no = "prov-sub-dup-ref"
		pe.insert(ignore_permissions=True)
		pe.docstatus = 1
		pe.db_update()
		
		frappe.db.commit()
		
		with self.assertRaises(frappe.ValidationError):
			submit_edgepay_payment_entry("EPE-SUB-008")
			
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-008", "posting_status"), "Blocked")

	def test_manual_submission_submits_draft(self):
		self.create_evidence("EPE-SUB-009", review_status="Reviewed", provider_ref="prov-sub-9")
		prepare_edgepay_payment_entry_draft("EPE-SUB-009")
		
		res = submit_edgepay_payment_entry("EPE-SUB-009")
		self.assertTrue(res["ok"])
		
		ev = frappe.get_doc("RetailEdge EdgePay Payment Evidence", "EPE-SUB-009")
		self.assertEqual(ev.posting_status, "Submitted")
		self.assertEqual(ev.submission_status, "Submitted")
		self.assertIsNotNone(ev.submitted_on)
		self.assertEqual(ev.submitted_by, "Administrator")

	def test_failed_submission_stores_redacted_error(self):
		self.create_evidence("EPE-SUB-010", review_status="Reviewed", provider_ref="prov-sub-10")
		prepare_edgepay_payment_entry_draft("EPE-SUB-010")
		frappe.db.commit()
		
		# Scenario A: Non-sensitive error should not be redacted
		self._mock_submit_failure = True
		self._mock_submit_failure_msg = "Database connection timed out"
		try:
			with self.assertRaises(frappe.ValidationError):
				submit_edgepay_payment_entry("EPE-SUB-010")
				
			ev = frappe.get_doc("RetailEdge EdgePay Payment Evidence", "EPE-SUB-010")
			self.assertEqual(ev.posting_status, "Failed")
			self.assertEqual(ev.submission_status, "Failed")
			self.assertIn("Database connection timed out", ev.submission_message)
		finally:
			self._mock_submit_failure = False

		# Scenario B: Sensitive error must be redacted
		self.create_evidence("EPE-SUB-010B", review_status="Reviewed", provider_ref="prov-sub-10b")
		prepare_edgepay_payment_entry_draft("EPE-SUB-010B")
		frappe.db.commit()
		
		self._mock_submit_failure = True
		self._mock_submit_failure_msg = "Mock submit failure with secret key token-123"
		try:
			with self.assertRaises(frappe.ValidationError):
				submit_edgepay_payment_entry("EPE-SUB-010B")
				
			ev = frappe.get_doc("RetailEdge EdgePay Payment Evidence", "EPE-SUB-010B")
			self.assertEqual(ev.posting_status, "Failed")
			self.assertEqual(ev.submission_status, "Failed")
			self.assertNotIn("secret key", ev.submission_message)
			self.assertNotIn("token-123", ev.submission_message)
			self.assertEqual(ev.submission_message, "Error occurred during Payment Entry submission. Details redacted for security.")
		finally:
			self._mock_submit_failure = False

	def test_submission_blocked_marking(self):
		self.create_evidence("EPE-SUB-011", review_status="Reviewed")
		
		res = mark_edgepay_evidence_submission_blocked("EPE-SUB-011", reason="Manual hold")
		self.assertTrue(res["ok"])
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-011", "posting_status"), "Blocked")
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-011", "submission_status"), "Blocked")
		self.assertEqual(frappe.db.get_value("RetailEdge EdgePay Payment Evidence", "EPE-SUB-011", "submission_message"), "Manual hold")

	def test_production_service_does_not_set_ignore_flags(self):
		self.create_evidence("EPE-TEST-012", review_status="Reviewed")
		
		captured_flags = {}
		captured_kwargs = {}
		
		pe = self.mock_get_payment_entry("Sales Invoice", "SINV-RE-0001")
		pe.flags.ignore_validate = False
		
		original_insert = pe.insert
		def mock_insert(*args, **kwargs):
			captured_flags.update(pe.flags)
			captured_kwargs.update(kwargs)
			pe.flags.ignore_validate = True
			return original_insert(ignore_permissions=True)
			
		pe.insert = mock_insert
		
		with patch("retailedge.services.edgepay_payment_posting.get_payment_entry", return_value=pe):
			prepare_edgepay_payment_entry_draft("EPE-TEST-012")
			
		self.assertFalse(captured_flags.get("ignore_validate"))
		self.assertFalse(captured_flags.get("ignore_mandatory"))
		self.assertFalse(captured_flags.get("ignore_links"))
		self.assertFalse(captured_flags.get("ignore_permissions"))
		self.assertFalse(captured_kwargs.get("ignore_permissions"))

