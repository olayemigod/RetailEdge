from frappe.model.document import Document

from retailedge.statement_import import validate_payment_statement_import


class RetailEdgePaymentStatementImport(Document):
	def validate(self):
		validate_payment_statement_import(self)
