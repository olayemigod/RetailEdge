from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import party_transaction_context


ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "public/js/retailedge_business_hub/PartyBusinessContext.vue"
QUICK_SALE = ROOT / "public/js/retailedge_business_hub/SimpleSalesInvoiceDialog.vue"
QUICK_PURCHASE = ROOT / "public/js/retailedge_business_hub/SimplePurchaseInvoiceDialog.vue"
MAKE_SALE = ROOT / "public/js/make_sale/MakeSale.vue"
RECORD_PURCHASE = ROOT / "public/js/record_purchase/RecordPurchase.vue"


def test_party_transaction_context_is_permission_and_branch_aware():
    source = inspect.getsource(party_transaction_context)
    assert 'frappe.has_permission(config["doctype"], "read")' in source
    assert '_assert_named_read("Company", company)' in source
    assert '_assert_named_read(config["party_type"], party)' in source
    assert "get_operational_branch_scope" in source
    assert "validate_operating_branch" in source
    assert "Choose an Operating Branch before loading party transaction context." in source
    assert "ignore_permissions" not in source
    assert "frappe.get_all" not in source
    assert "frappe.db.commit" not in source


def test_party_context_uses_submitted_invoice_truth_and_bounded_multicurrency_open_rows():
    source = inspect.getsource(party_transaction_context)
    assert '"docstatus": 1' in source
    assert '"Sales Invoice"' in source
    assert '"Purchase Invoice"' in source
    assert '{"SUM": "base_net_total", "as": "total_value"}' in source
    assert '{"SUM": "outstanding_amount", "as": "current_balance"}' in source
    assert "MAX_OPEN_DOCUMENT_ROWS = 2000" in source
    assert "limit_page_length=MAX_OPEN_DOCUMENT_ROWS + 1" in source
    assert '"conversion_rate"' in source
    assert '"source_of_truth": config["source"]' in source
    assert '{"COUNT": "*", "as": "document_count"}' in source
    assert '{"MAX": "posting_date", "as": "last_transaction_date"}' in source
    assert "count(name) as document_count" not in source
    assert "sum(base_net_total) as total_value" not in source


def test_context_card_refreshes_on_party_company_and_branch_changes():
    source = CARD.read_text(encoding="utf-8")
    assert "party() { this.loadContext(); }" in source
    assert "company() { this.loadContext(); }" in source
    assert "branch() { this.loadContext(); }" in source
    assert "requestToken" in source
    assert "retailedge.party_transaction_context.get_party_transaction_context" in source
    for label in ("Current Balance", "Overdue", "Total Sales Value", "Total Purchase Value"):
        assert label in inspect.getsource(party_transaction_context)


def test_sales_and_purchase_entry_surfaces_share_same_party_context_component():
    for path, party_type, field in (
        (QUICK_SALE, "Customer", "values.customer"),
        (MAKE_SALE, "Customer", "values.customer"),
        (QUICK_PURCHASE, "Supplier", "values.supplier"),
        (RECORD_PURCHASE, "Supplier", "values.supplier"),
    ):
        source = path.read_text(encoding="utf-8")
        assert "PartyBusinessContext" in source
        assert f'partyType="{party_type}"' in source
        assert f':party="{field}"' in source
        assert ':company="values.company"' in source
        assert ':branch="values.branch"' in source


def test_party_context_does_not_create_or_modify_accounting_documents():
    source = inspect.getsource(party_transaction_context)
    for forbidden in (
        "frappe.new_doc",
        ".insert(",
        ".save(",
        ".submit(",
        "frappe.db.set_value",
        "frappe.db.sql",
    ):
        assert forbidden not in source
