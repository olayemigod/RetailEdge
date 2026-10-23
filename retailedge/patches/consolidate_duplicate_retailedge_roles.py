from __future__ import annotations

import frappe
from frappe.model.rename_doc import rename_doc


LEGACY_TO_CANONICAL = {
    "RetailEdge Cashier": "RetailEdgeCashier",
    "RetailEdge Manager": "RetailEdgeManager",
    "RetailEdge Branch Manager": "RetailEdgeBranchManager",
    "RetailEdge Auditor": "RetailEdgeAuditor",
}

PERMISSION_FIELDS = (
    "read",
    "write",
    "create",
    "submit",
    "cancel",
    "delete",
    "amend",
    "report",
    "export",
    "import",
    "share",
    "print",
    "email",
    "select",
)


def _merge_duplicate_has_role_rows(legacy: str, canonical: str) -> None:
    rows = frappe.get_all(
        "Has Role",
        filters={"role": legacy},
        fields=["name", "parent", "parenttype", "parentfield"],
    )
    for row in rows:
        canonical_name = frappe.db.get_value(
            "Has Role",
            {
                "role": canonical,
                "parent": row.parent,
                "parenttype": row.parenttype,
                "parentfield": row.parentfield,
            },
            "name",
        )
        if canonical_name:
            frappe.db.delete("Has Role", {"name": row.name})


def _merge_duplicate_permission_rows(doctype: str, legacy: str, canonical: str) -> None:
    if not frappe.db.exists("DocType", doctype):
        return
    rows = frappe.get_all(
        doctype,
        filters={"role": legacy},
        fields=["name", "parent", "permlevel", "if_owner", *PERMISSION_FIELDS],
    )
    for row in rows:
        canonical_name = frappe.db.get_value(
            doctype,
            {
                "role": canonical,
                "parent": row.parent,
                "permlevel": row.permlevel,
                "if_owner": row.if_owner,
            },
            "name",
        )
        if not canonical_name:
            continue
        canonical_row = frappe.get_doc(doctype, canonical_name)
        changed = False
        for fieldname in PERMISSION_FIELDS:
            merged = max(int(canonical_row.get(fieldname) or 0), int(row.get(fieldname) or 0))
            if int(canonical_row.get(fieldname) or 0) != merged:
                canonical_row.set(fieldname, merged)
                changed = True
        if changed:
            canonical_row.db_update()
        frappe.db.delete(doctype, {"name": row.name})


def execute() -> None:
    """Merge obsolete spaced RetailEdge roles into one canonical role per persona."""
    for legacy, canonical in LEGACY_TO_CANONICAL.items():
        if not frappe.db.exists("Role", legacy):
            continue
        if not frappe.db.exists("Role", canonical):
            rename_doc("Role", legacy, canonical, force=True, ignore_permissions=True)
            continue

        _merge_duplicate_has_role_rows(legacy, canonical)
        _merge_duplicate_permission_rows("DocPerm", legacy, canonical)
        _merge_duplicate_permission_rows("Custom DocPerm", legacy, canonical)

        rename_doc(
            "Role",
            legacy,
            canonical,
            merge=True,
            force=True,
            ignore_permissions=True,
        )

    frappe.clear_cache()
