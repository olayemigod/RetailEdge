<template>
	<EdgeModal
		:open="open"
		:title="detail?.name ? `Cashier Expense · ${detail.name}` : 'Cashier Expense Details'"
		:subtitle="detail?.company ? `${detail.company}${detail.branch ? ` · ${detail.branch}` : ''}` : 'Review the recorded cashier expense and its posting status.'"
		size="xl"
		@close="$emit('close')"
	>
		<div class="cashier-expense-detail">
			<EdgeLoadingState v-if="loading" message="Loading cashier expense details..." :skeleton="true" />
			<EdgeErrorState
				v-else-if="error"
				title="Cashier Expense unavailable"
				:message="error"
				@retry="loadDetail"
			/>
			<template v-else-if="detail">
				<div class="detail-summary">
					<div>
						<span>Amount</span>
						<strong>{{ formatCurrency(detail.amount) }}</strong>
					</div>
					<div>
						<span>Review Status</span>
						<strong>{{ effectiveReviewStatus }}</strong>
					</div>
					<div>
						<span>Ledger Status</span>
						<strong>{{ detail.ledger_status || "Not Applicable" }}</strong>
					</div>
					<div>
						<span>Posting Ready</span>
						<strong>{{ Number(detail.posting_ready || 0) ? "Yes" : "No" }}</strong>
					</div>
				</div>

				<section class="detail-section">
					<h4>Expense</h4>
					<div class="detail-grid">
						<div><span>Date</span><strong>{{ formatDate(detail.expense_date) }}</strong></div>
						<div><span>Category</span><strong>{{ value(detail.expense_category) }}</strong></div>
						<div><span>Cashier</span><strong>{{ value(detail.cashier) }}</strong></div>
						<div><span>POS Profile</span><strong>{{ value(detail.pos_profile) }}</strong></div>
						<div><span>Company</span><strong>{{ value(detail.company) }}</strong></div>
						<div><span>Branch</span><strong>{{ value(detail.branch) }}</strong></div>
					</div>
					<div v-if="detail.description" class="detail-note">
						<span>Description</span>
						<p>{{ detail.description }}</p>
					</div>
					<a v-if="detail.attachment" class="evidence-link" :href="detail.attachment" target="_blank" rel="noopener noreferrer">
						View receipt / evidence
					</a>
				</section>

				<section class="detail-section">
					<h4>Cash & Shift</h4>
					<div class="detail-grid">
						<div><span>Opening Shift</span><strong>{{ value(detail.linked_pos_opening_shift) }}</strong></div>
						<div><span>Closing Shift</span><strong>{{ value(detail.linked_pos_closing_shift) }}</strong></div>
						<div><span>Opening Cash</span><strong>{{ formatCurrency(detail.shift_opening_cash_amount) }}</strong></div>
						<div><span>Cash Sales</span><strong>{{ formatCurrency(detail.shift_cash_sales_amount) }}</strong></div>
						<div><span>Prior Shift Expenses</span><strong>{{ formatCurrency(detail.prior_shift_expense_amount) }}</strong></div>
						<div><span>Cash Before Expense</span><strong>{{ formatCurrency(detail.available_shift_cash_before_expense) }}</strong></div>
						<div><span>Cash After Expense</span><strong>{{ formatCurrency(detail.available_shift_cash_after_expense) }}</strong></div>
						<div><span>Cash Source</span><strong>{{ value(detail.cash_source || detail.cash_balance_source) }}</strong></div>
					</div>
					<div v-if="detail.cash_control_message" class="detail-note">
						<span>Cash Control</span>
						<p>{{ detail.cash_control_message }}</p>
					</div>
				</section>

				<section class="detail-section">
					<h4>Accounting & Posting</h4>
					<div class="detail-grid">
						<div><span>Expense Account</span><strong>{{ value(detail.expense_account || detail.resolved_debit_account) }}</strong></div>
						<div><span>Payment / Credit Account</span><strong>{{ value(detail.payment_account || detail.resolved_credit_account) }}</strong></div>
						<div><span>Cost Center</span><strong>{{ value(detail.cost_center || detail.resolved_posting_cost_center) }}</strong></div>
						<div><span>Posting Mode</span><strong>{{ value(detail.posting_mode_applied) }}</strong></div>
						<div><span>Posting Reference</span><strong>{{ postingReference }}</strong></div>
						<div><span>Cash Movement</span><strong>{{ value(detail.cash_movement_status) }}</strong></div>
					</div>
					<div v-if="detail.posting_block_reason || detail.user_message" class="detail-note">
						<span>Posting Note</span>
						<p>{{ detail.posting_block_reason || detail.user_message }}</p>
					</div>
				</section>

				<section class="detail-section">
					<h4>Review & Audit</h4>
					<div class="detail-grid">
						<div><span>Daily Audit</span><strong>{{ value(detail.daily_audit_inclusion_status) }}</strong></div>
						<div><span>Classification</span><strong>{{ value(detail.daily_audit_classification) }}</strong></div>
						<div><span>Approved By</span><strong>{{ value(detail.approved_by) }}</strong></div>
						<div><span>Approved On</span><strong>{{ formatDateTime(detail.approved_on) }}</strong></div>
						<div><span>Rejected By</span><strong>{{ value(detail.rejected_by) }}</strong></div>
						<div><span>Rejected On</span><strong>{{ formatDateTime(detail.rejected_on) }}</strong></div>
						<div><span>Audit Reviewed By</span><strong>{{ value(detail.daily_audit_reviewed_by) }}</strong></div>
						<div><span>Audit Reviewed On</span><strong>{{ formatDateTime(detail.daily_audit_reviewed_on) }}</strong></div>
					</div>
					<div v-if="reviewNote" class="detail-note">
						<span>Review Note</span>
						<p>{{ reviewNote }}</p>
					</div>
				</section>

				<section v-if="workflowVisible" class="detail-section workflow-section">
					<div class="workflow-heading">
						<div>
							<h4>Workflow Actions</h4>
							<small>{{ workflowHelper }}</small>
						</div>
						<span v-if="actions.posting_mode" class="workflow-mode">{{ actions.posting_mode }}</span>
					</div>

					<div v-if="actionError" class="workflow-error" role="alert">{{ actionError }}</div>
					<ul v-if="!hasWorkflowActions && actions.reasons?.length" class="workflow-reasons">
						<li v-for="reason in actions.reasons" :key="reason">{{ reason }}</li>
					</ul>

					<div v-if="reviewAction" class="workflow-editor">
						<strong>{{ reviewActionTitle }}</strong>
						<label>
							<span>Remarks{{ reviewRemarksRequired ? " *" : "" }}</span>
							<textarea
								v-model="reviewRemarks"
								class="form-control"
								rows="3"
								:placeholder="reviewRemarksRequired ? 'Reason is required' : 'Optional review note'"
							></textarea>
						</label>
						<div class="workflow-editor-actions">
							<button type="button" class="edge-button" :disabled="actionBusy" @click="cancelReviewAction">Cancel</button>
							<button
								type="button"
								class="edge-button edge-button--primary"
								:disabled="actionBusy || (reviewRemarksRequired && !reviewRemarks.trim())"
								@click="submitReviewAction"
							>
								{{ actionBusy ? "Working..." : reviewActionSubmitLabel }}
							</button>
						</div>
					</div>

					<div v-else class="workflow-buttons">
						<button
							v-for="workflowAction in actions.workflow_actions || []"
							:key="workflowAction.action"
							type="button"
							class="edge-button edge-button--primary"
							:disabled="actionBusy"
							@click="applyWorkflowAction(workflowAction.action)"
						>
							{{ workflowAction.action }}
						</button>
						<button v-if="actions.can_submit_for_review" type="button" class="edge-button edge-button--primary" :disabled="actionBusy" @click="submitForReview">
							{{ actionBusy ? "Working..." : "Submit for Review" }}
						</button>
						<button v-if="actions.can_approve" type="button" class="edge-button edge-button--primary" :disabled="actionBusy" @click="beginReviewAction('approve')">Approve</button>
						<button v-if="actions.can_reject" type="button" class="edge-button" :disabled="actionBusy" @click="beginReviewAction('reject')">Reject</button>
						<button v-if="actions.can_reopen" type="button" class="edge-button" :disabled="actionBusy" @click="beginReviewAction('reopen')">Reopen</button>
						<button v-if="actions.can_refresh_posting" type="button" class="edge-button" :disabled="actionBusy" @click="refreshPostingReadiness">
							{{ actionBusy ? "Working..." : "Refresh Posting Readiness" }}
						</button>
						<button v-if="actions.can_post_to_accounts" type="button" class="edge-button edge-button--primary" :disabled="actionBusy" @click="requestPostToAccounts">
							Post to Accounts
						</button>
					</div>
				</section>

				<div class="detail-actions">
					<button
						v-if="canUseNativeDesk"
						type="button"
						class="edge-button"
						@click="openNativeRecord"
					>
						Advanced: Open Full Record
					</button>
					<button type="button" class="edge-button edge-button--primary" @click="$emit('close')">Close</button>
				</div>
			</template>
		</div>
	</EdgeModal>
</template>

<script>
import { confirmAboveEdgeModal } from "../retailedge_business_hub/guidedEntryUtils";

const DETAIL_METHOD = "retailedge.cashier_expense_detail.get_cashier_expense_detail";
const SUBMIT_FOR_REVIEW_METHOD = "retailedge.cashier_expense_detail.submit_cashier_expense_for_review";
const WORKFLOW_ACTION_METHOD = "retailedge.cashier_expense_detail.apply_cashier_expense_workflow_action";
const REVIEW_METHODS = Object.freeze({
	approve: "retailedge.api.approve_cashier_expense",
	reject: "retailedge.api.reject_cashier_expense",
	reopen: "retailedge.api.reopen_cashier_expense",
});
const REFRESH_POSTING_METHOD = "retailedge.api.refresh_cashier_expense_posting_readiness";
const POST_TO_ACCOUNTS_METHOD = "retailedge.cashier_expense_accounting.post_cashier_expense_to_accounts";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			type,
			callback: (response) => resolve(response.message || {}),
			error: reject,
		});
	});
}

function errorMessage(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback)
		|| error?.message
		|| fallback;
}

export default {
	name: "CashierExpenseDetailDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: {
		open: { type: Boolean, default: false },
		expenseName: { type: String, default: "" },
		company: { type: String, default: "" },
		branch: { type: String, default: "" },
		canUseNativeDesk: { type: Boolean, default: false },
	},
	emits: ["close", "changed"],
	data() {
		return {
			loading: false,
			error: "",
			detail: null,
			actions: {},
			workflow: {},
			loadToken: 0,
			actionBusy: false,
			actionError: "",
			reviewAction: "",
			reviewRemarks: "",
		};
	},
	computed: {
		effectiveReviewStatus() {
			if (!this.detail) return "—";
			if (Number(this.detail.docstatus) === 2 || this.detail.expense_status === "Cancelled") return "Cancelled";
			if (Number(this.detail.docstatus) === 1 && (!this.detail.expense_status || this.detail.expense_status === "Draft")) return "Submitted";
			return this.detail.expense_status || "Draft";
		},
		postingReference() {
			if (!this.detail) return "—";
			return [this.detail.posting_reference_type, this.detail.posting_reference].filter(Boolean).join(" · ") || "—";
		},
		reviewNote() {
			if (!this.detail) return "";
			return this.detail.daily_audit_exclusion_reason
				|| this.detail.daily_audit_note
				|| this.detail.review_remarks
				|| "";
		},
		hasWorkflowActions() {
			return Boolean(
				this.actions.can_submit_for_review
				|| this.actions.can_approve
				|| this.actions.can_reject
				|| this.actions.can_reopen
				|| this.actions.can_refresh_posting
				|| this.actions.can_post_to_accounts
				|| (this.actions.workflow_actions || []).length
			);
		},
		workflowReadiness() {
			return this.workflow || {};
		},
		workflowVisible() {
			return Boolean(this.detail && (this.hasWorkflowActions || this.actions.reasons?.length || this.actionError));
		},
		workflowHelper() {
			if (this.actions.workflow_controlled) return this.workflowReadiness?.message || "Use the merchant-configured Frappe Workflow actions below.";
			if (this.actions.can_submit_for_review) return "Submit this draft into the governed Cashier Expense review workflow.";
			if (this.actions.can_post_to_accounts) return "This expense is ready for ERPNext Journal Entry posting.";
			if (this.actions.posting_enabled && this.detail?.posting_block_reason) return this.detail.posting_block_reason;
			if (this.actions.posting_enabled) return "Review status and posting readiness remain governed by RetailEdge and ERPNext permissions.";
			return "Accounting posting is disabled in RetailEdge Settings.";
		},
		reviewActionTitle() {
			return {
				approve: "Approve Cashier Expense",
				reject: "Reject Cashier Expense",
				reopen: "Reopen Cashier Expense",
			}[this.reviewAction] || "Cashier Expense Review";
		},
		reviewActionSubmitLabel() {
			return {
				approve: "Approve",
				reject: "Reject",
				reopen: "Reopen",
			}[this.reviewAction] || "Apply";
		},
		reviewRemarksRequired() {
			return this.reviewAction === "reject";
		},
	},
	watch: {
		open(next) {
			if (next) this.loadDetail();
			else this.reset();
		},
		expenseName(next, previous) {
			if (this.open && next && next !== previous) this.loadDetail();
		},
	},
	methods: {
		reset() {
			this.loadToken += 1;
			this.loading = false;
			this.error = "";
			this.detail = null;
			this.actions = {};
			this.workflow = {};
			this.actionBusy = false;
			this.actionError = "";
			this.reviewAction = "";
			this.reviewRemarks = "";
		},
		async loadDetail() {
			const expenseName = String(this.expenseName || "").trim();
			if (!this.open || !expenseName) return;
			const token = ++this.loadToken;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod(DETAIL_METHOD, {
					expense_name: expenseName,
					company: this.company || "",
					branch: this.branch || "",
				});
				if (token !== this.loadToken) return;
				this.detail = result.expense || null;
				this.actions = result.actions || {};
				this.workflow = result.workflow_readiness || {};
				if (!this.detail) this.error = "Cashier Expense details were not returned.";
			} catch (error) {
				if (token !== this.loadToken) return;
				this.detail = null;
				this.error = errorMessage(error, "Unable to load Cashier Expense details.");
			} finally {
				if (token === this.loadToken) this.loading = false;
			}
		},
		value(value) {
			return value === null || value === undefined || value === "" ? "—" : String(value);
		},
		formatCurrency(value) {
			const amount = Number(value || 0);
			try {
				return window.retailedge?.formatPlainValue
					? window.retailedge.formatPlainValue(amount, { fieldtype: "Currency" })
					: amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
			} catch (_error) {
				return amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
			}
		},
		formatDate(value) {
			if (!value) return "—";
			try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; }
			catch (_error) { return String(value); }
		},
		formatDateTime(value) {
			if (!value) return "—";
			try { return frappe.datetime.str_to_user(value); }
			catch (_error) { return String(value); }
		},
		async applyWorkflowAction(action) {
			if (!action || !this.detail?.name || this.actionBusy) return;
			await this.runWorkflowAction("workflow", WORKFLOW_ACTION_METHOD, {
				expense_name: this.detail.name,
				action,
				expected_modified: this.detail.modified || null,
				expected_workflow_state: this.workflow?.current_state || "",
			});
		},
		async submitForReview() {
			if (!this.actions.can_submit_for_review || !this.detail?.name || this.actionBusy) return;
			await this.runWorkflowAction("submit-for-review", SUBMIT_FOR_REVIEW_METHOD, {
				expense_name: this.detail.name,
				expected_modified: this.detail.modified || null,
			});
		},
		beginReviewAction(action) {
			if (!REVIEW_METHODS[action]) return;
			this.actionError = "";
			this.reviewAction = action;
			this.reviewRemarks = "";
		},
		cancelReviewAction() {
			if (this.actionBusy) return;
			this.reviewAction = "";
			this.reviewRemarks = "";
			this.actionError = "";
		},
		async submitReviewAction() {
			const action = this.reviewAction;
			const method = REVIEW_METHODS[action];
			if (!method || !this.detail?.name || this.actionBusy) return;
			const remarks = String(this.reviewRemarks || "").trim();
			if (action === "reject" && !remarks) {
				this.actionError = "A rejection reason is required.";
				return;
			}
			await this.runWorkflowAction(action, method, {
				expense_name: this.detail.name,
				remarks,
			});
		},
		async refreshPostingReadiness() {
			if (!this.actions.can_refresh_posting || !this.detail?.name || this.actionBusy) return;
			await this.runWorkflowAction("refresh-posting", REFRESH_POSTING_METHOD, {
				expense_name: this.detail.name,
			});
		},
		requestPostToAccounts() {
			if (!this.actions.can_post_to_accounts || !this.detail?.name || this.actionBusy) return;
			confirmAboveEdgeModal(
				"Create and submit the ERPNext Journal Entry for this Cashier Expense?",
				() => this.postToAccounts()
			);
		},
		async postToAccounts() {
			if (!this.actions.can_post_to_accounts || !this.detail?.name || this.actionBusy) return;
			await this.runWorkflowAction("post-to-accounts", POST_TO_ACCOUNTS_METHOD, {
				expense_name: this.detail.name,
				expected_modified: this.detail.modified || null,
			});
		},
		async runWorkflowAction(action, method, args) {
			this.actionBusy = true;
			this.actionError = "";
			try {
				const result = await callMethod(method, args, "POST");
				this.reviewAction = "";
				this.reviewRemarks = "";
				await this.loadDetail();
				this.$emit("changed", {
					action,
					expense_name: this.detail?.name || args.expense_name,
					result,
				});
			} catch (error) {
				this.actionError = errorMessage(error, "Cashier Expense workflow action failed.");
			} finally {
				this.actionBusy = false;
			}
		},
		openNativeRecord() {
			if (!this.canUseNativeDesk || !this.detail?.name) return;
			this.$emit("close");
			frappe.set_route("Form", "RetailEdge Cashier Expense", this.detail.name);
		},
	},
};
</script>

<style scoped>
.cashier-expense-detail { display:grid; gap:1rem; min-height:12rem; }
.detail-summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.75rem; }
.detail-summary > div,
.detail-grid > div { display:grid; gap:.2rem; min-width:0; }
.detail-summary > div { padding:.8rem; border:1px solid var(--edge-border-color,var(--border-color)); border-radius:.7rem; background:var(--edge-surface-subtle,var(--subtle-fg)); }
.detail-summary span,
.detail-grid span,
.detail-note span { color:var(--text-muted); font-size:.76rem; }
.detail-summary strong { font-size:.95rem; overflow-wrap:anywhere; }
.detail-section { display:grid; gap:.7rem; padding:.9rem; border:1px solid var(--edge-border-color,var(--border-color)); border-radius:.75rem; background:var(--edge-surface,var(--card-bg)); }
.detail-section h4 { margin:0; font-size:.9rem; }
.detail-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.75rem 1rem; }
.detail-grid strong { font-size:.86rem; overflow-wrap:anywhere; }
.detail-note { display:grid; gap:.25rem; padding-top:.2rem; }
.detail-note p { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }
.evidence-link { width:max-content; max-width:100%; overflow-wrap:anywhere; font-weight:600; }
.workflow-section{gap:.8rem}.workflow-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:.8rem}.workflow-heading>div{display:grid;gap:.2rem}.workflow-heading small{color:var(--text-muted);font-size:.76rem}.workflow-mode{padding:.25rem .5rem;border:1px solid var(--edge-border-color,var(--border-color));border-radius:999px;color:var(--text-muted);font-size:.72rem;white-space:nowrap}.workflow-error{padding:.65rem .75rem;border:1px solid var(--red-400,#f04438);border-radius:.5rem;background:var(--red-50,#fef3f2);color:var(--red-700,#b42318)}.workflow-buttons,.workflow-editor-actions{display:flex;gap:.55rem;flex-wrap:wrap}.workflow-reasons{margin:0;padding-left:1.2rem;color:var(--text-muted);font-size:.8rem}.workflow-editor{display:grid;gap:.7rem;padding:.75rem;border:1px solid var(--edge-border-color,var(--border-color));border-radius:.6rem;background:var(--edge-surface-subtle,var(--subtle-fg))}.workflow-editor label{display:grid;gap:.35rem}.workflow-editor label span{font-size:.76rem;color:var(--text-muted)}.workflow-editor-actions{justify-content:flex-end}.detail-actions { display:flex; justify-content:flex-end; gap:.6rem; flex-wrap:wrap; }
@media (max-width:900px) {
	.detail-summary { grid-template-columns:repeat(2,minmax(0,1fr)); }
	.detail-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (max-width:560px) {
	.detail-summary,
	.detail-grid { grid-template-columns:1fr; }
	.detail-actions { flex-direction:column-reverse; }
	.detail-actions .edge-button { width:100%; }
}
</style>
