from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class SupplierDocumentPurchaseInvoiceHandoff(Document):
	def before_insert(self):
		if not getattr(self.flags, "supplier_document_purchase_invoice_handoff_api_write", False):
			frappe.throw(
				_("Supplier document Purchase Invoice handoffs can only be recorded through the controlled review service."),
				frappe.PermissionError,
			)

	def validate(self):
		if not self.is_new():
			frappe.throw(
				_("Supplier document Purchase Invoice handoff history is immutable."),
				frappe.ValidationError,
			)
		if not frappe.db.exists("Supplier Document Extraction", self.extraction):
			frappe.throw(_("Supplier Document Extraction was not found."), frappe.DoesNotExistError)
		extraction = frappe.get_doc("Supplier Document Extraction", self.extraction)
		if (
			self.supplier_document_intake != extraction.supplier_document_intake
			or self.supplier != extraction.supplier
			or self.company != extraction.company
			or self.purchase_order != extraction.purchase_order
			or self.source_file != extraction.source_file
		):
			frappe.throw(
				_("Purchase Invoice handoff authority must match the accepted extraction evidence."),
				frappe.ValidationError,
			)
		review = frappe.get_doc("Supplier Document Extraction Review", self.extraction_review)
		if review.extraction != self.extraction or review.decision != "Accepted":
			frappe.throw(_("Purchase Invoice handoff requires an accepted extraction review."), frappe.ValidationError)
		if not frappe.db.exists("Purchase Invoice", self.purchase_invoice):
			frappe.throw(_("Purchase Invoice draft was not found."), frappe.DoesNotExistError)
		invoice = frappe.get_doc("Purchase Invoice", self.purchase_invoice)
		if invoice.docstatus != 0:
			frappe.throw(_("A new supplier document handoff can reference only a draft Purchase Invoice."), frappe.ValidationError)
		if invoice.supplier != self.supplier or invoice.company != self.company:
			frappe.throw(_("Purchase Invoice Supplier and Company must match the extraction authority."), frappe.ValidationError)
		if not any(row.purchase_order == self.purchase_order for row in invoice.items):
			frappe.throw(_("Purchase Invoice must be mapped from the authoritative Purchase Order."), frappe.ValidationError)

	def on_trash(self):
		frappe.throw(
			_("Supplier document Purchase Invoice handoffs are retained for audit history."),
			frappe.ValidationError,
		)
