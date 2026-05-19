from frappe.model.document import Document

from retailedge.payment_evidence_matching import prepare_payment_evidence_doc


class RetailEdgePaymentEvidence(Document):
	def validate(self):
		prepare_payment_evidence_doc(self)
