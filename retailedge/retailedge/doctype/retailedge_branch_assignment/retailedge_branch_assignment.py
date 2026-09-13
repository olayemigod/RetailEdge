from __future__ import annotations

from frappe.model.document import Document


class RetailEdgeBranchAssignment(Document):
	def validate(self):
		from retailedge.branch_assignment import validate_branch_assignment

		validate_branch_assignment(self)
