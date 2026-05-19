from frappe.model.document import Document

from retailedge.payment_evidence_matching import validate_payment_statement_import


class RetailEdgePaymentStatementImport(Document):
	def validate(self):
		validate_payment_statement_import(self)
