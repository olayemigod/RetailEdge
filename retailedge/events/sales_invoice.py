from __future__ import annotations

import frappe
from frappe.utils import getdate, today

from retailedge.posting_date_control import can_override_posting_date
from retailedge.utils.settings import get_retailedge_settings


def validate_sales_invoice(doc, method=None):
	settings = get_retailedge_settings()
	if not settings.enable_posting_date_control:
		return

	if not getattr(doc, "is_pos", 0):
		return

	if can_override_posting_date():
		return

	if getdate(doc.posting_date) < getdate(today()):
		raise frappe.ValidationError(
			"Backdated POS invoices are not allowed for your role. Please contact a manager."
		)
