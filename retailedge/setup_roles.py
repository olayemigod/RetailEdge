from __future__ import annotations

from collections.abc import Iterable

import frappe
from frappe.permissions import add_permission, update_permission_property

from retailedge.branch_context import GLOBAL_BRANCH_ACCESS_ROLES


RETAILEDGE_ROLE_NAMES = (
	"RetailEdgeCashier",
	"RetailEdgeManager",
	"RetailEdgeBranchManager",
	"RetailEdgeAuditor",
)

RETAILEDGE_ROLE_ALIASES = {
	"RetailEdgeCashier": ("RetailEdge Cashier",),
	"RetailEdgeManager": ("RetailEdge Manager",),
	"RetailEdgeBranchManager": ("RetailEdge Branch Manager",),
	"RetailEdgeAuditor": ("RetailEdge Auditor",),
}

RETAILEDGE_COMPATIBILITY_ROLE_NAMES = tuple(
	alias for aliases in RETAILEDGE_ROLE_ALIASES.values() for alias in aliases
)
ALL_RETAILEDGE_ROLE_NAMES = RETAILEDGE_ROLE_NAMES + RETAILEDGE_COMPATIBILITY_ROLE_NAMES

# These ERPNext/master source documents already sit behind RetailEdge
# management/report capability checks. Product management/audit roles receive
# read/select/report only; mutation remains governed by native ERPNext roles and
# workflows. RetailEdge-owned workflow DocTypes keep their explicit DocType
# permissions and are deliberately not rewritten here.
MANAGEMENT_READ_DOCTYPES = (
	"Company",
	"Customer",
	"Supplier",
	"Item",
	"Warehouse",
	"Price List",
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"POS Invoice",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Supplier Quotation",
	"Request for Quotation",
	"Material Request",
	"Stock Entry",
	"Stock Reconciliation",
	"Stock Ledger Entry",
	"Payment Entry",
)


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

	_ensure_operational_branch_read()
	_ensure_management_read_permissions()
	_ensure_retailedge_page_role_variants()


def _ensure_operational_branch_read() -> None:
	"""Give RetailEdge operating/global roles only the Branch visibility they need.

	The Working Branch selector and Branch Assignment validation require normal
	Frappe read permission on the Branch master. Roles that RetailEdge explicitly
	classifies as global Branch authority must have the same minimum read/select
	capability. This does not grant create, write, delete, import or permission
	administration rights. User Permissions and Branch Assignment scope continue
	to decide which Branch records a restricted user may actually reach.
	"""
	if not frappe.db.exists("DocType", "Branch"):
		return
	role_names = sorted(set(ALL_RETAILEDGE_ROLE_NAMES).union(GLOBAL_BRANCH_ACCESS_ROLES))
	for role_name in role_names:
		if not frappe.db.exists("Role", role_name):
			continue
		if not frappe.db.exists(
			"Custom DocPerm",
			{"parent": "Branch", "role": role_name, "permlevel": 0},
		):
			add_permission("Branch", role_name, 0)
		update_permission_property("Branch", role_name, 0, "read", 1)
		update_permission_property("Branch", role_name, 0, "select", 1)
	frappe.clear_cache(doctype="Branch")


def _ensure_management_read_permissions() -> None:
	"""Align RetailEdge management/audit report roles with ERPNext source reads."""
	role_names = tuple(
		dict.fromkeys(
			(
				*retailedge_role_variants("RetailEdgeManager"),
				*retailedge_role_variants("RetailEdgeBranchManager"),
				*retailedge_role_variants("RetailEdgeAuditor"),
			)
		)
	)
	for doctype in MANAGEMENT_READ_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		for role_name in role_names:
			if not frappe.db.exists("Role", role_name):
				continue
			if not frappe.db.exists(
				"Custom DocPerm",
				{"parent": doctype, "role": role_name, "permlevel": 0},
			):
				add_permission(doctype, role_name, 0)
			update_permission_property(doctype, role_name, 0, "read", 1)
			update_permission_property(doctype, role_name, 0, "select", 1)
			update_permission_property(doctype, role_name, 0, "report", 1)
		frappe.clear_cache(doctype=doctype)


def _add_canonical_roles_for_alias_assignments():
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


def _ensure_retailedge_page_role_variants() -> None:
	if not frappe.db.exists("DocType", "Page"):
		return

	for page_name in frappe.get_all("Page", filters={"module": "RetailEdge"}, pluck="name"):
		rows = frappe.get_all(
			"Has Role",
			filters={"parenttype": "Page", "parent": page_name},
			fields=["role", "idx"],
			order_by="idx asc",
		)
		existing_roles = {row.role for row in rows}
		next_idx = max((int(row.idx or 0) for row in rows), default=0) + 1
		inserted = False

		for canonical, aliases in RETAILEDGE_ROLE_ALIASES.items():
			variants = (canonical, *aliases)
			if not existing_roles.intersection(variants):
				continue
			for variant in variants:
				if variant in existing_roles or not frappe.db.exists("Role", variant):
					continue
				frappe.get_doc(
					{
						"doctype": "Has Role",
						"parent": page_name,
						"parenttype": "Page",
						"parentfield": "roles",
						"role": variant,
						"idx": next_idx,
					}
				).db_insert()
				next_idx += 1
				existing_roles.add(variant)
				inserted = True

		if inserted:
			frappe.get_doc("Page", page_name).clear_cache()
