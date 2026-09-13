from frappe.model.document import Document

from retailedge.business_expense import (
	prepare_business_expense_defaults,
	prepare_business_expense_for_cancel,
	prepare_business_expense_for_submit,
	validate_business_expense_document,
)


class RetailEdgeBusinessExpense(Document):
	def before_validate(self):
		prepare_business_expense_defaults(self)

	def validate(self):
		validate_business_expense_document(self)

	def before_submit(self):
		prepare_business_expense_for_submit(self)

	def before_cancel(self):
		prepare_business_expense_for_cancel(self)
