from __future__ import annotations

import frappe
from frappe import _
from frappe.core.doctype.permission_type.permission_type import get_doctype_ptype_map
from frappe.model.rename_doc import get_link_fields, rename_doc

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

ROLE_POLICY_FIELDS = ("disabled", "desk_access", "two_factor_auth", "restrict_to_domain")


def _permission_fields() -> tuple[str, ...]:
    """Include Frappe v16 custom Permission Type columns in both permission tables."""
    custom = {
        perm
        for permission_types in get_doctype_ptype_map().values()
        for perm in permission_types
    }
    return tuple(sorted(set(PERMISSION_FIELDS) | custom))


def _permission_signatures(
    doctype: str, role: str, permission_fields: tuple[str, ...]
) -> dict[tuple[str, int, int], list[tuple[int, ...]]]:
    """Compare the complete raw grants, including rows without a counterpart.

    DocPerm and Custom DocPerm remain separate: Frappe's custom permission
    overrides can make a superficially similar pair behave differently.
    Duplicate rows are intentionally preserved in the comparison.
    """
    rows = frappe.get_all(
        doctype,
        filters={"role": role},
        fields=["parent", "permlevel", "if_owner", *permission_fields],
    )
    signatures: dict[tuple[str, int, int], list[tuple[int, ...]]] = {}
    for row in rows:
        key = (
            str(row.get("parent") or ""),
            int(row.get("permlevel") or 0),
            int(row.get("if_owner") or 0),
        )
        grant = tuple(int(row.get(fieldname) or 0) for fieldname in permission_fields)
        signatures.setdefault(key, []).append(grant)
    return {key: sorted(grants) for key, grants in signatures.items()}



def get_role_permission_conflict_report() -> dict:
    """Read-only CLI diagnostic. Does not expose a whitelisted API or mutate Roles.

    Use with bench execute on an isolated site, before authorizing any Role
    reconciliation. The report includes all conflicting native and custom
    permission flags; zero-valued flags are omitted for readability.
    """
    permission_fields = _permission_fields()
    conflicts: list[dict] = []
    for legacy, canonical in LEGACY_TO_CANONICAL.items():
        if not (frappe.db.exists("Role", legacy) and frappe.db.exists("Role", canonical)):
            continue
        for doctype in ("DocPerm", "Custom DocPerm"):
            left = _permission_signatures(doctype, legacy, permission_fields)
            right = _permission_signatures(doctype, canonical, permission_fields)
            for scope in sorted(set(left) | set(right)):
                legacy_grants = left.get(scope, [])
                canonical_grants = right.get(scope, [])
                if legacy_grants == canonical_grants:
                    continue
                parent, permlevel, if_owner = scope

                def active_flags(grants):
                    return [
                        {
                            field: value
                            for field, value in zip(
                                permission_fields, grant, strict=True
                            )
                            if value
                        }
                        for grant in grants
                    ]

                conflicts.append({
                    "legacy_role": legacy,
                    "canonical_role": canonical,
                    "permission_table": doctype,
                    "document_type": parent,
                    "permission_level": permlevel,
                    "if_owner": if_owner,
                    "legacy_grants": active_flags(legacy_grants),
                    "canonical_grants": active_flags(canonical_grants),
                })
    return {
        "read_only": True,
        "conflict_count": len(conflicts),
        "permission_fields_checked": list(permission_fields),
        "conflicts": conflicts,
    }


def _assert_permission_equivalence_before_merge() -> None:
    """Fail closed across ALL role pairs before the first role is renamed.

    Unioning grants from two different merchant-managed roles would expand the
    authority of canonical-only users. Even a non-overlapping permission row is
    consequential, as Frappe rewrites Role links when merging Role documents.
    """
    differences: list[str] = []
    permission_fields = _permission_fields()
    for legacy, canonical in LEGACY_TO_CANONICAL.items():
        if not (frappe.db.exists("Role", legacy) and frappe.db.exists("Role", canonical)):
            continue
        for doctype in ("DocPerm", "Custom DocPerm"):
            legacy_rows = _permission_signatures(doctype, legacy, permission_fields)
            canonical_rows = _permission_signatures(doctype, canonical, permission_fields)
            for scope in sorted(set(legacy_rows) | set(canonical_rows)):
                if legacy_rows.get(scope, []) != canonical_rows.get(scope, []):
                    parent, permlevel, if_owner = scope
                    differences.append(
                        f"{legacy} / {canonical}: {doctype} {parent} "
                        f"(level {permlevel}, if_owner {if_owner})"
                    )
    if differences:
        # Do not hide affected scopes: administrators must review them all.
        details = "; ".join(differences)
        frappe.throw(
            _(
                "RetailEdge role consolidation cannot proceed because legacy and "
                "canonical permissions differ. Review these grants in Role Permission "
                "Manager or reconcile the conflicting permission rows explicitly "
                "before retrying migration: {0}"
            ).format(details),
            frappe.ValidationError,
        )




def _assert_role_policy_equivalence_before_merge() -> None:
    """Retain legacy security policy unless the destination role matches it.

    Frappe's Role merge retains the canonical Role document, so a different
    legacy 2FA/domain/disabled/Desk-access policy would otherwise be lost.
    """
    rows = frappe.get_all(
        "Role", filters={"name": ["in", list(LEGACY_TO_CANONICAL) + list(LEGACY_TO_CANONICAL.values())]},
        fields=["name", *ROLE_POLICY_FIELDS], limit_page_length=0,
    )
    by_name = {row.get("name"): row for row in rows}
    differences: list[str] = []
    for legacy, canonical in LEGACY_TO_CANONICAL.items():
        if legacy not in by_name or canonical not in by_name:
            continue
        for fieldname in ROLE_POLICY_FIELDS:
            if str(by_name[legacy].get(fieldname) or "") != str(by_name[canonical].get(fieldname) or ""):
                differences.append(f"{legacy} / {canonical}: Role.{fieldname}")
    if differences:
        frappe.throw(
            _(
                "RetailEdge role consolidation would change Role security policy. "
                "Reconcile these settings before merging: {0}"
            ).format("; ".join(differences)),
            frappe.ValidationError,
        )


def _assert_authorization_link_safety_before_merge() -> None:
    """Reject Role-link remaps that could widen page, profile or approval access.

    Frappe rename_doc updates every Link-to-Role value, not only DocPerm.
    Legacy-only reviewer/approver settings would grant the same authority to
    existing canonical-only users after rename. Require explicit reconciliation.
    """
    differences: list[str] = []
    role_links = get_link_fields("Role")
    permission_and_assignment_tables = {"Has Role", "DocPerm", "Custom DocPerm"}

    for legacy, canonical in LEGACY_TO_CANONICAL.items():
        if not (frappe.db.exists("Role", legacy) and frappe.db.exists("Role", canonical)):
            continue

        # User/Role Profile/Page/Report assignments also carry authorization.
        # An existing matching canonical assignment is safe; legacy-only ones
        # are not silently converted to grants for a wider population.
        old_assignments = frappe.get_all(
            "Has Role",
            filters={"role": legacy},
            fields=["parent", "parenttype", "parentfield"],
        )
        for row in old_assignments:
            scope = {
                "role": canonical,
                "parent": row.get("parent"),
                "parenttype": row.get("parenttype"),
                "parentfield": row.get("parentfield"),
            }
            if not frappe.db.exists("Has Role", scope):
                differences.append(
                    f"{legacy} / {canonical}: Has Role "
                    f"{row.get('parenttype')} {row.get('parent')}"
                )

        for link in role_links:
            doctype = str(link.get("parent") or "").strip()
            fieldname = str(link.get("fieldname") or "").strip()
            if not doctype or not fieldname or doctype in permission_and_assignment_tables:
                continue
            if link.get("issingle"):
                configured_role = frappe.db.get_single_value(doctype, fieldname)
                has_legacy = configured_role == legacy
            else:
                has_legacy = bool(frappe.db.exists(doctype, {fieldname: legacy}))
            if has_legacy:
                differences.append(
                    f"{legacy} / {canonical}: {doctype}.{fieldname}"
                )
    if differences:
        # Do not hide affected scopes: administrators must review them all.
        details = "; ".join(differences)
        frappe.throw(
            _(
                "RetailEdge role consolidation cannot proceed because Role links "
                "or authorization assignments require explicit reconciliation. "
                "Review these reviewer, approver, Page, profile or User settings "
                "before retrying migration: {0}"
            ).format(details),
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
    """Keep canonical permissions authoritative during the approved Role merge."""
    if not frappe.db.exists("DocType", doctype):
        return
    frappe.db.delete(doctype, {"role": legacy})


def execute() -> None:
    """Apply the approved canonical permission policy, then merge roles.

    Frappe v16 synchronizes DocPerm and Page metadata during migration.
    Canonical roles are the explicit permission source of truth. Other Role
    policy and authorization-link differences remain hard blockers.
    """
    conflict_report = get_role_permission_conflict_report()
    _assert_role_policy_equivalence_before_merge()
    _assert_authorization_link_safety_before_merge()
    if conflict_report["conflict_count"]:
        frappe.log_error(
            title="RetailEdge canonical role permission reconciliation",
            message=frappe.as_json(conflict_report),
        )

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
