from __future__ import annotations

import frappe
from frappe.model.document import Document


class RetailEdgeCompanyProfile(Document):
	def validate(self):
		if self.company:
			self.company = str(self.company).strip()
		if self.display_name:
			self.display_name = str(self.display_name).strip()
		if self.email:
			self.email = str(self.email).strip()
		if self.website:
			self.website = str(self.website).strip()
