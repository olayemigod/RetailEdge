from __future__ import annotations

from typing import Any
from uuid import uuid4

import frappe
from frappe import _
from frappe.utils import now_datetime, strip_html

from erpnext.controllers.website_list_for_contact import has_website_permission

ALLOWED_ACTIVITY_TYPES = {"Message", "Acknowledged"}
MAX_ACTIVITY_MESSAGE_LENGTH = 2000
MAX_PORTAL_ACTIVITY_ROWS = 200
CLOSED_PURCHASE_ORDER_STATUSES = {"Closed", "Completed"}


def _portal_suppliers() -> list[str]:
	from retailedge.supplier_portal import _assert_supplier_portal_user

	return _assert_supplier_portal_user()


def _assert_owned_purchase_order(purchase_order, suppliers: list[str]) -> None:
	if purchase_order.doctype != "Purchase Order":
		frappe.throw(_("Only Purchase Orders are supported for supplier activity."), frappe.ValidationError)
	if purchase_order.supplier not in suppliers:
		frappe.throw(_("This purchase order is not linked to your supplier account."), frappe.PermissionError)
	if not has_website_permission(purchase_order, "read", frappe.session.user):
		frappe.throw(_("You do not have access to this purchase order."), frappe.PermissionError)
	if purchase_order.docstatus != 1:
		frappe.throw(_("Only submitted purchase orders can receive supplier activity."), frappe.ValidationError)


def _lock_and_reload_purchase_order(purchase_order, suppliers: list[str]):
	frappe.db.sql(
		"select name from `tabPurchase Order` where name=%s for update",
		(purchase_order.name,),
	)
	purchase_order.reload()
	_assert_owned_purchase_order(purchase_order, suppliers)
	return purchase_order


def purchase_order_acknowledgement_allowed(purchase_order: Any) -> bool:
	status = str(getattr(purchase_order, "status", "") or "")
	docstatus = int(getattr(purchase_order, "docstatus", 0) or 0)
	return docstatus == 1 and status not in CLOSED_PURCHASE_ORDER_STATUSES


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


def _latest_acknowledgement(purchase_order_name: str, supplier: str) -> Any | None:
	if not frappe.db.exists("DocType", "Supplier Portal Activity"):
		return None
	rows = frappe.get_all(
		"Supplier Portal Activity",
		filters={
			"reference_doctype": "Purchase Order",
			"reference_name": purchase_order_name,
			"supplier": supplier,
			"activity_type": "Acknowledged",
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
		"purchase_order": activity.reference_name,
		"activity_type": activity.activity_type,
		"message": activity.message or "",
		"activity_datetime": activity.activity_datetime,
		"reused": reused,
		"purchase_order_mutated": False,
	}


def _insert_activity(purchase_order, activity_type: str, message: str):
	activity = frappe.new_doc("Supplier Portal Activity")
	activity.update(
		{
			"activity_key": f"SPA-{uuid4().hex}",
			"reference_doctype": "Purchase Order",
			"reference_name": purchase_order.name,
			"activity_type": activity_type,
			"activity_datetime": now_datetime(),
			"supplier": purchase_order.supplier,
			"company": purchase_order.company,
			"portal_user": frappe.session.user,
			"message": message,
			"document_status": purchase_order.status or "",
			"document_modified": purchase_order.modified,
		}
	)
	activity.flags.supplier_portal_activity_api_write = True
	activity.insert(ignore_permissions=True)
	return activity


@frappe.whitelist(methods=["POST"])
def record_purchase_order_activity(
	purchase_order_name: str,
	activity_type: str,
	message: str = "",
) -> dict[str, Any]:
	suppliers = _portal_suppliers()
	purchase_order_name = str(purchase_order_name or "").strip()
	activity_type = str(activity_type or "").strip().title()
	if not purchase_order_name:
		frappe.throw(_("Purchase Order is required."), frappe.ValidationError)
	if activity_type not in ALLOWED_ACTIVITY_TYPES:
		frappe.throw(_("Choose Message or Acknowledged."), frappe.ValidationError)
	if not frappe.db.exists("Purchase Order", purchase_order_name):
		frappe.throw(_("Purchase Order was not found."), frappe.DoesNotExistError)

	purchase_order = frappe.get_doc("Purchase Order", purchase_order_name)
	_assert_owned_purchase_order(purchase_order, suppliers)
	purchase_order = _lock_and_reload_purchase_order(purchase_order, suppliers)

	cleaned_message = _clean_message(message, required=activity_type == "Message")
	if activity_type == "Acknowledged":
		if not purchase_order_acknowledgement_allowed(purchase_order):
			frappe.throw(
				_("This purchase order can no longer be acknowledged from the portal."),
				frappe.ValidationError,
			)
		existing = _latest_acknowledgement(purchase_order.name, purchase_order.supplier)
		if existing:
			return _activity_result(existing, reused=True)

	activity = _insert_activity(purchase_order, activity_type, cleaned_message)
	return _activity_result(activity, reused=False)


def get_purchase_order_activity_states(
	purchase_order_names: list[str],
	suppliers: list[str],
) -> dict[str, dict[str, Any]]:
	purchase_order_names = [str(name) for name in purchase_order_names if name]
	suppliers = [str(name) for name in suppliers if name]
	if (
		not purchase_order_names
		or not suppliers
		or not frappe.db.exists("DocType", "Supplier Portal Activity")
	):
		return {}

	rows = frappe.get_all(
		"Supplier Portal Activity",
		filters={
			"reference_doctype": "Purchase Order",
			"reference_name": ["in", purchase_order_names],
			"supplier": ["in", suppliers],
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
		purchase_order_name = str(row.reference_name or "")
		if not purchase_order_name:
			continue
		state = states.setdefault(
			purchase_order_name,
			{
				"acknowledged": False,
				"acknowledged_on": None,
				"acknowledgement_note": "",
				"message_count": 0,
				"recent_messages": [],
			},
		)
		if row.activity_type == "Acknowledged" and not state["acknowledged"]:
			state["acknowledged"] = True
			state["acknowledged_on"] = row.activity_datetime
			state["acknowledgement_note"] = row.message or ""
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
