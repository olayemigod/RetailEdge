from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

# R1-R4 service modules are allowed to create/update draft or RetailEdge control
# state, but must not silently complete ERPNext accounting/stock workflows.
SERVICE_MODULES = (
    "guided_sales_invoice.py",
    "guided_purchase_invoice.py",
    "guided_payment.py",
    "guided_stock_transfer.py",
    "guided_stock_adjustment.py",
    "guided_cash_transfer.py",
    "guided_cashier_expense.py",
    "action_center.py",
    "action_follow_up.py",
    "sales_reporting.py",
    "purchase_reporting.py",
    "stock_position.py",
    "cash_movement.py",
    "expense_register.py",
    "expense_review.py",
    "customer_receivables.py",
    "supplier_payables.py",
    "owner_dashboard.py",
    "sales_dashboard.py",
    "money_dashboard.py",
    "expense_dashboard.py",
)

FORBIDDEN_TRANSACTION_SHORTCUTS = (
    ".submit(",
    "apply_workflow(",
    "ignore_permissions=True",
    "ignore_permissions = True",
    "frappe.db.commit(",
    "frappe.db.rollback(",
)


def test_r1_r4_service_modules_do_not_complete_or_bypass_transactions():
    for relative_path in SERVICE_MODULES:
        path = APP_ROOT / relative_path
        assert path.exists(), f"Expected R1-R4 service module is missing: {relative_path}"
        source = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_TRANSACTION_SHORTCUTS:
            assert forbidden not in source, (
                f"{relative_path} contains forbidden transaction shortcut {forbidden!r}; "
                "R1-R4 must preserve native ERPNext submission/workflow/permission boundaries."
            )


def test_reporting_and_dashboard_services_are_read_only_at_source_level():
    read_only_modules = (
        "sales_reporting.py",
        "purchase_reporting.py",
        "stock_position.py",
        "cash_movement.py",
        "expense_register.py",
        "customer_receivables.py",
        "supplier_payables.py",
        "owner_dashboard.py",
        "sales_dashboard.py",
        "money_dashboard.py",
        "expense_dashboard.py",
        "action_center.py",
    )
    write_markers = (
        ".insert(",
        ".save(",
        ".delete(",
        ".cancel(",
        "frappe.db.set_value(",
        "frappe.db.delete(",
    )
    for relative_path in read_only_modules:
        source = (APP_ROOT / relative_path).read_text(encoding="utf-8")
        for marker in write_markers:
            assert marker not in source, (
                f"Read-only R1-R4 service {relative_path} contains write marker {marker!r}."
            )
