from __future__ import annotations

from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


OPERATIONAL_HISTORY_DOCTYPES = (
	"Sales Invoice",
	"POS Invoice",
	"Sales Order",
	"Delivery Note",
	"Quotation",
	"Payment Entry",
	"Payment Request",
	"Bank Transaction",
	"Material Request",
	"Stock Entry",
	"Stock Reconciliation",
	"Pick List",
	"Packing Slip",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Supplier Quotation",
	"Request for Quotation",
	"POS Opening Shift",
	"POS Closing Shift",
	"RetailEdge Cashier Expense",
	"RetailEdge Daily Sales Audit",
	"RetailEdge Bank Transaction Match",
)

IDENTITY_DEPENDENT_FIELDS = (
	"default_pos_profile",
	"default_pos_opening_cash_account",
	"default_cash_mode_of_payment",
	"default_warehouse",
	"default_source_warehouse",
	"default_target_warehouse",
	"default_returns_warehouse",
	"default_cost_center",
	"default_sales_cost_center",
	"default_expense_cost_center",
	"default_cash_account",
	"default_bank_account",
	"default_card_pos_account",
	"default_mobile_money_account",
)

BRANCH_USER_TABLE_FIELDS = (
	"default_cashiers",
	"default_managers",
	"default_auditors",
)


class RetailEdgeBranchProfile(Document):
	def validate(self):
		self._validate_company_branch_identity()
		try:
			from retailedge.branch_profile import validate_branch_profile
		except Exception:
			validate_branch_profile = None
		if validate_branch_profile:
			validate_branch_profile(self)

	def _validate_company_branch_identity(self):
		"""Allow corrections while protecting historical Company↔Branch meaning."""
		if getattr(self.flags, "branch_reassignment_archive", False):
			return

		stored = _stored_identity(self.name) if not self.is_new() and self.name else None
		stored_company = _clean(stored.get("company")) if stored else ""
		stored_branch = _clean(stored.get("branch")) if stored else ""
		company_changed = bool(stored and stored_company != _clean(self.company))
		branch_changed = bool(stored and stored_branch != _clean(self.branch))
		identity_changed = bool(company_changed or branch_changed)

		if identity_changed and not getattr(self.flags, "controlled_branch_reassignment", False):
			usage = get_branch_operational_usage(company=stored_company, branch=stored_branch)
			if usage:
				frappe.throw(
					_(
						"This Branch Setup already has operational history. Use the Change Company / Branch "
						"action so RetailEdge preserves the historical mapping instead of rewriting it."
					)
				)

			# Direct correction is allowed only while the mapping is unused. Clear
			# Branch-dependent values on the server as well as the form so API/import
			# callers cannot carry stale operational defaults into the new identity.
			_clear_identity_dependent_values(self)
			_clear_branch_users(self)
			if company_changed:
				self.is_default_for_company = 0

		if self.is_new() or identity_changed:
			if getattr(self.flags, "controlled_branch_reassignment", False):
				_assert_controlled_target_available(
					profile_name=self.name,
					company=_clean(self.company),
					branch=_clean(self.branch),
				)
			else:
				_assert_normal_target_available(
					profile_name=self.name,
					company=_clean(self.company),
					branch=_clean(self.branch),
				)


@frappe.whitelist()
def get_branch_profile_reassignment_state(name: str) -> dict:
	"""Return whether direct identity correction is safe for one Branch Setup."""
	doc = frappe.get_doc("RetailEdge Branch Profile", name)
	doc.check_permission("read")
	usage = get_branch_operational_usage(company=_clean(doc.company), branch=_clean(doc.branch))
	can_write = bool(doc.has_permission("write"))
	can_create = bool(frappe.has_permission("RetailEdge Branch Profile", "create"))
	return {
		"has_operational_history": bool(usage),
		"identity_editable": bool(can_write and not usage),
		"requires_controlled_reassignment": bool(usage),
		"can_reassign": bool(can_write and can_create),
		"usage_doctypes": [row["doctype"] for row in usage],
	}


@frappe.whitelist()
def reassign_branch_profile(name: str, new_company: str, new_branch: str) -> dict:
	"""Deliberately change Branch identity without rewriting historical meaning.

	Unused setups are corrected in place. If operational history exists, RetailEdge
	first creates a disabled historical snapshot of the old Company↔Branch mapping,
	then moves the current setup to the requested target in the same request
	transaction. Submitted ERPNext documents are never changed.
	"""
	doc = frappe.get_doc("RetailEdge Branch Profile", name)
	doc.check_permission("write")
	if not frappe.has_permission("RetailEdge Branch Profile", "create"):
		frappe.throw(
			_("You need permission to create Branch Setup history before reassigning this Branch."),
			frappe.PermissionError,
		)

	new_company = _clean(new_company)
	new_branch = _clean(new_branch)
	if not new_company:
		frappe.throw(_("New Company is required."))
	if not new_branch:
		frappe.throw(_("New Branch is required."))
	_assert_master_access("Company", new_company)
	_assert_master_access("Branch", new_branch)

	old_company = _clean(doc.company)
	old_branch = _clean(doc.branch)
	if old_company == new_company and old_branch == new_branch:
		return {
			"name": doc.name,
			"company": old_company,
			"branch": old_branch,
			"historical_setup": "",
			"changed": False,
		}

	_assert_controlled_target_available(
		profile_name=doc.name,
		company=new_company,
		branch=new_branch,
	)
	blockers = _get_active_reassignment_blockers(doc)
	if blockers:
		references = ", ".join(f"{row['doctype']} {row['name']}" for row in blockers)
		frappe.throw(
			_("Close active POS work before changing this Branch assignment: {0}.").format(references)
		)

	usage = get_branch_operational_usage(company=old_company, branch=old_branch)
	historical_setup = ""
	if usage:
		historical_setup = _create_historical_snapshot(
			doc,
			new_company=new_company,
			new_branch=new_branch,
		)

	company_changed = old_company != new_company
	branch_changed = old_branch != new_branch
	doc.company = new_company
	doc.branch = new_branch
	_clear_identity_dependent_values(doc)
	if company_changed:
		doc.is_default_for_company = 0
	if company_changed or branch_changed:
		_clear_branch_users(doc)
	_append_reassignment_note(
		doc,
		old_company=old_company,
		old_branch=old_branch,
		new_company=new_company,
		new_branch=new_branch,
		historical_setup=historical_setup,
	)
	doc.flags.controlled_branch_reassignment = True
	doc.save()

	return {
		"name": doc.name,
		"company": new_company,
		"branch": new_branch,
		"historical_setup": historical_setup,
		"changed": True,
		"had_operational_history": bool(usage),
		"cleared_identity_defaults": list(IDENTITY_DEPENDENT_FIELDS),
	}


def get_branch_operational_usage(company: str, branch: str) -> list[dict[str, str]]:
	"""Return bounded evidence that a Company↔Branch mapping has operational history."""
	company = _clean(company)
	branch = _clean(branch)
	if not branch:
		return []

	usage = []
	for doctype in OPERATIONAL_HISTORY_DOCTYPES:
		if not _doctype_exists(doctype):
			continue
		filters = _usage_filters(doctype=doctype, company=company, branch=branch)
		if not filters:
			continue
		try:
			name = frappe.db.exists(doctype, filters)
		except Exception:
			name = None
		if name:
			usage.append({"doctype": doctype, "name": str(name)})
	return usage


def _usage_filters(*, doctype: str, company: str, branch: str) -> dict:
	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		return {}

	filters = {}
	if meta.has_field("company") and company:
		filters["company"] = company
	if meta.has_field("retailedge_branch"):
		filters["retailedge_branch"] = branch
	elif meta.has_field("branch"):
		filters["branch"] = branch
	else:
		return {}
	return filters


def _stored_identity(name: str) -> dict | None:
	if not name:
		return None
	return frappe.db.get_value(
		"RetailEdge Branch Profile",
		name,
		["company", "branch"],
		as_dict=True,
	)


def _assert_normal_target_available(*, profile_name: str, company: str, branch: str) -> None:
	if not company or not branch:
		return
	other = frappe.db.get_value(
		"RetailEdge Branch Profile",
		{"name": ["!=", profile_name or ""], "branch": branch},
		["name", "company", "enabled"],
		as_dict=True,
	)
	if not other:
		return
	frappe.throw(
		_(
			"Branch {0} already has Branch Setup {1} for Company {2}. Use the controlled Change Company / Branch "
			"action when deliberately reusing a historical Branch mapping."
		).format(branch, other.get("name"), other.get("company"))
	)


def _assert_controlled_target_available(*, profile_name: str, company: str, branch: str) -> None:
	if not company or not branch:
		return
	other = frappe.db.get_value(
		"RetailEdge Branch Profile",
		{
			"name": ["!=", profile_name or ""],
			"branch": branch,
			"enabled": 1,
		},
		["name", "company"],
		as_dict=True,
	)
	if not other:
		return
	frappe.throw(
		_(
			"Branch {0} is currently active in Branch Setup {1} for Company {2}. "
			"Disable or correct that active mapping first."
		).format(
			branch,
			other.get("name"),
			other.get("company"),
		)
	)


def _create_historical_snapshot(doc, *, new_company: str, new_branch: str) -> str:
	archive = frappe.copy_doc(doc)
	archive.name = None
	archive.profile_name = _historical_profile_name(doc)
	archive.enabled = 0
	archive.is_default_for_company = 0
	archive.notes = _append_note_text(
		getattr(archive, "notes", None),
		_(
			"Historical Branch Setup snapshot created automatically before reassignment from {0} / {1} to {2} / {3}."
		).format(doc.company, doc.branch, new_company, new_branch),
	)
	archive.flags.branch_reassignment_archive = True
	archive.insert()
	return archive.name


def _historical_profile_name(doc) -> str:
	stamp = now_datetime().strftime("%Y%m%d-%H%M%S")
	suffix = uuid4().hex[:6]
	base = f"{_clean(getattr(doc, 'profile_name', None)) or _clean(doc.name)} [History {stamp}-{suffix}]"
	return base[:140]


def _clear_identity_dependent_values(doc) -> None:
	for fieldname in IDENTITY_DEPENDENT_FIELDS:
		if doc.meta.has_field(fieldname):
			setattr(doc, fieldname, None)


def _clear_branch_users(doc) -> None:
	for fieldname in BRANCH_USER_TABLE_FIELDS:
		if doc.meta.has_field(fieldname):
			doc.set(fieldname, [])


def _append_reassignment_note(
	doc,
	*,
	old_company: str,
	old_branch: str,
	new_company: str,
	new_branch: str,
	historical_setup: str,
) -> None:
	detail = _("Branch assignment changed from {0} / {1} to {2} / {3}.").format(
		old_company,
		old_branch,
		new_company,
		new_branch,
	)
	if historical_setup:
		detail = f"{detail} Historical setup: {historical_setup}."
	doc.notes = _append_note_text(getattr(doc, "notes", None), detail)


def _append_note_text(existing, detail: str) -> str:
	existing = str(existing or "").strip()
	stamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
	line = f"[{stamp}] {detail}"
	return f"{existing}\n{line}".strip() if existing else line


def _get_active_reassignment_blockers(doc) -> list[dict[str, str]]:
	blockers = []
	for doctype in ("POS Opening Shift", "POS Opening Entry"):
		if not _doctype_exists(doctype):
			continue
		filters = _open_pos_filters(doctype=doctype, doc=doc)
		if not filters:
			continue
		try:
			name = frappe.db.exists(doctype, filters)
		except Exception:
			name = None
		if name:
			blockers.append({"doctype": doctype, "name": str(name)})
	return blockers


def _open_pos_filters(*, doctype: str, doc) -> dict:
	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		return {}

	filters = {}
	if meta.has_field("company") and doc.company:
		filters["company"] = doc.company
	if meta.has_field("retailedge_branch"):
		filters["retailedge_branch"] = doc.branch
	elif meta.has_field("branch"):
		filters["branch"] = doc.branch
	elif meta.has_field("pos_profile") and getattr(doc, "default_pos_profile", None):
		filters["pos_profile"] = doc.default_pos_profile
	else:
		return {}
	if meta.has_field("status"):
		filters["status"] = ["in", ["Open", "Opened"]]
	if meta.has_field("docstatus"):
		filters["docstatus"] = ["<", 2]
	return filters


def _assert_master_access(doctype: str, name: str) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have access to {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)


def _doctype_exists(doctype: str) -> bool:
	try:
		return bool(frappe.db.exists("DocType", doctype))
	except Exception:
		return False


def _clean(value) -> str:
	return str(value or "").strip()
