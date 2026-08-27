from __future__ import annotations

import frappe
from frappe.model.document import Document


class RetailEdgeBranchProfile(Document):
	def validate(self):
		self._validate_company_branch_identity()
		try:
			from retailedge.branch_profile import validate_branch_profile
		except Exception:
			validate_branch_profile = None
		if validate_branch_profile:
			validate_branch_profile(self)

	def _validate_company_branch_identity(self):
		"""Keep Branch ownership stable independently of operational enabled state."""
		if not self.is_new() and self.name:
			stored = frappe.db.get_value(
				"RetailEdge Branch Profile",
				self.name,
				["company", "branch"],
				as_dict=True,
			)
			if stored and (
				str(stored.get("company") or "") != str(self.company or "")
				or str(stored.get("branch") or "") != str(self.branch or "")
			):
				frappe.throw(
					"Company and Branch define the RetailEdge Branch Setup identity and cannot be changed after save. "
					"Create a deliberate replacement setup instead of moving a Branch between Companies."
				)

		if not self.branch or not self.company:
			return

		existing = frappe.db.get_value(
			"RetailEdge Branch Profile",
			{
				"name": ["!=", self.name or ""],
				"branch": self.branch,
			},
			["name", "company", "enabled"],
			as_dict=True,
		)
		if existing and str(existing.get("company") or "") != str(self.company or ""):
			frappe.throw(
				f"Branch {self.branch} is already assigned to Company {existing.get('company')} in Branch Setup "
				f"{existing.get('name')}. Disabling that setup does not release the Branch to another Company."
			)
