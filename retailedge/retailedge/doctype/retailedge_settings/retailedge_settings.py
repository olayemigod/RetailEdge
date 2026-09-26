import frappe
from frappe import _
from frappe.model.document import Document

from retailedge.utils.settings import clear_retailedge_settings_cache


SELLING_PRICE_LIST_DEFAULT = (
	"party_default",
	"pos_profile",
	"branch_default",
	"user_default",
	"user_permission",
	"erpnext_default",
	"standard_price_list",
)
BUYING_PRICE_LIST_DEFAULT = (
	"party_default",
	"branch_default",
	"user_default",
	"user_permission",
	"erpnext_default",
	"standard_price_list",
)
SELLING_PRICE_LIST_SOURCES = set(SELLING_PRICE_LIST_DEFAULT)
BUYING_PRICE_LIST_SOURCES = set(BUYING_PRICE_LIST_DEFAULT)


class RetailEdgeSettings(Document):
	def validate(self):
		self._sync_cashier_expense_posting_policy()
		self._validate_price_list_governance()
		self._set_bank_auto_match_guidance()
		self._validate_business_expense_posting_workflow_state()

	def on_update(self):
		clear_retailedge_settings_cache()


	def _sync_cashier_expense_posting_policy(self):
		mode = str(getattr(self, "cashier_expense_posting_mode", None) or "Controlled Posting").strip()
		if mode not in {"Controlled Posting", "Direct Posting"}:
			frappe.throw(_("Cashier Expense Posting Mode must be Controlled Posting or Direct Posting."))
		self.cashier_expense_posting_mode = mode
		# Keep the legacy boolean synchronized for backward compatibility with
		# older integrations while the Select policy is the authoritative setting.
		self.require_cashier_expense_approval_before_posting = 0 if mode == "Direct Posting" else 1
		if (
			mode == "Direct Posting"
			and int(getattr(self, "enable_cashier_expense_workflow", 0) or 0)
			and not int(getattr(self, "enable_cashier_expense_accounting_posting", 0) or 0)
		):
			frappe.throw(
				_("Enable Accounting Posting for Cashier Expenses before selecting Direct Posting.")
			)

	def _validate_price_list_governance(self):
		if not int(getattr(self, "enable_price_list_governance", 1) or 0):
			return
		self.selling_price_list_precedence = self._normalise_price_list_precedence(
			getattr(self, "selling_price_list_precedence", None)
			or "\n".join(SELLING_PRICE_LIST_DEFAULT),
			allowed=SELLING_PRICE_LIST_SOURCES,
			label=_("Selling Price List Precedence"),
		)
		self.buying_price_list_precedence = self._normalise_price_list_precedence(
			getattr(self, "buying_price_list_precedence", None)
			or "\n".join(BUYING_PRICE_LIST_DEFAULT),
			allowed=BUYING_PRICE_LIST_SOURCES,
			label=_("Buying Price List Precedence"),
		)

	@staticmethod
	def _normalise_price_list_precedence(value, *, allowed: set[str], label: str) -> str:
		raw = str(value or "").replace(">", "\n").replace(",", "\n")
		keys = [line.strip() for line in raw.splitlines() if line.strip()]
		if not keys:
			frappe.throw(_("{0} must contain at least one Price List source.").format(label))
		unknown = [key for key in keys if key not in allowed]
		if unknown:
			frappe.throw(
				_("{0} contains unsupported source keys: {1}.").format(
					label,
					", ".join(unknown),
				)
			)
		if len(keys) != len(set(keys)):
			frappe.throw(_("{0} cannot contain duplicate source keys.").format(label))
		return "\n".join(keys)

	def _validate_business_expense_posting_workflow_state(self):
		state = str(
			getattr(self, "business_expense_posting_workflow_state", None) or ""
		).strip()
		if not state:
			return
		workflows = frappe.get_all(
			"Workflow",
			filters={
				"document_type": "RetailEdge Business Expense",
				"is_active": 1,
			},
			pluck="name",
			limit=2,
		)
		if len(workflows) != 1:
			frappe.throw(
				_(
					"Workflow State Allowed for Accounting Posting requires exactly one active Business Expense workflow."
				)
			)
		if not frappe.db.exists(
			"Workflow Document State",
			{
				"parent": workflows[0],
				"parenttype": "Workflow",
				"state": state,
				"doc_status": "1",
			},
		):
			frappe.throw(
				_(
					"Workflow State {0} is not a submitted state in the active Business Expense workflow."
				).format(state)
			)


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
			"It operates only at the review layer. "
			"Auto-prepare creates Bank Match Review records. "
			"Auto-confirm confirms Bank Match Review records only. "
			"It does not reconcile Bank Transactions, change Bank Transaction status, create Payment Entries, "
			"create Journal Entries, create GL Entries, mark Sales Invoices as paid, mutate POS shifts, "
			"mutate Daily Sales Audit records, or mutate stock records. "
			"Reconciliation remains a separate controlled process."
		)
