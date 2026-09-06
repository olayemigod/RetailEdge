from __future__ import annotations

from collections.abc import Iterable

import frappe


# These compact names are the long-standing internal RetailEdge role IDs used by
# existing DocType permissions and installed sites. Keep them stable.
RETAILEDGE_ROLE_NAMES = (
	"RetailEdgeCashier",
	"RetailEdgeManager",
	"RetailEdgeBranchManager",
	"RetailEdgeAuditor",
)

# Only aliases already present in the product contract are preserved here. Do
# not invent additional spellings: every extra Role becomes another permission
# identity that must be governed and migrated later.
RETAILEDGE_ROLE_ALIASES = {
	"RetailEdgeManager": ("RetailEdge Manager",),
	"RetailEdgeBranchManager": ("RetailEdge Branch Manager",),
	"RetailEdgeAuditor": ("RetailEdge Auditor",),
}

RETAILEDGE_COMPATIBILITY_ROLE_NAMES = tuple(
	alias for aliases in RETAILEDGE_ROLE_ALIASES.values() for alias in aliases
)
ALL_RETAILEDGE_ROLE_NAMES = RETAILEDGE_ROLE_NAMES + RETAILEDGE_COMPATIBILITY_ROLE_NAMES


def canonical_retailedge_role(role_name: str | None) -> str | None:
	if not role_name:
		return role_name
	if role_name in RETAILEDGE_ROLE_NAMES:
		return role_name
	for canonical, aliases in RETAILEDGE_ROLE_ALIASES.items():
		if role_name in aliases:
			return canonical
	return role_name


def canonicalize_retailedge_roles(role_names: Iterable[str] | None) -> set[str]:
	return {canonical_retailedge_role(role_name) for role_name in (role_names or ()) if role_name}


def retailedge_role_variants(role_name: str) -> tuple[str, ...]:
	canonical = canonical_retailedge_role(role_name)
	if canonical not in RETAILEDGE_ROLE_NAMES:
		return (role_name,)
	return (canonical, *RETAILEDGE_ROLE_ALIASES.get(canonical, ()))


def user_has_retailedge_role(role_name: str, *, user: str | None = None) -> bool:
	user_roles = set(frappe.get_roles(user or frappe.session.user))
	return bool(user_roles.intersection(retailedge_role_variants(role_name)))


def ensure_retailedge_roles(*, migrate_alias_assignments: bool = True):
	"""Ensure stable RetailEdge roles and preserve known alias compatibility.

	Existing Role records are never renamed, deleted, or have ``desk_access``
	changed here. New missing canonical/compatibility Role records are created as
	Desk-enabled roles so RetailEdge operational users remain valid System Users.
	"""
	for role_name in ALL_RETAILEDGE_ROLE_NAMES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": 1,
			}
		).insert(ignore_permissions=True)

	if migrate_alias_assignments:
		_add_canonical_roles_for_alias_assignments()


def _add_canonical_roles_for_alias_assignments():
	"""Add canonical roles to alias-only users without removing any assignment."""
	for canonical, aliases in RETAILEDGE_ROLE_ALIASES.items():
		users = frappe.get_all(
			"Has Role",
			filters={"parenttype": "User", "role": ["in", list(aliases)]},
			pluck="parent",
		)
		for user in sorted(set(users)):
			user_doc = frappe.get_doc("User", user)
			existing_roles = {row.role for row in user_doc.get("roles") or []}
			if canonical in existing_roles:
				continue
			user_doc.append("roles", {"role": canonical})
			user_doc.save(ignore_permissions=True)
