from __future__ import annotations

import frappe
from frappe import _
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
    "mask",
)



def _permission_signatures(doctype: str, role: str) -> dict[tuple[str, int, int], list[tuple[int, ...]]]:
    """Compare the complete raw grants, including rows without a counterpart.

    DocPerm and Custom DocPerm remain separate: Frappe's custom permission
    overrides can make a superficially similar pair behave differently.
    Duplicate rows are intentionally preserved in the comparison.
    """
    rows = frappe.get_all(
        doctype,
        filters={"role": role},
        fields=["parent", "permlevel", "if_owner", *PERMISSION_FIELDS],
    )
    signatures: dict[tuple[str, int, int], list[tuple[int, ...]]] = {}
    for row in rows:
        key = (
            str(row.get("parent") or ""),
            int(row.get("permlevel") or 0),
            int(row.get("if_owner") or 0),
        )
        grant = tuple(int(row.get(fieldname) or 0) for fieldname in PERMISSION_FIELDS)
        signatures.setdefault(key, []).append(grant)
    return {key: sorted(grants) for key, grants in signatures.items()}


def _assert_permission_equivalence_before_merge() -> None:
    """Fail closed across ALL role pairs before the first role is renamed.

    Unioning grants from two different merchant-managed roles would expand the
    authority of canonical-only users. Even a non-overlapping permission row is
    consequential, as Frappe rewrites Role links when merging Role documents.
    """
    differences: list[str] = []
    for legacy, canonical in LEGACY_TO_CANONICAL.items():
        if not (frappe.db.exists("Role", legacy) and frappe.db.exists("Role", canonical)):
            continue
        for doctype in ("DocPerm", "Custom DocPerm"):
            legacy_rows = _permission_signatures(doctype, legacy)
            canonical_rows = _permission_signatures(doctype, canonical)
            for scope in sorted(set(legacy_rows) | set(canonical_rows)):
                if legacy_rows.get(scope, []) != canonical_rows.get(scope, []):
                    parent, permlevel, if_owner = scope
                    differences.append(
                        f"{legacy} / {canonical}: {doctype} {parent} "
                        f"(level {permlevel}, if_owner {if_owner})"
                    )
    if differences:
        details = "; ".join(differences[:12])
        remaining = f" (+{len(differences) - 12} more)" if len(differences) > 12 else ""
        frappe.throw(
            _(
                "RetailEdge role consolidation cannot proceed because legacy and "
                "canonical permissions differ. Review these grants in Role Permission "
                "Manager or reconcile the conflicting permission rows explicitly "
                "before retrying migration: {0}{1}"
            ).format(details, remaining),
            frappe.ValidationError,
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
        # The global preflight confirmed these rows have identical grants.
        # Delete only the duplicate legacy row; never union privileges.
        frappe.db.delete(doctype, {"name": row.name})


def execute() -> None:
    """Merge obsolete spaced RetailEdge roles into one canonical role per persona."""
    _assert_permission_equivalence_before_merge()
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
