from __future__ import annotations

import frappe


GOVERNED_PAGE_ROLES = {
    "retailedge-business-hub": (
        "System Manager",
        "Accounts Manager",
        "Accounts User",
        "Stock Manager",
        "Stock User",
        "RetailEdgeManager",
        "RetailEdgeBranchManager",
        "RetailEdgeCashier",
        "Sales Manager",
        "Sales User",
        "Purchase Manager",
        "Purchase User",
    ),
    "payment-management": (
        "System Manager",
        "Accounts User",
        "Accounts Manager",
    ),
}


def execute() -> None:
    """Reconcile bounded core Page roles after older sites preserved stale child rows."""
    if not frappe.db.exists("DocType", "Page"):
        return

    for page_name, expected_roles in GOVERNED_PAGE_ROLES.items():
        if not frappe.db.exists("Page", page_name):
            continue

        actual_roles = tuple(
            frappe.get_all(
                "Has Role",
                filters={
                    "parenttype": "Page",
                    "parentfield": "roles",
                    "parent": page_name,
                },
                pluck="role",
                order_by="idx asc",
            )
        )
        if actual_roles == expected_roles:
            continue

        frappe.db.delete(
            "Has Role",
            {
                "parenttype": "Page",
                "parentfield": "roles",
                "parent": page_name,
            },
        )
        for idx, role in enumerate(expected_roles, start=1):
            if not frappe.db.exists("Role", role):
                continue
            frappe.get_doc(
                {
                    "doctype": "Has Role",
                    "parent": page_name,
                    "parenttype": "Page",
                    "parentfield": "roles",
                    "role": role,
                    "idx": idx,
                }
            ).db_insert()
        frappe.get_doc("Page", page_name).clear_cache()
