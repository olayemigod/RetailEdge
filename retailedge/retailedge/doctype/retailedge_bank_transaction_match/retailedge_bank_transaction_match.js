frappe.ui.form.on("RetailEdge Bank Transaction Match", {
	refresh(frm) {
		if (!frm.doc.party_type) {
			frm.set_value("party_type", "Customer");
		}

		frm.clear_custom_buttons();

		if (frm.is_new()) {
			return;
		}

		add_bank_transaction_match_action_buttons(frm);
	},

	party_type(frm) {
		frm.set_value("party", null);
		frm.refresh_field("party");
	},
});

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
