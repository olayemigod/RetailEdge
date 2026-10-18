from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

from retailedge import party_transaction_context


ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "public/js/retailedge_business_hub/PartyBusinessContext.vue"
QUICK_SALE = ROOT / "public/js/retailedge_business_hub/SimpleSalesInvoiceDialog.vue"
QUICK_PURCHASE = ROOT / "public/js/retailedge_business_hub/SimplePurchaseInvoiceDialog.vue"
MAKE_SALE = ROOT / "public/js/make_sale/MakeSale.vue"
RECORD_PURCHASE = ROOT / "public/js/record_purchase/RecordPurchase.vue"


def test_party_transaction_context_preserves_permissions_and_supplier_branch_scope():
    source = inspect.getsource(party_transaction_context)
    assert 'frappe.has_permission(config["doctype"], "read")' in source
    assert '_assert_named_read("Company", company)' in source
    assert '_assert_named_read(config["party_type"], party)' in source
    assert "get_operational_branch_scope" in source
    assert "validate_operating_branch" in source
    assert "Choose an Operating Branch before loading party transaction context." in source
    assert 'if config["party_type"] == "Supplier":' in source
    assert "ignore_permissions" not in source
    assert "frappe.get_all" not in source
    assert "frappe.db.commit" not in source


def test_customer_context_is_company_wide_not_retailedge_branch_scoped():
    source = inspect.getsource(party_transaction_context)
    assert 'if config["party_type"] == "Supplier":' in source
    assert 'else:\n\t\tbranch = ""\n\t\tbranch_field = None' in source
    assert '"scope": "Company" if config["party_type"] == "Customer" else "Branch"' in source
    assert "Company-wide submitted ERPNext Sales Invoices" in source

    card = CARD.read_text(encoding="utf-8")
    assert 'branch() { if (this.partyType === "Supplier") this.loadContext(); }' in card
    assert 'branch: this.partyType === "Supplier" ? (this.branch || "") : ""' in card


def test_customer_context_filters_company_and_customer_but_not_branch():
    with (
        patch.object(party_transaction_context, "_assert_named_read"),
        patch.object(party_transaction_context.frappe, "has_permission", return_value=True),
        patch.object(party_transaction_context, "_resolve_scope") as resolve_scope,
        patch.object(
            party_transaction_context,
            "_summary",
            return_value={"document_count": 3, "total_value": 90000, "last_transaction_date": "2026-10-15"},
        ) as summary,
        patch.object(
            party_transaction_context,
            "_outstanding_summary",
            return_value={"current_balance": 25000, "overdue_balance": 10000, "open_document_count": 2, "partial": False},
        ) as outstanding,
        patch.object(party_transaction_context, "_company_currency", return_value="NGN"),
    ):
        result = party_transaction_context.get_party_transaction_context(
            "Customer",
            "CUST-001",
            "RetailEdge Consulting",
            "Ketu",
        )

    resolve_scope.assert_not_called()
    expected_filters = {
        "docstatus": 1,
        "company": "RetailEdge Consulting",
        "customer": "CUST-001",
    }
    summary.assert_called_once_with(expected_filters, "Sales Invoice")
    outstanding.assert_called_once_with(expected_filters, "Sales Invoice")
    assert result["branch"] == ""
    assert result["scope"] == "Company"
    assert result["metrics"][0]["value"] == 25000


def test_supplier_context_keeps_branch_filter():
    with (
        patch.object(party_transaction_context, "_assert_named_read"),
        patch.object(party_transaction_context.frappe, "has_permission", return_value=True),
        patch.object(
            party_transaction_context,
            "_resolve_scope",
            return_value=("Ketu", "retailedge_branch"),
        ) as resolve_scope,
        patch.object(
            party_transaction_context,
            "_summary",
            return_value={"document_count": 1, "total_value": 20000, "last_transaction_date": "2026-10-15"},
        ) as summary,
        patch.object(
            party_transaction_context,
            "_outstanding_summary",
            return_value={"current_balance": 5000, "overdue_balance": 0, "open_document_count": 1, "partial": False},
        ),
        patch.object(party_transaction_context, "_company_currency", return_value="NGN"),
    ):
        result = party_transaction_context.get_party_transaction_context(
            "Supplier",
            "SUP-001",
            "RetailEdge Consulting",
            "Ketu",
        )

    resolve_scope.assert_called_once_with(
        doctype="Purchase Invoice",
        company="RetailEdge Consulting",
        branch="Ketu",
    )
    summary.assert_called_once_with(
        {
            "docstatus": 1,
            "company": "RetailEdge Consulting",
            "supplier": "SUP-001",
            "retailedge_branch": "Ketu",
        },
        "Purchase Invoice",
    )
    assert result["branch"] == "Ketu"
    assert result["scope"] == "Branch"


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


def test_context_card_refreshes_on_party_company_and_supplier_branch_changes():
    source = CARD.read_text(encoding="utf-8")
    assert "party() { this.loadContext(); }" in source
    assert "company() { this.loadContext(); }" in source
    assert 'branch() { if (this.partyType === "Supplier") this.loadContext(); }' in source
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
