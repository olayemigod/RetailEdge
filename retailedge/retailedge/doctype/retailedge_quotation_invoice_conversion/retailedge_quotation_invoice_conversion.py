from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from retailedge.quotation_invoice_conversion import conversion_write_authorized


class RetailEdgeQuotationInvoiceConversion(Document):
	def validate(self):
		if not conversion_write_authorized():
			frappe.throw(
				_("Quotation invoice conversion records are maintained by RetailEdge and cannot be edited manually."),
				frappe.PermissionError,
			)
		if self.quotation:
			quotation = frappe.get_doc("Quotation", self.quotation)
			if quotation.docstatus != 1:
				frappe.throw(_("Only submitted Quotations can be registered for direct invoicing."))
			if str(quotation.get("quotation_to") or "") != "Customer":
				frappe.throw(_("Only Customer Quotations can be registered for direct invoicing."))
			if self.company and quotation.company != self.company:
				frappe.throw(_("Quotation Company does not match the conversion record Company."))
		if self.sales_invoice:
			if not frappe.db.exists("Sales Invoice", self.sales_invoice):
				frappe.throw(_("The linked Sales Invoice does not exist."))
			invoice_company = frappe.db.get_value("Sales Invoice", self.sales_invoice, "company")
			if self.company and invoice_company and invoice_company != self.company:
				frappe.throw(_("Sales Invoice Company does not match the conversion record Company."))

	def on_trash(self):
		if not conversion_write_authorized():
			frappe.throw(
				_("Quotation invoice conversion records cannot be deleted manually."),
				frappe.PermissionError,
			)
