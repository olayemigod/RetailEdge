// Copyright (c) 2026, ProcessEdge Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on('RetailEdge EdgePay Payment Evidence', {
	refresh: function(frm) {
		// 1. Review Actions
		if (frm.doc.review_status === 'Pending Review' && frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Mark as Reviewed'), function() {
				frappe.call({
					method: 'retailedge.api.mark_edgepay_evidence_reviewed',
					args: {
						evidence_name: frm.doc.name
					},
					callback: function(r) {
						if (r.message && r.message.ok) {
							frappe.show_alert({
								message: __('Payment evidence marked as Reviewed.'),
								indicator: 'green'
							});
							frm.reload_doc();
						}
					}
				});
			}, __('Actions'));

			frm.add_custom_button(__('Reject'), function() {
				frappe.prompt(
					[
						{
							label: __('Reason for Rejection'),
							fieldname: 'reason',
							fieldtype: 'Small Text'
						}
					],
					(values) => {
						frappe.call({
							method: 'retailedge.api.mark_edgepay_evidence_rejected',
							args: {
								evidence_name: frm.doc.name,
								reason: values.reason
							},
							callback: function(r) {
								if (r.message && r.message.ok) {
									frappe.show_alert({
										message: __('Payment evidence marked as Rejected.'),
										indicator: 'red'
									});
									frm.reload_doc();
								}
							}
						});
					},
					__('Reject Payment Evidence'),
					__('Reject')
				);
			}, __('Actions'));
		}

		// 2. Posting Actions
		if (frm.doc.review_status === 'Reviewed' && frm.doc.docstatus === 0) {
			if (!frm.doc.payment_entry) {
				frm.add_custom_button(__('Prepare Draft Payment Entry'), function() {
					frappe.call({
						method: 'retailedge.api.prepare_edgepay_payment_entry_draft',
						args: {
							evidence_name: frm.doc.name
						},
						callback: function(r) {
							if (r.message && r.message.ok) {
								frappe.show_alert({
									message: __('Draft Payment Entry {0} prepared successfully.', [r.message.payment_entry]),
									indicator: 'green'
								});
								frm.reload_doc();
							}
						}
					});
				});
			} else if (frm.doc.posting_status !== 'Submitted') {
				frm.add_custom_button(__('Submit Payment Entry'), function() {
					frappe.confirm(
						__('Are you sure you want to submit the linked Payment Entry {0}? This will post to the ledger.', [frm.doc.payment_entry]),
						() => {
							frappe.call({
								method: 'retailedge.api.submit_edgepay_payment_entry',
								args: {
									evidence_name: frm.doc.name
								},
								callback: function(r) {
									if (r.message && r.message.ok) {
										frappe.show_alert({
											message: __('Payment Entry submitted successfully.'),
											indicator: 'green'
										});
										frm.reload_doc();
									}
								}
							});
						}
					);
				});
			}
		}

		// 3. Reconciliation Actions
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
		
		if (frm.doc.reconciliation_status === 'Matched' && frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Confirm Match Review'), function() {
				frappe.call({
					method: 'retailedge.api.get_edgepay_bank_match_confirmation_preflight',
					args: {
						evidence_name: frm.doc.name,
						review_name: frm.doc.linked_bank_match_review
					},
					callback: function(res) {
						if (res.message && res.message.ok) {
							frappe.confirm(
								__('Are you sure you want to confirm this Bank Match Review?'),
								() => {
									frappe.call({
										method: 'retailedge.api.confirm_edgepay_bank_match_review',
										args: {
											evidence_name: frm.doc.name,
											review_name: frm.doc.linked_bank_match_review
										},
										callback: function(confirm_res) {
											if (confirm_res.message && confirm_res.message.ok) {
												frappe.show_alert({
													message: __('Bank Match Review confirmed successfully.'),
													indicator: 'green'
												});
												frm.reload_doc();
											} else {
												frappe.msgprint(confirm_res.message.message || __('Failed to confirm match review.'));
											}
										}
									});
								}
							);
						} else {
							frappe.msgprint(res.message.message || __('Confirmation preflight validation failed.'));
						}
					}
				});
			});
		}
	}
});
