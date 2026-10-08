from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    ROOT / "standard_delivery_completion.py",
    ROOT / "standard_stock_completion.py",
    ROOT / "standard_sales_invoice_completion.py",
    ROOT / "standard_purchase_invoice_completion.py",
)
FORBIDDEN = ("ERPNext", "EdgeSuite", "Frappe", "Native Desk")


def _translated_messages(source: str) -> list[str]:
    tree = ast.parse(source)
    messages = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" and node.args:
            value = node.args[0]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                messages.append(value.value)
    return messages


def test_standard_completion_user_messages_hide_platform_implementation_names():
    for path in SERVICES:
        source = path.read_text(encoding="utf-8")
        leaked = [message for message in _translated_messages(source) if any(term in message for term in FORBIDDEN)]
        assert not leaked, f"{path.name} leaked platform wording: {leaked}"


def test_standard_completion_safety_and_native_authority_contracts_remain_intact():
    delivery, stock, sales, purchase = [path.read_text(encoding="utf-8") for path in SERVICES]
    for source in (delivery, stock, sales, purchase):
        assert "get_workflow_readiness" in source
        assert "apply_document_workflow_action(" in source
        assert "doc.submit()" in source
        assert "frappe.has_permission" in source
    assert "_validate_source_and_stock_context" in delivery
    assert "_validate_warehouse_access" in stock
    assert "erpnext_make_sales_return" in sales
    assert "_validate_stock_context" in sales
    assert "_completion_source_context" in purchase
    assert "_validate_stock_context" in purchase
    assert '"source_of_truth": "ERPNext"' in delivery
    assert '"source_of_truth": f"ERPNext {doc.doctype}"' in stock
    assert '"source_of_truth": "ERPNext"' in sales
    assert '"source_of_truth": "ERPNext Purchase Invoice"' in purchase
