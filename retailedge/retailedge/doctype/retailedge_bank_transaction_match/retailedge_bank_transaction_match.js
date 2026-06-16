frappe.ui.form.on("RetailEdge Bank Transaction Match", {
	refresh(frm) {
		if (!frm.doc.party_type) {
			frm.set_value("party_type", "Customer");
		}

		frm.clear_custom_buttons();
		setSuggestedDocumentQuery(frm);

		if (!frm.is_new()) {
			add_bank_transaction_match_action_buttons(frm);
		}
	},

	party_type(frm) {
		frm.set_value("party", null);
		frm.refresh_field("party");
	},

	bank_transaction(frm) {
		refreshBankTransactionMatchContext(frm, { preserveCandidate: true });
	},

	suggested_document_type(frm) {
		setSuggestedDocumentQuery(frm);
		const clearValues = {
			suggested_document: null,
			sales_invoice: null,
			payment_entry: null,
			candidate_amount: null,
			amount_difference: null,
			amount_scenario: null,
			match_confidence: null,
			match_score: null,
			match_reason: null,
			candidate_posting_date: null,
			payment_event_source: null,
			payment_row_index: null,
			payment_mode: null,
			payment_account: null,
			resolved_payment_account: null,
			account_resolution_status: null,
		};
		frm.set_value(clearValues);
	},

	suggested_document(frm) {
		refreshBankTransactionMatchContext(frm);
	},

	sales_invoice(frm) {
		if (frm.__retailedge_context_sync) {
			return;
		}
		if (frm.doc.sales_invoice && frm.doc.suggested_document_type !== "Sales Invoice") {
			frm.set_value("suggested_document_type", "Sales Invoice");
		}
		if (frm.doc.sales_invoice && frm.doc.suggested_document !== frm.doc.sales_invoice) {
			frm.set_value("suggested_document", frm.doc.sales_invoice);
		}
	},

	payment_entry(frm) {
		if (frm.__retailedge_context_sync) {
			return;
		}
		if (frm.doc.payment_entry && frm.doc.suggested_document_type !== "Payment Entry") {
			frm.set_value("suggested_document_type", "Payment Entry");
		}
		if (frm.doc.payment_entry && frm.doc.suggested_document !== frm.doc.payment_entry) {
			frm.set_value("suggested_document", frm.doc.payment_entry);
		}
	},
});

function setSuggestedDocumentQuery(frm) {
	frm.set_query("suggested_document", function () {
		return {
			filters: {
				docstatus: 1,
			},
		};
	});
}

function refreshBankTransactionMatchContext(frm, options = {}) {
	if (frm.__retailedge_context_sync) {
		return;
	}
	const suggestedDocumentType = frm.doc.suggested_document_type;
	const suggestedDocument = frm.doc.suggested_document || frm.doc.sales_invoice || frm.doc.payment_entry;
	if (!frm.doc.bank_transaction && !(suggestedDocumentType && suggestedDocument)) {
		return;
	}
	frappe.call({
		method:
			"retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.get_bank_transaction_match_form_context",
		args: {
			bank_transaction: frm.doc.bank_transaction,
			suggested_document_type: suggestedDocumentType,
			suggested_document: suggestedDocument,
			sales_invoice: frm.doc.sales_invoice,
			payment_entry: frm.doc.payment_entry,
		},
		freeze: false,
		callback: function (r) {
			const context = (r && r.message) || {};
			if (context.block_reason && suggestedDocumentType && suggestedDocument) {
				frappe.show_alert({ message: __(context.block_reason), indicator: "orange" });
			}
			applyBankTransactionMatchContext(frm, context, options);
		},
	});
}

function applyBankTransactionMatchContext(frm, context, options = {}) {
	frm.__retailedge_context_sync = true;
	const values = {};
	const fields = [
		"company",
		"branch",
		"bank_account",
		"transaction_date",
		"bank_amount",
		"bank_reference",
		"bank_narration",
		"bank_direction",
		"bank_party",
		"resolved_bank_account",
		"suggested_document_type",
		"suggested_document",
		"sales_invoice",
		"payment_entry",
		"customer",
		"party_type",
		"party",
		"candidate_amount",
		"amount_difference",
		"amount_scenario",
		"match_confidence",
		"match_score",
		"match_reason",
		"candidate_posting_date",
		"payment_event_source",
		"payment_row_index",
		"payment_mode",
		"payment_account",
		"resolved_payment_account",
		"account_resolution_status",
		"details_json",
	];
	fields.forEach((fieldname) => {
		if (Object.prototype.hasOwnProperty.call(context, fieldname)) {
			if (options.preserveCandidate && ["suggested_document_type", "suggested_document", "sales_invoice", "payment_entry"].includes(fieldname)) {
				return;
			}
			values[fieldname] = context[fieldname];
		}
	});
	frm.set_value(values).then(() => {
		frm.__retailedge_context_sync = false;
		frm.refresh_fields(fields);
		frm.trigger("refresh");
	});
}

function add_bank_transaction_match_action_buttons(frm) {
	const status = frm.doc.decision_status || "Suggested";
	if (["Suggested", "Reopened"].includes(status)) {
		addBankTransactionMatchButton(frm, __("Confirm Candidate"), "retailedge.api.confirm_bank_transaction_match", __("Confirming candidate..."), __("Confirmed"), __("Review Actions"));
		addBankTransactionMatchButton(
			frm,
			__("Mark Needs Review"),
			"retailedge.api.mark_bank_transaction_match_needs_review",
			__("Marking match for review..."),
			__("Needs Review"),
			__("Review Actions")
		);
		addBankTransactionMatchButton(frm, __("Reject Candidate"), "retailedge.api.reject_bank_transaction_match", __("Rejecting candidate..."), __("Rejected"), __("Review Actions"));
	}

	if (status === "Needs Review") {
		addBankTransactionMatchButton(frm, __("Confirm Candidate"), "retailedge.api.confirm_bank_transaction_match", __("Confirming candidate..."), __("Confirmed"), __("Review Actions"));
		addBankTransactionMatchButton(frm, __("Reject Candidate"), "retailedge.api.reject_bank_transaction_match", __("Rejecting candidate..."), __("Rejected"), __("Review Actions"));
	}

	if (status === "Confirmed") {
		maybe_add_execute_reconciliation_button(frm);

		frm.add_custom_button(__("Check Reconciliation Gate"), function () {
			frappe.call({
				method: "retailedge.api.check_reconciliation_execution_gate",
				args: { match_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Checking execution gate..."),
				callback: function (r) {
					show_reconciliation_gate_result(r.message);
				},
			});
		}, __("Reconciliation"));

		frm.add_custom_button(__("Dry Run Reconciliation"), function () {
			frappe.call({
				method: "retailedge.api.dry_run_reconciliation_for_match",
				args: { match_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Checking reconciliation readiness..."),
				callback: function (r) {
					show_reconciliation_dry_run_result(r.message);
				},
			});
		}, __("Reconciliation"));
		addBankTransactionMatchButton(frm, __("Reopen"), "retailedge.api.reopen_bank_transaction_match", __("Reopening candidate..."), __("Reopened"), __("More Actions"));
		addBankTransactionMatchButton(frm, __("Cancel"), "retailedge.api.cancel_bank_transaction_match", __("Cancelling candidate..."), __("Cancelled"), __("More Actions"));
	}

	if (["Rejected", "Cancelled"].includes(status)) {
		addBankTransactionMatchButton(frm, __("Reopen"), "retailedge.api.reopen_bank_transaction_match", __("Reopening candidate..."), __("Reopened"), __("More Actions"));
	}

	if (frm.page && frm.page.set_inner_btn_group_as_primary) {
		frm.page.set_inner_btn_group_as_primary(__("Review Actions"));
	}
}


function maybe_add_execute_reconciliation_button(frm) {
	if (!frm.doc.name || frm.is_new() || frm.doc.decision_status !== "Confirmed") {
		return;
	}
	frappe.call({
		method: "retailedge.api.check_reconciliation_execution_gate",
		args: { match_name: frm.doc.name },
		freeze: false,
		callback: function (r) {
			const result = (r && r.message) || {};
			if (!result.can_execute) {
				return;
			}
			frm.add_custom_button(__("Execute Reconciliation"), function () {
				frappe.confirm(
					__(
						"This will reconcile the selected Bank Transaction using the confirmed reviewed candidate only. This action is controlled by RetailEdge gates and cannot choose another candidate. Continue?"
					),
					function () {
						frappe.call({
							method: "retailedge.api.execute_reconciliation_for_match",
							args: { match_name: frm.doc.name, confirm: true },
							freeze: true,
							freeze_message: __("Executing reconciliation..."),
							callback: function (response) {
								show_reconciliation_execution_result(response.message);
								frm.reload_doc();
							},
						});
					}
				);
			}, __("Reconciliation"));
		},
	});
}

function addBankTransactionMatchButton(frm, label, method, freezeMessage, title, group) {
	frm.add_custom_button(label, function () {
		frappe.prompt(
			[
				{
					fieldname: "decision_note",
					fieldtype: "Small Text",
					label: __("Decision Note"),
				},
			],
			function (values) {
				frappe.call({
					method,
					args: {
						match_name: frm.doc.name,
						decision_note: values.decision_note || "",
					},
					freeze: true,
					freeze_message: freezeMessage,
					callback: function (r) {
						const message = (r && r.message && r.message.message) || __("Decision updated.");
						frappe.msgprint({
							title,
							message: `${frappe.utils.escape_html(message)}<br><br>${frappe.utils.escape_html(
								__(
									"This action updates only the RetailEdge match decision record. It does not reconcile Bank Transaction, create Payment Entry, post GL, or update Sales Invoice accounting fields."
								)
							)}`,
							indicator: "green",
						});
						frm.reload_doc();
					},
				});
			},
			title,
			__("Apply")
		);
	}, group);
}


function show_reconciliation_dry_run_result(result) {
	if (!result) {
		frappe.msgprint({ title: __("Reconciliation Dry Run"), indicator: "orange", message: __("No dry-run result returned.") });
		return;
	}
	const indicator = result.readiness_group === "Ready" ? "green" : result.readiness_group === "Already Handled" ? "gray" : "orange";
	const rows = [
		[__("Status"), result.readiness_group || result.eligibility_status || ""],
		[__("Review"), result.review_name || ""],
		[__("Bank Transaction"), result.bank_transaction || ""],
		[__("Candidate"), `${result.candidate_doctype || ""} ${result.candidate_name || ""}`.trim()],
		[__("Payment Event"), result.payment_event_identity || ""],
		[__("Bank Amount"), result.bank_amount || 0],
		[__("Candidate Amount"), result.candidate_amount || 0],
		[__("Block Reason"), result.block_reason || ""],
		[__("Safe Next Step"), result.safe_next_step || ""],
	];
	frappe.msgprint({
		title: __("Reconciliation Dry Run"),
		indicator,
		message: frappe.render_template("<table class='table table-bordered'><tbody>{% for row in rows %}<tr><th style='width: 180px'>{{ row[0] }}</th><td>{{ row[1] }}</td></tr>{% endfor %}</tbody></table>", { rows }),
	});
}


function show_reconciliation_gate_result(result) {
	if (!result) {
		frappe.msgprint({ title: __("Reconciliation Execution Gate"), indicator: "orange", message: __("No gate result returned.") });
		return;
	}
	const indicator = result.can_execute ? "green" : result.status === "Settings Disabled" ? "gray" : "orange";
	const reasons = (result.block_reasons || []).map((reason) => `<li>${frappe.utils.escape_html(reason)}</li>`).join("");
	const rows = [
		[__("Gate Status"), result.status || ""],
		[__("Can Execute Later"), result.can_execute ? __("Yes") : __("No")],
		[__("Dry Run Status"), result.dry_run_status || ""],
		[__("Final Confirmation Required"), result.final_confirmation_required ? __("Yes") : __("No")],
		[__("Execution in R5.9"), result.execution_available_in_r59 ? __("Available after confirmation") : __("Not Available")],
		[__("Safe Next Step"), result.safe_next_step || ""],
	];
	frappe.msgprint({
		title: __("Reconciliation Execution Gate"),
		indicator,
		message: `${frappe.render_template("<table class='table table-bordered'><tbody>{% for row in rows %}<tr><th style='width: 220px'>{{ row[0] }}</th><td>{{ row[1] }}</td></tr>{% endfor %}</tbody></table>", { rows })}
			${reasons ? `<p><b>${frappe.utils.escape_html(__("Gate Reasons"))}</b></p><ul>${reasons}</ul>` : ""}`,
	});
}

function show_reconciliation_execution_result(result) {
	if (!result) {
		frappe.msgprint({ title: __("Reconciliation Execution"), indicator: "orange", message: __("No execution result returned.") });
		return;
	}
	const indicator = result.execution_status === "Executed" ? "green" : result.execution_status === "Already Handled" ? "gray" : "orange";
	const rows = [
		[__("Execution Status"), result.execution_status || result.status || ""],
		[__("Review"), result.match_name || ""],
		[__("Bank Transaction"), result.bank_transaction || ""],
		[__("Candidate"), `${result.candidate_doctype || ""} ${result.candidate_name || ""}`.trim()],
		[__("Payment Event"), result.payment_event_identity || ""],
		[__("Dry Run Status"), result.dry_run_status_at_execution || ""],
		[__("Gate Status"), result.gate_status_at_execution || ""],
		[__("Reference"), result.execution_reference || ""],
		[__("Message"), result.message || ""],
		[__("Error"), result.execution_error_summary || ""],
	];
	frappe.msgprint({
		title: __("Reconciliation Execution"),
		indicator,
		message: frappe.render_template("<table class='table table-bordered'><tbody>{% for row in rows %}<tr><th style='width: 220px'>{{ row[0] }}</th><td>{{ row[1] }}</td></tr>{% endfor %}</tbody></table>", { rows }),
	});
}
