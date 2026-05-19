from frappe.model.document import Document

from retailedge.payment_evidence_matching import prepare_statement_import_row_doc


class RetailEdgeStatementImportRow(Document):
	def validate(self):
		parent = getattr(self, "parent_doc", None)
		prepare_statement_import_row_doc(self, parent=parent)
