from __future__ import annotations

from frappe.model.document import Document


class RetailEdgeBranchProfile(Document):
	def validate(self):
		try:
			from retailedge.branch_profile import validate_branch_profile
		except Exception:
			validate_branch_profile = None
		if validate_branch_profile:
			validate_branch_profile(self)

