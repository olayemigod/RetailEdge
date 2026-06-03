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
