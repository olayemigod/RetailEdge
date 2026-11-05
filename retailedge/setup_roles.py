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

ALL_RETAILEDGE_ROLE_NAMES = RETAILEDGE_ROLE_NAMES

# Product management/audit roles need Company visibility so RetailEdge can
# validate the selected operating/reporting context. Business-document authority
# deliberately remains merchant-governed through native ERPNext roles and Role
# Permission Manager (including If Owner, User Permissions and sharing).
MANAGEMENT_READ_DOCTYPES = ("Company",)


def canonical_retailedge_role(role_name: str | None) -> str | None:
	return role_name


def canonicalize_retailedge_roles(role_names: Iterable[str] | None) -> set[str]:
	return {role_name for role_name in (role_names or ()) if role_name}


def retailedge_role_variants(role_name: str) -> tuple[str, ...]:
	return (role_name,)


def user_has_retailedge_role(role_name: str, *, user: str | None = None) -> bool:
	user_roles = set(frappe.get_roles(user or frappe.session.user))
	return bool(user_roles.intersection(retailedge_role_variants(role_name)))


def ensure_retailedge_roles():
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

	_ensure_operational_branch_read()
	_ensure_management_context_read_permissions()


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


def _ensure_management_context_read_permissions() -> None:
	"""Grant only the context-master read needed by RetailEdge management roles.

	Do not add or repair transaction permissions here. Sales, purchase, stock and
	payment document access must stay configurable in ERPNext Role Permission
	Manager so merchant policies such as If Owner remain authoritative.
	"""
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
		frappe.clear_cache(doctype=doctype)
