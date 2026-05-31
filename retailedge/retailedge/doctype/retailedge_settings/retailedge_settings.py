from frappe.model.document import Document


class RetailEdgeSettings(Document):
	def validate(self):
		self._set_bank_auto_match_guidance()

	def _set_bank_auto_match_guidance(self):
		enable_auto_match = int(getattr(self, "enable_bank_auto_match", 0) or 0)
		auto_prepare = int(getattr(self, "auto_prepare_exact_bank_matches", 0) or 0)
		auto_confirm = int(getattr(self, "auto_confirm_exact_bank_matches", 0) or 0)

		if not enable_auto_match:
			mode = "Disabled"
		elif auto_confirm:
			mode = "Auto-Prepare + Auto-Confirm"
		elif auto_prepare:
			mode = "Auto-Prepare Only"
		else:
			mode = "Disabled"

		self.bank_auto_match_mode = mode
		self.bank_auto_match_guidance = (
			"Auto-match helps reduce manual review for strict exact bank matches. "
			"It operates only at the RetailEdge review layer. "
			"Auto-prepare creates Bank Match Review records. "
			"Auto-confirm confirms Bank Match Review records only. "
			"It does not reconcile Bank Transactions, change Bank Transaction status, create Payment Entries, "
			"create Journal Entries, create GL Entries, mark Sales Invoices as paid, mutate POS shifts, "
			"mutate Daily Sales Audit records, or mutate stock records. "
			"ERPNext reconciliation remains a separate future process."
		)
