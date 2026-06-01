function applyRetailEdgeSummaryCardDesign() {
	// Report summary cards are styled through native Frappe DOM selectors in CSS.
}

function scheduleRetailEdgeSummaryCardDesign() {
	// No-op: report summary card appearance is CSS-only.
}

frappe.query_reports["RetailEdge Bank Transaction Matching"] = {
	onload(report) {
		report.page.add_inner_button(__("Create Review Records"), function () {
			open_create_review_records_dialog(report);
		});
		report.page.add_inner_button(__("Run Auto-Match for Visible Results"), function () {
			open_run_auto_match_dialog(report);
		});

		$(document).off("click", ".retailedge-bank-match-review");
		$(document).on("click", ".retailedge-bank-match-review", function () {
			const $btn = $(this);
			frappe.query_reports["RetailEdge Bank Transaction Matching"].open_match_review_dialog({
				bank_transaction: $btn.data("bankTransaction"),
				transaction_date: $btn.data("transactionDate"),
				bank_account: $btn.data("bankAccount"),
				bank_amount: $btn.data("bankAmount"),
				direction: $btn.data("direction"),
				reference: $btn.data("reference"),
				narration: $btn.data("narration"),
				branch: $btn.data("branch"),
				suggested_document_type: $btn.data("suggestedDocumentType"),
				suggested_document: $btn.data("suggestedDocument"),
				sales_invoice: $btn.data("salesInvoice"),
				candidate_amount: $btn.data("candidateAmount"),
				amount_scenario: $btn.data("amountScenario"),
				amount_scenario_label: $btn.data("amountScenarioLabel"),
				sales_invoice_outstanding_amount: $btn.data("salesInvoiceOutstandingAmount"),
				sales_invoice_grand_total: $btn.data("salesInvoiceGrandTotal"),
				payment_entry_paid_amount: $btn.data("paymentEntryPaidAmount"),
				payment_entry_allocated_amount: $btn.data("paymentEntryAllocatedAmount"),
				payment_entry_invoice_context: $btn.data("paymentEntryInvoiceContext"),
				multi_invoice_references: $btn.data("multiInvoiceReferences"),
				amount_difference: $btn.data("amountDifference"),
				match_confidence: $btn.data("matchConfidence"),
				match_score: $btn.data("matchScore"),
				match_reason: $btn.data("matchReason"),
				customer: $btn.data("customer"),
				match_record: $btn.data("matchRecord"),
				match_decision: $btn.data("matchDecision"),
			});
		});

		scheduleRetailEdgeSummaryCardDesign(report);
	},

	after_refresh(report) {
		scheduleRetailEdgeSummaryCardDesign(report);
	},

	open_match_review_dialog(args) {
		const dialog = new frappe.ui.Dialog({
			title: __("Bank Match Review"),
			fields: [
				{
					fieldname: "review_summary",
					fieldtype: "HTML",
				},
				{
					fieldname: "remarks",
					fieldtype: "Small Text",
					label: __("Remarks"),
				},
				{
					fieldname: "confirm_candidate",
					fieldtype: "Button",
					label: __("Confirm Candidate"),
				},
				{
					fieldname: "mark_needs_review",
					fieldtype: "Button",
					label: __("Mark Needs Review"),
				},
				{
					fieldname: "reject_candidate",
					fieldtype: "Button",
					label: __("Reject Candidate"),
				},
				{
					fieldname: "open_match_review",
					fieldtype: "Button",
					label: __("Open Match Review"),
				},
			],
		});

		dialog.show();
		render_bank_match_review_summary(dialog, args);

		dialog.get_field("confirm_candidate").$input.on("click", function () {
			run_bank_match_review_action(dialog, args, {
				action: "confirm",
				method: "retailedge.api.confirm_bank_transaction_match",
				success_message: __("Candidate confirmed. No accounting entries were posted."),
				freeze_message: __("Confirming candidate..."),
			});
		});

		dialog.get_field("mark_needs_review").$input.on("click", function () {
			run_bank_match_review_action(dialog, args, {
				action: "needs_review",
				method: "retailedge.api.mark_bank_transaction_match_needs_review",
				require_remarks: false,
				success_message: __("Candidate marked as Needs Review. No source records were changed."),
				freeze_message: __("Marking candidate for review..."),
			});
		});

		dialog.get_field("reject_candidate").$input.on("click", function () {
			run_bank_match_review_action(dialog, args, {
				action: "reject",
				method: "retailedge.api.reject_bank_transaction_match",
				require_remarks: true,
				success_message: __(
					"Candidate rejected. Bank Transaction remains available for another match."
				),
				freeze_message: __("Rejecting candidate..."),
			});
		});

		dialog.get_field("open_match_review").$input.on("click", function () {
			ensure_bank_match_record(args, function (matchRecord) {
				dialog.hide();
				frappe.set_route("Form", "RetailEdge Bank Transaction Match", matchRecord);
			});
		});
	},

	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname !== "action") {
			return formatted;
		}

		if (!data || !data.bank_transaction) {
			return "";
		}

		return `
			<button type="button"
				class="btn btn-xs btn-default retailedge-bank-match-review"
				data-bank-transaction="${frappe.utils.escape_html(String(data.bank_transaction || ""))}"
				data-transaction-date="${frappe.utils.escape_html(String(data.transaction_date || ""))}"
				data-bank-account="${frappe.utils.escape_html(String(data.bank_account || ""))}"
				data-bank-amount="${frappe.utils.escape_html(String(data.amount || ""))}"
				data-direction="${frappe.utils.escape_html(String(data.direction || ""))}"
				data-reference="${frappe.utils.escape_html(String(data.reference || ""))}"
				data-narration="${frappe.utils.escape_html(String(data.narration || ""))}"
				data-branch="${frappe.utils.escape_html(String(data.branch || ""))}"
				data-suggested-document-type="${frappe.utils.escape_html(String(data.suggested_document_type || ""))}"
				data-suggested-document="${frappe.utils.escape_html(String(data.suggested_document || ""))}"
				data-sales-invoice="${frappe.utils.escape_html(String(data.suggested_sales_invoice || ""))}"
				data-candidate-amount="${frappe.utils.escape_html(String(data.candidate_amount || ""))}"
				data-amount-difference="${frappe.utils.escape_html(String(data.amount_difference || ""))}"
				data-amount-scenario="${frappe.utils.escape_html(String(data.amount_scenario || ""))}"
				data-amount-scenario-label="${frappe.utils.escape_html(String(data.amount_scenario_label || data.amount_scenario || ""))}"
				data-sales-invoice-outstanding-amount="${frappe.utils.escape_html(String(data.sales_invoice_outstanding_amount || ""))}"
				data-sales-invoice-grand-total="${frappe.utils.escape_html(String(data.sales_invoice_grand_total || ""))}"
				data-payment-entry-paid-amount="${frappe.utils.escape_html(String(data.payment_entry_paid_amount || ""))}"
				data-payment-entry-allocated-amount="${frappe.utils.escape_html(String(data.payment_entry_allocated_amount || ""))}"
				data-payment-entry-invoice-context="${frappe.utils.escape_html(String(data.payment_entry_invoice_context || ""))}"
				data-multi-invoice-references="${frappe.utils.escape_html(String(data.multi_invoice_references || ""))}"
				data-match-confidence="${frappe.utils.escape_html(String(data.match_confidence || ""))}"
				data-match-score="${frappe.utils.escape_html(String(data.match_score || ""))}"
				data-match-reason="${frappe.utils.escape_html(String(data.match_reason || ""))}"
				data-customer="${frappe.utils.escape_html(String(data.customer || ""))}"
				data-match-record="${frappe.utils.escape_html(String(data.match_record || ""))}"
				data-match-decision="${frappe.utils.escape_html(String(data.decision_status || ""))}">
				${frappe.utils.escape_html(__("Review"))}
			</button>
		`;
	},

	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "bank_account",
			label: __("Bank Account"),
			fieldtype: "Link",
			options: "Bank Account",
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "match_confidence",
			label: __("Match Confidence"),
			fieldtype: "Select",
			options: "\nStrong Match\nPossible Match\nWeak Match\nNo Match",
		},
		{
			fieldname: "amount_scenario",
			label: __("Amount Scenario"),
			fieldtype: "Select",
			options:
				"\nExact Outstanding Amount\nExact Invoice Amount\nPartial Payment\nOverpayment / Advance\nAmount Variance\nMulti-Invoice Payment\nSubmitted Payment Entry Amount\nPayment Entry Allocated Amount\nPayment Entry Amount Variance",
		},
		{
			fieldname: "customer",
			label: __("Customer / Party"),
			fieldtype: "Data",
		},
		{
			fieldname: "suggested_document_type",
			label: __("Candidate Type"),
			fieldtype: "Select",
			options: "\nSales Invoice\nPayment Entry",
		},
		{
			fieldname: "suggested_document",
			label: __("Suggested Document"),
			fieldtype: "Data",
		},
		{
			fieldname: "action_status",
			label: __("Action Status"),
			fieldtype: "Select",
			options:
				"\nSuggested\nNeeds Review\nNo Match\nDuplicate Candidate\nException Only\nExisting Active Review\nAlready Reconciled\nAlready Bank Verified\nAlready Confirmed\nOutflow / Not Sales Receipt\nRejected\nReopened\nCancelled",
		},
		{
			fieldname: "auto_match_status",
			label: __("Auto-Match Status"),
			fieldtype: "Select",
			options:
				"\nEligible for Auto-Prepare\nEligible for Auto-Confirm\nBlocked from Auto-Match\nNeeds Manual Review\nAuto Prepared\nAuto Confirmed",
		},
		{
			fieldname: "exception_status",
			label: __("Exception Status"),
			fieldtype: "Select",
			options: "\nException Only\nNormal Candidate",
		},
		{
			fieldname: "duplicate_candidate_status",
			label: __("Duplicate Candidate Status"),
			fieldtype: "Select",
			options: "\nDuplicate Candidate\nNot Duplicate Candidate",
		},
		{
			fieldname: "already_reviewed_status",
			label: __("Review Record Status"),
			fieldtype: "Select",
			options: "\nHas Review Record\nNo Review Record",
		},
		{
			fieldname: "review_queue_status",
			label: __("Review Queue Status"),
			fieldtype: "Select",
			options: "Open Suggestions Only\nAlready In Review\nConfirmed\nAll",
			default: "Open Suggestions Only",
		},
		{
			fieldname: "only_unmatched",
			label: __("Only Unmatched"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "include_reconciled",
			label: __("Include Reconciled"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "include_verified_invoices",
			label: __("Include Verified Invoices"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "include_confirmed_matches",
			label: __("Include Confirmed Matches"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "include_rejected_candidates",
			label: __("Include Rejected Candidates"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "include_exception_candidates",
			label: __("Show Date/Account Exceptions"),
			fieldtype: "Check",
			default: 0,
		},
	],
};

function format_currency_value(value) {
	if (value === undefined || value === null || value === "") {
		return __("Amount not available");
	}

	return format_currency(value, frappe.defaults.get_default("currency"));
}

function format_match_label(amount, label, suffix) {
	const formatted_amount = format_currency_value(amount);
	return `(${formatted_amount}) ${label || ""}${suffix ? " — " + suffix : ""}`.trim();
}

function amount_scenario_label(value) {
	const labels = {
		"Exact Outstanding Amount": __("Exact Outstanding Match"),
		"exact_outstanding_match": __("Exact Outstanding Match"),
		"Partial Payment": __("Partial Payment"),
		"partial_payment": __("Partial Payment"),
		"Overpayment / Advance": __("Overpayment / Advance"),
		"overpayment": __("Overpayment / Advance"),
		"Amount Variance": __("Amount Variance"),
		"Payment Entry Amount Variance": __("Amount Variance"),
		"Multi-Invoice Payment": __("Multi-Invoice Payment"),
		"Payment Entry Allocated Amount": __("Payment Entry with Invoice Allocation"),
		"Submitted Payment Entry Amount": __("Submitted Payment Entry Amount"),
	};
	return labels[value] || value || "";
}

function add_summary_section(title, rows) {
	const ui = window.retailedge && window.retailedge.ui;
	const visibleRows = rows.filter((row) => row[1] !== undefined && row[1] !== null && row[1] !== "");
	if (!visibleRows.length) {
		return "";
	}
	if (ui && ui.renderKeyValueSection) {
		return ui.renderKeyValueSection(title, visibleRows, {
			value: __("Review Details"),
			tone: "info",
		});
	}
	return "";
}

function render_bank_match_review_summary(dialog, args) {
	const scenarioLabel = args.amount_scenario_label || amount_scenario_label(args.amount_scenario);
	const suggestedLabel = args.suggested_document
		? build_readable_suggested_document_label(args)
		: __("No suggestion available");
	const matchRecordLabel = args.match_record
		? `${args.match_record} (${__("Bank Amount")}: ${format_currency_value(args.bank_amount)} | ${__("Suggested Amount")}: ${format_currency_value(
				args.candidate_amount
		  )})${args.match_decision ? " — " + args.match_decision : ""}`
		: __("Not yet created");
	const context = build_match_context_summary(args);
	const ui = window.retailedge && window.retailedge.ui;
	const tone = ui ? ui.inferTone(args.match_confidence || args.match_decision || args.action_status, args.match_reason) : "info";
	const sections = [
		add_summary_section(__("Bank Transaction"), [
			[__("Bank Transaction ID"), args.bank_transaction || ""],
			[__("Transaction Date"), args.transaction_date || ""],
			[__("Bank Account"), args.bank_account || ""],
			[__("Bank Amount"), format_currency_value(args.bank_amount)],
			[__("Direction"), args.direction || ""],
			[__("Reference"), args.reference || ""],
			[__("Narration / Description"), args.narration || ""],
			[__("Branch"), args.branch || ""],
		]),
		add_summary_section(__("Suggested Match"), [
			[__("Suggested Document"), suggestedLabel],
			[__("Candidate Type"), args.suggested_document_type || ""],
			[__("Sales Invoice"), args.sales_invoice || ""],
			[__("Current Match Record"), matchRecordLabel],
		]),
		add_summary_section(__("Amount Breakdown"), [
			[__("Bank Amount"), format_currency_value(args.bank_amount)],
			[__("Suggested Match Amount"), format_currency_value(args.candidate_amount)],
			[__("Sales Invoice Outstanding"), args.sales_invoice_outstanding_amount ? format_currency_value(args.sales_invoice_outstanding_amount) : ""],
			[__("Sales Invoice Total"), args.sales_invoice_grand_total ? format_currency_value(args.sales_invoice_grand_total) : ""],
			[__("Payment Entry Paid Amount"), args.payment_entry_paid_amount ? format_currency_value(args.payment_entry_paid_amount) : ""],
			[__("Payment Entry Allocated Amount"), args.payment_entry_allocated_amount ? format_currency_value(args.payment_entry_allocated_amount) : ""],
			[__("Difference / Variance"), format_currency_value(args.amount_difference)],
			[__("Scenario"), scenarioLabel],
			[__("Match Confidence"), args.match_confidence || ""],
			[__("Match Score"), args.match_score || ""],
			[__("Issue / Reason"), args.match_reason || ""],
		]),
		context,
	].filter(Boolean);

	dialog.get_field("review_summary").$wrapper.html(
		`<div class="retailedge-dialog-content">${ui && ui.renderCard
			? ui.renderCard({
					title: __("RetailEdge Match Review"),
					value: suggestedLabel,
					badge: args.match_confidence || args.match_decision || __("Needs Review"),
					tone,
					meta: [
						args.branch || "",
						args.bank_account || "",
						scenarioLabel || "",
					].filter(Boolean),
					footer: __("This review changes only the RetailEdge decision state."),
				})
			: ""}${sections.join("")}</div>`
	);
}

function build_readable_suggested_document_label(args) {
	if (args.suggested_document_type === "Sales Invoice") {
		const amounts = [];
		if (args.sales_invoice_outstanding_amount) {
			amounts.push(`${__("Outstanding")}: ${format_currency_value(args.sales_invoice_outstanding_amount)}`);
		}
		if (args.sales_invoice_grand_total) {
			amounts.push(`${__("Invoice Total")}: ${format_currency_value(args.sales_invoice_grand_total)}`);
		}
		return `${args.suggested_document}${args.customer ? " — " + args.customer : ""}${amounts.length ? " (" + amounts.join(" | ") + ")" : ""}`;
	}
	if (args.suggested_document_type === "Payment Entry") {
		const amounts = [];
		if (args.payment_entry_paid_amount) {
			amounts.push(`${__("Paid")}: ${format_currency_value(args.payment_entry_paid_amount)}`);
		}
		if (args.payment_entry_allocated_amount) {
			amounts.push(`${__("Allocated")}: ${format_currency_value(args.payment_entry_allocated_amount)}`);
		}
		return `${__("Payment Entry")} ${args.suggested_document}${args.customer ? " — " + args.customer : ""}${
			amounts.length ? " (" + amounts.join(" | ") + ")" : ""
		}`;
	}
	return format_match_label(args.candidate_amount, args.suggested_document, args.customer || "");
}

function build_match_context_summary(args) {
	const rows = [];
	if (args.payment_entry_invoice_context) {
		rows.push([__("Payment Entry Invoice Context"), args.payment_entry_invoice_context]);
	}
	if (args.multi_invoice_references) {
		rows.push([__("Possible Multi-Invoice Payment"), args.multi_invoice_references]);
	}
	return add_summary_section(__("Invoice / Allocation Context"), rows);
}

function run_bank_match_review_action(dialog, args, options) {
	const remarks = dialog.get_value("remarks") || "";
	if (options.require_remarks && !String(remarks).trim()) {
		frappe.msgprint(__("Remarks are required for Reject Candidate."));
		return;
	}

	ensure_bank_match_record(args, function (matchRecord) {
		frappe.call({
			method: options.method,
			args: {
				match_name: matchRecord,
				decision_note: remarks,
			},
			freeze: true,
			freeze_message: options.freeze_message,
			callback: function () {
				dialog.hide();
				frappe.show_alert({
					message: options.success_message,
					indicator: "green",
				});
				frappe.query_report.refresh();
			},
		});
	});
}

function ensure_bank_match_record(args, callback) {
	if (args.match_record) {
		callback(args.match_record);
		return;
	}

	frappe.call({
		method: "retailedge.api.create_bank_transaction_match_from_suggestion",
		args: {
			bank_transaction_name: args.bank_transaction,
			suggested_document_type: args.suggested_document_type,
			suggested_document: args.suggested_document,
			sales_invoice: args.sales_invoice,
			force_refresh: 1,
		},
		freeze: true,
		freeze_message: __("Creating RetailEdge match review record..."),
		callback: function (r) {
			const result = r && r.message;
			if (!result || !result.name) {
				frappe.msgprint(__("RetailEdge could not create a match review record for this row."));
				return;
			}
			args.match_record = result.name;
			callback(result.name);
		},
	});
}

function open_create_review_records_dialog(report) {
	const selection = get_report_suggestion_rows(report, { eligibleOnly: true });
	if (!selection.rows.length) {
		frappe.msgprint(__("No eligible suggested rows are visible in the report."));
		return;
	}

	const sourceLabel = selection.used_selection
		? __("selected report rows")
		: __("currently visible eligible report rows");
	const warning = __(
		"This creates RetailEdge Bank Match Review records only. It does not reconcile Bank Transactions, create Payment Entries, post Journal Entries or GL Entries, or update Sales Invoice accounting/payment fields."
	);
	const message = `
		<p>${frappe.utils.escape_html(
			__("Create review records for {0} {1}?", [selection.rows.length, sourceLabel])
		)}</p>
		<p>${frappe.utils.escape_html(warning)}</p>
		${
			selection.used_selection
				? ""
				: `<p class="text-muted">${frappe.utils.escape_html(
						__("No selected rows were detected, so RetailEdge will use the currently visible eligible rows.")
				  )}</p>`
		}
	`;

	frappe.confirm(message, function () {
		frappe.call({
			method: "retailedge.api.create_bank_match_reviews_from_suggestions",
			args: {
				filters: JSON.stringify(frappe.query_report.get_filter_values()),
				rows: JSON.stringify(selection.rows),
			},
			freeze: true,
			freeze_message: __("Creating RetailEdge match review records..."),
			callback: function (r) {
				show_create_review_records_summary((r && r.message) || {});
				frappe.query_report.refresh();
			},
		});
	});
}

function open_run_auto_match_dialog(report) {
	const selection = get_report_suggestion_rows(report, { eligibleOnly: false });
	if (!selection.rows.length) {
		frappe.msgprint(__("No candidate suggestion rows are visible in the report."));
		return;
	}

	const sourceLabel = selection.used_selection
		? __("selected report rows")
		: __("currently visible filtered report rows");
	const message = `
		<p>${frappe.utils.escape_html(
			__("Run auto-match for {0} {1}?", [selection.rows.length, sourceLabel])
		)}</p>
		<p>${frappe.utils.escape_html(
			__(
				"This will only create or confirm RetailEdge Bank Match Review records for strict exact matches allowed by RetailEdge Settings. It will not reconcile Bank Transactions, change Bank Transaction status, create Payment Entries, create Journal Entries, create GL Entries, or mark Sales Invoices as paid."
			)
		)}</p>
		<p>${frappe.utils.escape_html(
			__(
				"Unsafe or manual-review scenarios such as partial payments, amount variance, duplicate candidates, and date/account exceptions will be skipped or blocked."
			)
		)}</p>
		${
			selection.used_selection
				? ""
				: `<p class="text-muted">${frappe.utils.escape_html(
						__("No selected rows were detected, so RetailEdge will use only the currently visible filtered rows.")
				  )}</p>`
		}
	`;

	frappe.confirm(message, function () {
		frappe.call({
			method: "retailedge.api.run_bank_transaction_auto_match",
			args: {
				filters: JSON.stringify(frappe.query_report.get_filter_values()),
				rows: JSON.stringify(selection.rows),
			},
			freeze: true,
			freeze_message: __("Running RetailEdge auto-match..."),
			callback: function (r) {
				show_auto_match_summary((r && r.message) || {});
				frappe.query_report.refresh();
			},
		});
	});
}

function get_report_suggestion_rows(report, options) {
	const config = options || {};
	const rawData = (report && report.data) || frappe.query_report.data || [];
	const rowFilter = config.eligibleOnly ? is_eligible_report_suggestion_row : is_report_candidate_row;
	const data = rawData.filter(rowFilter);
	const selectedIndexes = get_selected_report_row_indexes(report);
	const selectedRows = selectedIndexes
		.map((index) => rawData[index])
		.filter(rowFilter);

	if (selectedRows.length) {
		return { rows: selectedRows.map(clean_report_suggestion_row), used_selection: true };
	}
	return { rows: data.map(clean_report_suggestion_row), used_selection: false };
}

function get_selected_report_row_indexes(report) {
	const datatable = (report && report.datatable) || frappe.query_report.datatable;
	const rowmanager = datatable && datatable.rowmanager;
	if (!rowmanager) {
		return [];
	}
	let checkedRows = [];
	if (typeof rowmanager.getCheckedRows === "function") {
		checkedRows = rowmanager.getCheckedRows() || [];
	} else if (typeof rowmanager.getCheckedRowIndices === "function") {
		checkedRows = rowmanager.getCheckedRowIndices() || [];
	}
	return checkedRows
		.map((row) => (typeof row === "number" ? row : row && (row.rowIndex ?? row.index)))
		.filter((rowIndex) => rowIndex !== undefined && rowIndex !== null);
}

function is_eligible_report_suggestion_row(row) {
	if (!is_report_candidate_row(row)) {
		return false;
	}
	if (row.decision_status === "Confirmed" || row.action_status === "Already Confirmed") {
		return false;
	}
	if (["No Match", "Outflow / Not Sales Receipt", "Duplicate Candidate", "Exception Only"].includes(row.action_status)) {
		return false;
	}
	return ["Sales Invoice", "Payment Entry"].includes(row.suggested_document_type);
}

function is_report_candidate_row(row) {
	if (!row || !row.bank_transaction || !row.suggested_document || !row.suggested_document_type) {
		return false;
	}
	return ["Sales Invoice", "Payment Entry"].includes(row.suggested_document_type);
}

function clean_report_suggestion_row(row) {
	return {
		bank_transaction: row.bank_transaction,
		transaction_date: row.transaction_date,
		bank_account: row.bank_account,
		reference: row.reference,
		narration: row.narration,
		branch: row.branch,
		direction: row.direction,
		amount: row.amount,
		bank_amount: row.amount,
		suggested_document_type: row.suggested_document_type,
		suggested_document: row.suggested_document,
		suggested_sales_invoice: row.suggested_sales_invoice,
		customer: row.customer,
		candidate_amount: row.candidate_amount,
		amount_difference: row.amount_difference,
		amount_scenario: row.amount_scenario,
		amount_scenario_label: row.amount_scenario_label,
		sales_invoice_outstanding_amount: row.sales_invoice_outstanding_amount,
		sales_invoice_grand_total: row.sales_invoice_grand_total,
		payment_entry_paid_amount: row.payment_entry_paid_amount,
		payment_entry_allocated_amount: row.payment_entry_allocated_amount,
		payment_entry_invoice_context: row.payment_entry_invoice_context,
		multi_invoice_references: row.multi_invoice_references,
		exception_only: row.exception_only,
		exception_type: row.exception_type,
		match_confidence: row.match_confidence,
		match_score: row.match_score,
		match_reason: row.match_reason,
		action_status: row.action_status,
		decision_status: row.decision_status,
		match_record: row.match_record,
		reference_match_exact: row.reference_match_exact,
		account_match: row.account_match,
		branch_match: row.branch_match,
		auto_match_status: row.auto_match_status,
		auto_match_reason: row.auto_match_reason,
	};
}

function show_create_review_records_summary(result) {
	const ui = window.retailedge && window.retailedge.ui;
	const rows = [
		[__("Selected / Visible Rows"), result.total_selected || 0],
		[__("Created"), result.created_count || 0],
		[__("Duplicate Candidate Suggestions"), result.duplicate_candidate_skipped_count || 0],
		[__("Duplicates"), result.duplicate_count || 0],
		[__("Already Matched"), result.already_matched_count || 0],
		[__("Unsafe / Skipped"), result.unsafe_count || 0],
		[__("Errors"), result.error_count || 0],
	];
	const reasonList = (result.reasons || [])
		.slice(0, 8)
		.map((row) => `<li>${frappe.utils.escape_html(row.reason || "")}: ${frappe.utils.escape_html(String(row.count || 0))}</li>`)
		.join("");
	const created = result.created || [];
	const createdList = created
		.slice(0, 10)
		.map((row) => row.match_record || row.suggested_document || row.bank_transaction || "");

	const message = ui
		? `<div class="retailedge-dialog-content">
				${result.message ? ui.renderEmptyState(result.message) : ""}
				${ui.renderCardGrid([
					{
						title: __("Review Records"),
						value: String(result.created_count || 0),
						badge: result.created_count ? __("Ready") : __("Needs Review"),
						tone: result.error_count ? "warning" : "success",
						meta: [
							`${__("Selected / Visible Rows")}: ${result.total_selected || 0}`,
							`${__("Created")}: ${result.created_count || 0}`,
							`${__("Already Matched")}: ${result.already_matched_count || 0}`,
						],
						footer: __("Open Bank Match Review to continue reviewer decisions."),
					},
					{
						title: __("Duplicates & Unsafe"),
						value: String((result.duplicate_candidate_skipped_count || 0) + (result.duplicate_count || 0) + (result.unsafe_count || 0)),
						badge: result.unsafe_count ? __("Blocked") : __("Possible Match"),
						tone: result.unsafe_count ? "danger" : "warning",
						meta: [
							`${__("Duplicate Candidate Suggestions")}: ${result.duplicate_candidate_skipped_count || 0}`,
							`${__("Duplicates")}: ${result.duplicate_count || 0}`,
							`${__("Unsafe / Skipped")}: ${result.unsafe_count || 0}`,
						],
						footer: __("Duplicate candidate rows remain informational until a reviewer confirms the safe path."),
					},
					{
						title: __("Errors"),
						value: String(result.error_count || 0),
						badge: result.error_count ? __("Needs Review") : __("Clear"),
						tone: result.error_count ? "danger" : "success",
						meta: [`${__("Errors")}: ${result.error_count || 0}`],
						footer: __("No accounting entries were posted."),
					},
				])}
				${createdList.length
					? ui.renderListCard(__("Created Records"), createdList, {
							value: `${createdList.length}`,
							badge: __("Matched"),
							tone: "success",
					  })
					: ""}
				${(result.reasons || []).length
					? ui.renderListCard(
							__("Grouped Reasons"),
							(result.reasons || []).slice(0, 8).map((row) => `${row.reason || ""}: ${String(row.count || 0)}`),
							{
								value: `${(result.reasons || []).length}`,
								badge: __("Needs Review"),
								tone: "warning",
							}
					  )
					: ""}
			</div>`
		: "";

	frappe.msgprint({
		title: __("Review Record Creation Summary"),
		message:
			message ||
			`${rows
				.map(([label, value]) => `<p><strong>${frappe.utils.escape_html(label)}</strong>: ${frappe.utils.escape_html(String(value))}</p>`)
				.join("")}${reasonList ? `<ul>${reasonList}</ul>` : ""}`,
		primary_action: {
			label: __("Open Bank Match Review"),
			action: function () {
				frappe.set_route("List", "RetailEdge Bank Transaction Match");
			},
		},
	});
}

function show_auto_match_summary(result) {
	const ui = window.retailedge && window.retailedge.ui;
	const reasonList = (result.reasons || [])
		.slice(0, 10)
		.map((row) => `<li>${frappe.utils.escape_html(row.reason || "")}: ${frappe.utils.escape_html(String(row.count || 0))}</li>`)
		.join("");
	const message = ui
		? `<div class="retailedge-dialog-content">
				${result.message ? ui.renderEmptyState(result.message) : ""}
				${ui.renderCardGrid([
					{
						title: __("Auto Prepared"),
						value: String(result.auto_prepared_count || 0),
						badge: __("Prepared"),
						tone: "info",
						meta: [
							`${__("Checked")}: ${result.checked_count || 0}`,
							`${__("Auto Prepared")}: ${result.auto_prepared_count || 0}`,
							`${__("Auto Confirmed")}: ${result.auto_confirmed_count || 0}`,
						],
						footer: __("Auto Prepared means the RetailEdge review record was created automatically only."),
					},
					{
						title: __("Blocked / Manual Review"),
						value: String(result.manual_review_count || 0),
						badge: __("Needs Review"),
						tone: "warning",
						meta: [
							`${__("Already Confirmed")}: ${result.already_confirmed_count || 0}`,
							`${__("Duplicate Candidates")}: ${result.duplicate_candidate_skipped_count || 0}`,
							`${__("Existing Review Records")}: ${result.review_record_exists_count || 0}`,
						],
						footer: __("Unsafe scenarios remain manual and are not auto-confirmed."),
					},
					{
						title: __("Auto Confirmed"),
						value: String(result.auto_confirmed_count || 0),
						badge: result.auto_confirmed_count ? __("Confirmed") : __("Disabled"),
						tone: result.auto_confirmed_count ? "success" : "info",
						meta: [`${__("Errors")}: ${result.error_count || 0}`],
						footer: __("Auto Confirmed means the RetailEdge review record was confirmed automatically only. It is still not ERPNext bank reconciliation."),
					},
				])}
				${(result.reasons || []).length
					? ui.renderListCard(
							__("Grouped Reasons"),
							(result.reasons || []).slice(0, 10).map((row) => `${row.reason || ""}: ${String(row.count || 0)}`),
							{
								value: `${(result.reasons || []).length}`,
								badge: __("Needs Review"),
								tone: "warning",
							}
					  )
					: ""}
			</div>`
		: "";

	frappe.msgprint({
		title: __("RetailEdge Auto-Match Summary"),
		message:
			message ||
			`<p>${frappe.utils.escape_html(result.message || "")}</p>${reasonList ? `<ul>${reasonList}</ul>` : ""}`,
		primary_action: {
			label: __("Open Bank Match Review"),
			action: function () {
				frappe.set_route("List", "RetailEdge Bank Transaction Match");
			},
		},
	});
}
