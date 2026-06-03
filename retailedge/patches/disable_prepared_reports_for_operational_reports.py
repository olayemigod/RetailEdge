from __future__ import annotations

import frappe


OPERATIONAL_REPORTS = (
    "RetailEdge Bank Transaction Matching",
    "RetailEdge Unmatched Bank Transactions",
    "RetailEdge Unmatched Bank Payment Events",
    "RetailEdge Bank Match Reconciliation Readiness",
    "RetailEdge Reconciliation Handoff",
    "RetailEdge Branch Performance Summary",
    "RetailEdge Invoice Payment Audit",
    "RetailEdge Cashier Expense Review",
    "RetailEdge Cash Shift Verification",
    "RetailEdge Daily Sales Audit Register",
    "POS Closing Variance vs Expenses",
)


def execute():
    for report_name in OPERATIONAL_REPORTS:
        if frappe.db.exists("Report", report_name):
            frappe.db.set_value("Report", report_name, "prepared_report", 0, update_modified=False)
