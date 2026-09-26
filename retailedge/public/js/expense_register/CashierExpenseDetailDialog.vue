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

				<section class="detail-section workflow-section">
					<h4>Workflow</h4>
					<div v-if="workflow.posting_preview" class="detail-note">
						<span>Posting Preview</span>
						<p>{{ workflow.posting_preview }}</p>
					</div>
					<label v-if="hasReviewActions" class="workflow-remarks">
						<span>Review Remarks</span>
						<textarea
							v-model="workflowRemarks"
							class="form-control"
							rows="3"
							placeholder="Optional review note or reason"
						></textarea>
					</label>
					<div v-if="actionError" class="workflow-error" role="alert">{{ actionError }}</div>
					<div class="workflow-actions">
						<button
							v-if="capabilities.can_submit"
							type="button"
							class="edge-button edge-button--primary"
							:disabled="Boolean(actionRunning)"
							@click="applyWorkflowAction('submit')"
						>
							{{ actionRunning === "submit" ? "Submitting…" : "Submit Expense" }}
						</button>
						<button
							v-if="capabilities.can_approve"
							type="button"
							class="edge-button edge-button--primary"
							:disabled="Boolean(actionRunning)"
							@click="applyWorkflowAction('approve')"
						>
							{{ actionRunning === "approve" ? "Approving…" : "Approve" }}
						</button>
						<button
							v-if="capabilities.can_reject"
							type="button"
							class="edge-button workflow-danger"
							:disabled="Boolean(actionRunning)"
							@click="applyWorkflowAction('reject')"
						>
							{{ actionRunning === "reject" ? "Rejecting…" : "Reject" }}
						</button>
						<button
							v-if="capabilities.can_reopen"
							type="button"
							class="edge-button"
							:disabled="Boolean(actionRunning)"
							@click="applyWorkflowAction('reopen')"
						>
							{{ actionRunning === "reopen" ? "Reopening…" : "Reopen" }}
						</button>
						<button
							v-if="capabilities.can_refresh_posting"
							type="button"
							class="edge-button"
							:disabled="Boolean(actionRunning)"
							@click="applyWorkflowAction('refresh_posting')"
						>
							{{ actionRunning === "refresh_posting" ? "Refreshing…" : "Refresh Posting Readiness" }}
						</button>
						<button
							v-if="capabilities.can_post_accounts"
							type="button"
							class="edge-button edge-button--primary"
							:disabled="Boolean(actionRunning)"
							@click="applyWorkflowAction('post_accounts')"
						>
							{{ actionRunning === "post_accounts" ? "Posting…" : "Post Journal Entry" }}
						</button>
					</div>
				</section>

				<div class="detail-actions">
					<button type="button" class="edge-button edge-button--primary" @click="$emit('close')">Close</button>
				</div>
			</template>
		</div>
	</EdgeModal>
</template>

<script>
const DETAIL_METHOD = "retailedge.cashier_expense_detail.get_cashier_expense_detail";
const ACTION_METHOD = "retailedge.cashier_expense_detail.apply_cashier_expense_workflow_action";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: reject,
		});
	});
}

function errorMessage(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback)
		|| error?.message
		|| error?.exc
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
	},
	emits: ["close", "updated"],
	data() {
		return {
			loading: false,
			error: "",
			detail: null,
			workflow: { capabilities: {} },
			workflowRemarks: "",
			actionRunning: "",
			actionError: "",
			loadToken: 0,
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
		capabilities() {
			return this.workflow?.capabilities || {};
		},
		hasReviewActions() {
			return Boolean(
				this.capabilities.can_approve
				|| this.capabilities.can_reject
				|| this.capabilities.can_reopen
			);
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
			this.workflow = { capabilities: {} };
			this.workflowRemarks = "";
			this.actionRunning = "";
			this.actionError = "";
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
				this.workflow = result.workflow || { capabilities: {} };
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
			if (!this.detail?.name || this.actionRunning) return;
			this.actionRunning = action;
			this.actionError = "";
			try {
				const result = await callMethod(ACTION_METHOD, {
					expense_name: this.detail.name,
					action,
					remarks: this.workflowRemarks || "",
					expected_modified: this.detail.modified || "",
					company: this.company || "",
					branch: this.branch || "",
				});
				this.detail = result.expense || this.detail;
				this.workflow = result.workflow || { capabilities: {} };
				if (["approve", "reject", "reopen"].includes(action)) this.workflowRemarks = "";
				this.$emit("updated", this.detail);
				frappe.show_alert?.({
					message: __("Cashier Expense workflow updated."),
					indicator: "green",
				});
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to update the Cashier Expense workflow.");
			} finally {
				this.actionRunning = "";
			}
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
.detail-actions { display:flex; justify-content:flex-end; gap:.6rem; flex-wrap:wrap; }
.workflow-section { gap:.8rem; }
.workflow-remarks { display:grid; gap:.35rem; }
.workflow-remarks > span { color:var(--text-muted); font-size:.76rem; }
.workflow-actions { display:flex; gap:.55rem; flex-wrap:wrap; align-items:center; }
.workflow-error { padding:.65rem .75rem; border:1px solid var(--edge-danger,#d92d20); border-radius:.55rem; color:var(--edge-danger,#b42318); background:var(--edge-danger-subtle,#fef3f2); }
.workflow-danger { border-color:var(--edge-danger,#d92d20); color:var(--edge-danger,#b42318); }
@media (max-width:900px) {
	.detail-summary { grid-template-columns:repeat(2,minmax(0,1fr)); }
	.detail-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (max-width:560px) {
	.detail-summary,
	.detail-grid { grid-template-columns:1fr; }
	.detail-actions { flex-direction:column-reverse; }
	.detail-actions .edge-button,
	.workflow-actions .edge-button { width:100%; }
}
</style>
