# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch
from retailedge.services.edgepay_payment_posting import (
	get_edgepay_evidence_posting_preflight,
	prepare_edgepay_payment_entry_draft,
	mark_edgepay_evidence_posting_ready,
	mark_edgepay_evidence_posting_blocked
)
from retailedge.api import (
	get_edgepay_evidence_posting_preflight as api_get_preflight,
	prepare_edgepay_payment_entry_draft as api_prepare_draft
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
				"currency": "NGN",
				"docstatus": 1
			})
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
