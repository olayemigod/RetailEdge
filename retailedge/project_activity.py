from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

MAX_PROJECT_TASK_ROWS = 500


def _assert_project_read(project: str) -> Any:
	if not frappe.has_permission("Project", "read", doc=project):
		frappe.throw(_("You do not have permission to read this Project."), frappe.PermissionError)
	return frappe.get_doc("Project", project)


@frappe.whitelist()
def get_project_activity_context(project: str, limit: int = 200) -> dict[str, Any]:
	"""Return a bounded permission-aware native ERPNext Task/Milestone worklist.

	Task remains the operational source of truth. RetailEdge does not create a
	parallel milestone or project-activity document. Project Tasks are whole-project
	operational records because standard ERPNext Task has no RetailEdge Branch field.
	"""
	doc = _assert_project_read(project)
	if not frappe.db.exists("DocType", "Task"):
		return {
			"available": False,
			"tasks": [],
			"task_count": 0,
			"milestone_count": 0,
			"can_create_task": False,
			"scope": "Whole Project",
		}
	if not frappe.has_permission("Task", "read"):
		frappe.throw(_("You do not have permission to read Project Tasks."), frappe.PermissionError)

	page_length = max(1, min(cint(limit) or 200, MAX_PROJECT_TASK_ROWS))
	fields = [
		"name",
		"subject",
		"status",
		"priority",
		"progress",
		"is_milestone",
		"is_group",
		"parent_task",
		"exp_start_date",
		"exp_end_date",
		"completed_on",
	]
	rows = frappe.get_list(
		"Task",
		filters={"project": project, "is_template": 0},
		fields=fields,
		order_by="is_milestone desc, exp_end_date asc, modified desc",
		limit_page_length=page_length,
	)

	tasks = [
		{
			"name": row.name,
			"subject": row.subject or row.name,
			"status": row.status or "",
			"priority": row.priority or "",
			"progress": flt(row.progress),
			"is_milestone": bool(cint(row.is_milestone)),
			"is_group": bool(cint(row.is_group)),
			"parent_task": row.parent_task or "",
			"expected_start": row.exp_start_date,
			"expected_end": row.exp_end_date,
			"completed_on": row.completed_on,
			"route": f"/app/task/{row.name}",
		}
		for row in rows
	]

	return {
		"available": True,
		"project": doc.name,
		"company": doc.company or "",
		"tasks": tasks,
		"task_count": len(tasks),
		"milestone_count": sum(1 for row in tasks if row["is_milestone"]),
		"open_count": sum(1 for row in tasks if row["status"] not in {"Completed", "Cancelled"}),
		"overdue_count": sum(1 for row in tasks if row["status"] == "Overdue"),
		"can_create_task": bool(frappe.has_permission("Task", "create")),
		"scope": "Whole Project",
		"scope_note": "ERPNext Tasks and Milestones are whole-project operational records; Branch filtering does not narrow them.",
		"source_of_truth": "ERPNext Task",
	}
