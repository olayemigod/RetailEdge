from __future__ import annotations

from typing import Any
from urllib.parse import quote

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt, now_datetime, strip_html

from retailedge.branch_context import has_doctype, has_field

PROJECT_UPDATE_DOCTYPE = "Project Update"
PROJECT_DOCTYPE = "Project"
PUBLISH_FIELD = "retailedge_publish_to_customer"
SUMMARY_FIELD = "retailedge_customer_summary"
PUBLISHED_ON_FIELD = "retailedge_published_on"
PUBLISHED_BY_FIELD = "retailedge_published_by"
MAX_CUSTOMER_UPDATE_LENGTH = 2000
MAX_PROJECT_UPDATE_ROWS = 200


def ensure_customer_project_update_custom_fields() -> dict[str, list[dict[str, Any]]]:
	"""Add neutral publication metadata to ERPNext Project Update.

	Project and Project Update remain the source of truth. These fields only mark
	which submitted native updates are approved for customer-portal visibility.
	"""
	if not has_doctype(PROJECT_UPDATE_DOCTYPE):
		return {}

	custom_fields = {
		PROJECT_UPDATE_DOCTYPE: [
			{
				"fieldname": "retailedge_customer_portal_section",
				"label": "Customer Portal Publication",
				"fieldtype": "Section Break",
				"insert_after": "users",
				"collapsible": 1,
			},
			{
				"fieldname": PUBLISH_FIELD,
				"label": "Publish to Customer Portal",
				"fieldtype": "Check",
				"default": "0",
				"insert_after": "retailedge_customer_portal_section",
				"allow_on_submit": 1,
			},
			{
				"fieldname": SUMMARY_FIELD,
				"label": "Customer Update",
				"fieldtype": "Small Text",
				"insert_after": PUBLISH_FIELD,
				"depends_on": f"eval:doc.{PUBLISH_FIELD}",
				"mandatory_depends_on": f"eval:doc.{PUBLISH_FIELD}",
				"allow_on_submit": 1,
			},
			{
				"fieldname": PUBLISHED_ON_FIELD,
				"label": "Published On",
				"fieldtype": "Datetime",
				"insert_after": SUMMARY_FIELD,
				"read_only": 1,
				"allow_on_submit": 1,
			},
			{
				"fieldname": PUBLISHED_BY_FIELD,
				"label": "Published By",
				"fieldtype": "Link",
				"options": "User",
				"insert_after": PUBLISHED_ON_FIELD,
				"read_only": 1,
				"allow_on_submit": 1,
			},
		]
	}
	create_custom_fields(custom_fields, ignore_validate=True, update=True)
	return custom_fields


def validate_customer_project_update_publication(doc, method: str | None = None) -> None:
	"""Govern explicit customer publication without changing the linked Project."""
	if not has_field(PROJECT_UPDATE_DOCTYPE, PUBLISH_FIELD):
		return
	if not cint(doc.get(PUBLISH_FIELD)):
		return

	project_name = str(doc.get("project") or "").strip()
	if not project_name or not frappe.db.exists(PROJECT_DOCTYPE, project_name):
		frappe.throw(_("A valid Project is required before publishing a customer update."))
	if not frappe.has_permission(PROJECT_DOCTYPE, "read", doc=project_name):
		frappe.throw(_("You do not have permission to publish an update for this Project."), frappe.PermissionError)

	project = frappe.db.get_value(
		PROJECT_DOCTYPE,
		project_name,
		["customer", "company"],
		as_dict=True,
	)
	if not project or not project.customer:
		frappe.throw(_("Only Projects linked to a Customer can be published to the Customer Portal."))

	summary = _clean_customer_summary(doc.get(SUMMARY_FIELD))
	if not summary:
		frappe.throw(_("Customer Update is required when publishing to the Customer Portal."))
	doc.set(SUMMARY_FIELD, summary)

	old_doc = doc.get_doc_before_save()
	was_published = cint(old_doc.get(PUBLISH_FIELD)) if old_doc else 0
	if not was_published or not doc.get(PUBLISHED_ON_FIELD):
		doc.set(PUBLISHED_ON_FIELD, now_datetime())
		doc.set(PUBLISHED_BY_FIELD, frappe.session.user)


def _clean_customer_summary(value: Any) -> str:
	plain = strip_html(str(value or ""))
	cleaned = "\n".join(line.strip() for line in plain.splitlines() if line.strip()).strip()
	if len(cleaned) > MAX_CUSTOMER_UPDATE_LENGTH:
		frappe.throw(
			_("Customer Update cannot exceed {0} characters.").format(MAX_CUSTOMER_UPDATE_LENGTH),
			frappe.ValidationError,
		)
	return cleaned


def _publication_fields_available() -> bool:
	return all(
		has_field(PROJECT_UPDATE_DOCTYPE, fieldname)
		for fieldname in (PUBLISH_FIELD, SUMMARY_FIELD, PUBLISHED_ON_FIELD)
	)


def _owned_projects(customers: list[str], project_names: list[str] | None = None) -> list[Any]:
	customers = [str(name) for name in customers if name]
	if not customers or not has_doctype(PROJECT_DOCTYPE):
		return []
	filters: dict[str, Any] = {"customer": ["in", customers]}
	if project_names:
		filters["name"] = ["in", [str(name) for name in project_names if name]]
	return frappe.get_all(
		PROJECT_DOCTYPE,
		filters=filters,
		fields=[
			"name",
			"project_name",
			"customer",
			"company",
			"status",
			"percent_complete",
			"expected_start_date",
			"expected_end_date",
		],
		order_by="modified desc",
		limit_page_length=MAX_PROJECT_UPDATE_ROWS,
	)


def _published_update_rows(project_names: list[str], limit: int = MAX_PROJECT_UPDATE_ROWS) -> list[Any]:
	if not project_names or not _publication_fields_available():
		return []
	return frappe.get_all(
		PROJECT_UPDATE_DOCTYPE,
		filters={
			"project": ["in", project_names],
			"docstatus": 1,
			PUBLISH_FIELD: 1,
		},
		fields=[
			"name",
			"project",
			"date",
			"time",
			SUMMARY_FIELD,
			PUBLISHED_ON_FIELD,
		],
		order_by=f"{PUBLISHED_ON_FIELD} desc, date desc, time desc, creation desc",
		limit_page_length=max(1, min(int(limit or MAX_PROJECT_UPDATE_ROWS), MAX_PROJECT_UPDATE_ROWS)),
	)


def get_customer_project_update_states(
	project_names: list[str],
	customers: list[str],
) -> dict[str, dict[str, Any]]:
	"""Return only explicitly published summaries for already-owned Projects."""
	owned = _owned_projects(customers, project_names)
	owned_names = [str(row.name) for row in owned if row.name]
	updates = _published_update_rows(owned_names)
	states: dict[str, dict[str, Any]] = {
		name: {"count": 0, "latest_summary": "", "latest_on": None}
		for name in owned_names
	}
	for row in updates:
		project = str(row.project or "")
		if project not in states:
			continue
		state = states[project]
		state["count"] += 1
		if not state["latest_summary"]:
			state["latest_summary"] = str(row.get(SUMMARY_FIELD) or "")
			state["latest_on"] = row.get(PUBLISHED_ON_FIELD) or row.date
	return states


def get_customer_project_updates(project: str | None = None) -> dict[str, Any]:
	"""Return customer-safe Project progress plus approved native Project Updates."""
	from retailedge.customer_portal import _assert_customer_portal_user

	customers = _assert_customer_portal_user()
	requested_project = str(project or "").strip()
	owned = _owned_projects(customers, [requested_project] if requested_project else None)
	if requested_project and not any(str(row.name) == requested_project for row in owned):
		frappe.throw(_("This Project is not linked to your customer account."), frappe.PermissionError)

	project_map = {str(row.name): row for row in owned if row.name}
	updates = _published_update_rows(list(project_map))
	rows: list[dict[str, Any]] = []
	for update in updates:
		project_row = project_map.get(str(update.project or ""))
		if not project_row:
			continue
		rows.append(
			{
				"project": project_row.name,
				"project_name": project_row.project_name or project_row.name,
				"status": project_row.status or "",
				"percent_complete": flt(project_row.percent_complete),
				"expected_start_date": project_row.expected_start_date,
				"expected_end_date": project_row.expected_end_date,
				"update": update.name,
				"update_date": update.date,
				"published_on": update.get(PUBLISHED_ON_FIELD) or update.date,
				"summary": str(update.get(SUMMARY_FIELD) or ""),
			}
		)

	projects = [
		{
			"name": row.name,
			"label": row.project_name or row.name,
			"status": row.status or "",
			"percent_complete": flt(row.percent_complete),
			"updates_url": f"/customer_project_updates?project={quote(str(row.name), safe='')}",
		}
		for row in owned
	]
	return {
		"customer_names": customers,
		"project": requested_project,
		"projects": projects,
		"rows": rows,
		"row_count": len(rows),
		"source_of_truth": PROJECT_UPDATE_DOCTYPE,
		"project_source_of_truth": PROJECT_DOCTYPE,
		"publication_required": True,
		"submitted_updates_only": True,
		"internal_project_update_users_exposed": False,
		"project_costing_exposed": False,
		"read_only": True,
	}
