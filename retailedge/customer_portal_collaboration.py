from __future__ import annotations

from typing import Any
from uuid import uuid4

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, strip_html, today

from erpnext.controllers.website_list_for_contact import has_website_permission

ALLOWED_ACTIVITY_TYPES = {"Message", "Accepted", "Declined"}
QUOTATION_RESPONSE_TYPES = {"Accepted", "Declined"}
QUOTATION_RESPONSE_STATUSES = {"Open", "Replied"}
MAX_ACTIVITY_MESSAGE_LENGTH = 2000
MAX_PORTAL_ACTIVITY_ROWS = 200


def _portal_customers() -> list[str]:
	# Local import avoids a customer_portal <-> collaboration import cycle.
	from retailedge.customer_portal import _assert_customer_portal_user

	return _assert_customer_portal_user()


def _assert_owned_quotation(quotation, customers: list[str]) -> None:
	if quotation.doctype != "Quotation":
		frappe.throw(_("Only Quotations are supported for this customer activity."), frappe.ValidationError)
	if quotation.quotation_to != "Customer" or quotation.party_name not in customers:
		frappe.throw(_("This quotation is not linked to your customer account."), frappe.PermissionError)
	if not has_website_permission(quotation, "read", frappe.session.user):
		frappe.throw(_("You do not have access to this quotation."), frappe.PermissionError)
	if quotation.docstatus != 1:
		frappe.throw(_("Only submitted quotations can receive customer activity."), frappe.ValidationError)


def _lock_and_reload_quotation(quotation, customers: list[str]):
	# Serialize customer responses without changing the submitted Quotation.
	frappe.db.sql("select name from `tabQuotation` where name=%s for update", (quotation.name,))
	quotation.reload()
	_assert_owned_quotation(quotation, customers)
	return quotation


def quotation_response_allowed(quotation: Any) -> bool:
	status = str(getattr(quotation, "status", "") or "")
	docstatus = int(getattr(quotation, "docstatus", 0) or 0)
	valid_till = getattr(quotation, "valid_till", None)
	if docstatus != 1 or status not in QUOTATION_RESPONSE_STATUSES:
		return False
	if valid_till and getdate(valid_till) < getdate(today()):
		return False
	return True


def _clean_message(message: str | None, *, required: bool) -> str:
	plain = strip_html(str(message or ""))
	lines = [line.strip() for line in plain.splitlines()]
	cleaned = "\n".join(line for line in lines if line).strip()
	if required and not cleaned:
		frappe.throw(_("Enter a message before sending."), frappe.ValidationError)
	if len(cleaned) > MAX_ACTIVITY_MESSAGE_LENGTH:
		frappe.throw(
			_("Message cannot exceed {0} characters.").format(MAX_ACTIVITY_MESSAGE_LENGTH),
			frappe.ValidationError,
		)
	return cleaned


def _latest_response(quotation_name: str, customer: str) -> Any | None:
	if not frappe.db.exists("DocType", "Customer Portal Activity"):
		return None
	rows = frappe.get_all(
		"Customer Portal Activity",
		filters={
			"reference_doctype": "Quotation",
			"reference_name": quotation_name,
			"customer": customer,
			"activity_type": ["in", sorted(QUOTATION_RESPONSE_TYPES)],
		},
		fields=[
			"name",
			"reference_name",
			"activity_type",
			"message",
			"activity_datetime",
			"portal_user",
		],
		order_by="activity_datetime desc, creation desc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def _activity_result(activity: Any, *, reused: bool) -> dict[str, Any]:
	return {
		"activity": activity.name,
		"quotation": activity.reference_name,
		"activity_type": activity.activity_type,
		"message": activity.message or "",
		"activity_datetime": activity.activity_datetime,
		"reused": reused,
		"quotation_mutated": False,
	}


def _insert_activity(quotation, activity_type: str, message: str):
	activity = frappe.new_doc("Customer Portal Activity")
	activity.update(
		{
			"activity_key": f"CPA-{uuid4().hex}",
			"reference_doctype": "Quotation",
			"reference_name": quotation.name,
			"activity_type": activity_type,
			"activity_datetime": now_datetime(),
			"customer": quotation.party_name,
			"company": quotation.company,
			"portal_user": frappe.session.user,
			"message": message,
			"document_status": quotation.status or "",
			"document_modified": quotation.modified,
		}
	)
	# Website users receive no generic create permission for the activity DocType.
	# This flag is checked by the DocType and exists only on this in-memory record.
	activity.flags.customer_portal_activity_api_write = True
	activity.insert(ignore_permissions=True)
	return activity


@frappe.whitelist(methods=["POST"])
def record_quotation_activity(
	quotation_name: str,
	activity_type: str,
	message: str = "",
) -> dict[str, Any]:
	customers = _portal_customers()
	quotation_name = str(quotation_name or "").strip()
	activity_type = str(activity_type or "").strip().title()
	if not quotation_name:
		frappe.throw(_("Quotation is required."), frappe.ValidationError)
	if activity_type not in ALLOWED_ACTIVITY_TYPES:
		frappe.throw(_("Choose Message, Accepted or Declined."), frappe.ValidationError)
	if not frappe.db.exists("Quotation", quotation_name):
		frappe.throw(_("Quotation was not found."), frappe.DoesNotExistError)

	quotation = frappe.get_doc("Quotation", quotation_name)
	_assert_owned_quotation(quotation, customers)
	quotation = _lock_and_reload_quotation(quotation, customers)

	if activity_type in QUOTATION_RESPONSE_TYPES and not quotation_response_allowed(quotation):
		frappe.throw(
			_("This quotation can no longer be accepted or declined from the portal."),
			frappe.ValidationError,
		)
	cleaned_message = _clean_message(message, required=activity_type == "Message")

	if activity_type in QUOTATION_RESPONSE_TYPES:
		existing = _latest_response(quotation.name, quotation.party_name)
		if (
			existing
			and existing.activity_type == activity_type
			and str(existing.message or "") == cleaned_message
		):
			return _activity_result(existing, reused=True)

	activity = _insert_activity(quotation, activity_type, cleaned_message)
	return _activity_result(activity, reused=False)


def get_quotation_activity_states(
	quotation_names: list[str],
	customers: list[str],
) -> dict[str, dict[str, Any]]:
	quotation_names = [str(name) for name in quotation_names if name]
	customers = [str(name) for name in customers if name]
	if not quotation_names or not customers or not frappe.db.exists("DocType", "Customer Portal Activity"):
		return {}

	rows = frappe.get_all(
		"Customer Portal Activity",
		filters={
			"reference_doctype": "Quotation",
			"reference_name": ["in", quotation_names],
			"customer": ["in", customers],
		},
		fields=[
			"name",
			"reference_name",
			"activity_type",
			"activity_datetime",
			"message",
			"portal_user",
		],
		order_by="activity_datetime desc, creation desc",
		limit_page_length=MAX_PORTAL_ACTIVITY_ROWS,
	)
	states: dict[str, dict[str, Any]] = {}
	for row in rows:
		quotation_name = str(row.reference_name or "")
		if not quotation_name:
			continue
		state = states.setdefault(
			quotation_name,
			{
				"response": "",
				"response_on": None,
				"response_note": "",
				"message_count": 0,
				"recent_messages": [],
			},
		)
		if row.activity_type in QUOTATION_RESPONSE_TYPES and not state["response"]:
			state["response"] = row.activity_type
			state["response_on"] = row.activity_datetime
			state["response_note"] = row.message or ""
		elif row.activity_type == "Message":
			state["message_count"] += 1
			if len(state["recent_messages"]) < 3:
				state["recent_messages"].append(
					{
						"activity": row.name,
						"message": row.message or "",
						"activity_datetime": row.activity_datetime,
						"portal_user": row.portal_user or "",
					}
				)
	return states
