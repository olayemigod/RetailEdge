// Copyright (c) 2026, ProcessEdge Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on('RetailEdge EdgePay Payment Evidence', {
	refresh: function(frm) {
		if (frm.doc.reconciliation_status === 'Ready' && frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Create Match Review'), function() {
				// 1. Fetch candidate bank transactions
				frappe.call({
					method: 'retailedge.api.find_edgepay_payment_entry_bank_match_candidates',
					args: {
						evidence_name: frm.doc.name
					},
					callback: function(r) {
						let candidates = r.message || [];
						if (candidates.length === 0) {
							frappe.msgprint(__('No candidate Bank Transactions found matching this evidence.'));
							return;
						}
						
						// 2. Map candidates for Select options
						let options = candidates.map(c => ({
							value: c.bank_transaction,
							label: `${c.bank_transaction} - Date: ${c.date} | Ref: ${c.reference_number || 'None'} | Conf: ${c.confidence}`
						}));
						
						// 3. Show dialog prompt
						let dialog = new frappe.ui.Dialog({
							title: __('Select Bank Transaction Candidate'),
							fields: [
								{
									label: __('Bank Transaction Candidate'),
									fieldname: 'bank_transaction',
									fieldtype: 'Select',
									options: options,
									reqd: 1
								}
							],
							primary_action_label: __('Create Match Review'),
							primary_action(values) {
								dialog.hide();
								// Call preflight first, then create review
								frappe.call({
									method: 'retailedge.api.get_edgepay_bank_match_review_preflight',
									args: {
										evidence_name: frm.doc.name,
										bank_transaction_name: values.bank_transaction
									},
									callback: function(res) {
										if (res.message && res.message.ok) {
											frappe.call({
												method: 'retailedge.api.create_edgepay_bank_match_review',
												args: {
													evidence_name: frm.doc.name,
													bank_transaction_name: values.bank_transaction
												},
												callback: function(create_res) {
													if (create_res.message && create_res.message.ok) {
														frappe.show_alert({
															message: __('Bank Match Review {0} created successfully.', [create_res.message.review_name]),
															indicator: 'green'
														});
														frm.reload_doc();
													} else {
														frappe.msgprint(create_res.message.message || __('Failed to create match review.'));
													}
												}
											});
										} else {
											frappe.msgprint(res.message.message || __('Preflight validation failed.'));
										}
									}
								});
							}
						});
						dialog.show();
					}
				});
			});
		}
	}
});
