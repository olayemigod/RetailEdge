from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import retailedge.master_experience as master


ROOT = Path(__file__).resolve().parents[1]
PAYMENT_MANAGEMENT = ROOT / "public" / "js" / "payment_management" / "PaymentManagement.vue"
PURCHASE_REPORT = ROOT / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _method_source(source: str, name: str, next_name: str) -> str:
	start = source.index(f"\t\t{name}(")
	end = source.index(f"\t\t{next_name}(", start + 1)
	return source[start:end]


def test_payment_management_contains_native_payment_entry_fallback_for_edgesuite_only_users():
	page = _read(PAYMENT_MANAGEMENT)
	assert "canUseNativeDesk: false" in page
	assert "retailedge.master_experience.get_master_retailedge_business_hub_context" in page
	assert "this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);" in page
	assert 'v-if="canUseNativeDesk"' in page

	open_list = _method_source(page, "openPaymentEntries", "openPayment")
	open_payment = _method_source(page, "openPayment", "openInvoice")
	assert "if (!this.canUseNativeDesk) return" in open_list
	assert 'frappe.set_route("List", "Payment Entry")' in open_list
	assert "if (!this.canUseNativeDesk) return" in open_payment
	assert 'frappe.set_route("Form", "Payment Entry", name)' in open_payment


def test_customer_standard_review_stays_edgesuite_owned_while_native_review_is_explicit():
	page = _read(PAYMENT_MANAGEMENT)
	assert "Draft Payments Awaiting Submission" in page
	assert "reviewPaymentDraft(row.payment_entry)" in page
	assert "submit_standard_customer_payment" in page
	assert "expected_payment_entry_modified" in page
	assert "Open in ERPNext" in page
	assert 'v-if="canUseNativeDesk"' in page

	submit = _method_source(page, "submitPaymentDraft", "clearDraftState")
	assert 'frappe.set_route("Form", "Payment Entry"' not in submit


def test_supplier_payables_does_not_force_native_payment_entry_after_standard_handoff():
	page = _read(PURCHASE_REPORT)
	assert "canUseNativeDesk: false" in page
	assert "retailedge.master_experience.get_master_retailedge_business_hub_context" in page
	assert "this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);" in page
	assert 'intent="pay-supplier"' in page

	saved = _method_source(page, "async handleSupplierPaymentSaved", "openNativePayment")
	assert "await this.fetchData()" in saved
	assert 'frappe.set_route("Form", "Payment Entry"' not in saved

	native = _method_source(page, "openNativePayment", "openReportCell")
	assert "if (!this.canUseNativeDesk) return" in native
	assert 'frappe.new_doc("Payment Entry")' in native


def test_f3f4_keeps_native_payment_peer_until_generic_history_revisit_is_edgesuite_owned():
	groups = deepcopy(master.NAVIGATION_GROUPS)
	with (
		patch.object(master, "_can_open_page", return_value=True),
		patch.object(master, "_can_open_report", return_value=True),
	):
		promoted = master._promote_payment_management(groups, roles={"Accounts User"})

	money = next(group for group in promoted if group.get("key") == "money")
	items = money.get("items") or []
	payment_management_index = next(
		index for index, item in enumerate(items)
		if item.get("target_type") == "Page" and item.get("target") == "payment-management"
	)
	payment_entry_index = next(
		index for index, item in enumerate(items)
		if item.get("target_type") == "DocType" and item.get("target") == "Payment Entry"
	)
	assert payment_management_index < payment_entry_index
	assert any(item.get("target_type") == "DocType" and item.get("target") == "Payment Entry" for item in items)
	assert any(item.get("target_type") == "DocType" and item.get("target") == "Payment Reconciliation" for item in items)


def test_f3f4_changes_no_payment_posting_authority():
	for filename in (
		"standard_customer_payment_submit.py",
		"standard_supplier_payment_submit.py",
	):
		source = _read(ROOT / filename)
		assert "doc.submit()" in source
		assert "frappe.db.commit" not in source
		assert "db_set(" not in source
