function configureOperationalReportRefresh(report) {
	if (!report || report.__retailedgeAutoRefreshConfigured) {
		return;
	}
	report.__retailedgeAutoRefreshConfigured = true;
	report.ignore_prepared_report = true;
	report.prepared_report = false;
	report.prepared_report_name = null;
	report.prepared_report_document = null;
	report.__retailedgeAutoRefreshReady = true;
	(report.filters || []).forEach((filter) => {
		const originalOnChange = filter.on_change;
		filter.on_change = function (queryReport) {
			if (typeof originalOnChange === "function") {
				originalOnChange.call(this, queryReport || report);
			}
			if (!report.__retailedgeAutoRefreshReady) {
				return;
			}
			scheduleOperationalReportRefresh(queryReport || report);
		};
	});
}

function scheduleOperationalReportRefresh(report) {
	if (!report) {
		return;
	}
	if (report.__retailedgeRefreshTimer) {
		clearTimeout(report.__retailedgeRefreshTimer);
	}
	report.__retailedgeRefreshTimer = setTimeout(() => {
		report.refresh();
	}, 200);
}

function forceOperationalPrimaryAction(report) {
	if (!report || !report.page || typeof report.page.set_primary_action !== "function") {
		return;
	}
	report.page.set_primary_action(__("Refresh Report"), () => {
		report.refresh();
	});
}

frappe.query_reports["RetailEdge EdgePay Reconciliation Readiness"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "from_date", label: __("Date From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("Date To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "review_status", label: __("Review Status"), fieldtype: "Select", options: "\nPending Review\nReviewed\nRejected\nException" },
		{ fieldname: "reconciliation_status", label: __("Reconciliation Status"), fieldtype: "Select", options: "\nNot Ready\nReady\nMatched\nReconciled\nBlocked\nException" }
	],
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
		
		report.page.add_inner_button(__('Create Match Review'), () => {
			// Step 1: Prompt user for Evidence Name
			frappe.prompt([
				{
					label: __('Payment Evidence'),
					fieldname: 'evidence',
					fieldtype: 'Link',
					options: 'RetailEdge EdgePay Payment Evidence',
					get_query: () => {
						return {
							filters: {
								reconciliation_status: 'Ready',
								docstatus: 0
							}
						};
					},
					reqd: 1
				}
			], (values) => {
				let evidence_name = values.evidence;
				// Step 2: Fetch candidates
				frappe.call({
					method: 'retailedge.api.find_edgepay_payment_entry_bank_match_candidates',
					args: {
						evidence_name: evidence_name
					},
					callback: function(r) {
						let candidates = r.message || [];
						if (candidates.length === 0) {
							frappe.msgprint(__('No candidate Bank Transactions found matching this evidence.'));
							return;
						}
						
						let options = candidates.map(c => ({
							value: c.bank_transaction,
							label: `${c.bank_transaction} - Date: ${c.date} | Ref: ${c.reference_number || 'None'} | Conf: ${c.confidence}`
						}));
						
						frappe.prompt([
							{
								label: __('Bank Transaction Candidate'),
								fieldname: 'bank_transaction',
								fieldtype: 'Select',
								options: options,
								reqd: 1
							}
						], (cand_values) => {
							// Step 3: Call preflight first
							frappe.call({
								method: 'retailedge.api.get_edgepay_bank_match_review_preflight',
								args: {
									evidence_name: evidence_name,
									bank_transaction_name: cand_values.bank_transaction
								},
								callback: function(res) {
									if (res.message && res.message.ok) {
										// Step 4: Create match review
										frappe.call({
											method: 'retailedge.api.create_edgepay_bank_match_review',
											args: {
												evidence_name: evidence_name,
												bank_transaction_name: cand_values.bank_transaction
											},
											callback: function(create_res) {
												if (create_res.message && create_res.message.ok) {
													frappe.show_alert({
														message: __('Bank Match Review {0} created successfully.', [create_res.message.review_name]),
														indicator: 'green'
													});
													report.refresh();
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
						}, __('Select Candidate'), __('Create Match Review'));
					}
				});
			}, __('Select Payment Evidence'), __('Next'));
		});

		report.page.add_inner_button(__('Confirm Match Review'), () => {
			frappe.prompt([
				{
					label: __('Payment Evidence'),
					fieldname: 'evidence',
					fieldtype: 'Link',
					options: 'RetailEdge EdgePay Payment Evidence',
					get_query: () => {
						return {
							filters: {
								reconciliation_status: 'Matched',
								docstatus: 0
							}
						};
					},
					reqd: 1
				}
			], (values) => {
				let evidence_name = values.evidence;
				frappe.db.get_doc('RetailEdge EdgePay Payment Evidence', evidence_name).then(doc => {
					let review_name = doc.linked_bank_match_review;
					if (!review_name) {
						frappe.msgprint(__('No linked Bank Match Review found on evidence.'));
						return;
					}
					frappe.call({
						method: 'retailedge.api.get_edgepay_bank_match_confirmation_preflight',
						args: {
							evidence_name: evidence_name,
							review_name: review_name
						},
						callback: function(res) {
							if (res.message && res.message.ok) {
								frappe.confirm(
									__('Are you sure you want to confirm this Bank Match Review?'),
									() => {
										frappe.call({
											method: 'retailedge.api.confirm_edgepay_bank_match_review',
											args: {
												evidence_name: evidence_name,
												review_name: review_name
											},
											callback: function(confirm_res) {
												if (confirm_res.message && confirm_res.message.ok) {
													frappe.show_alert({
														message: __('Bank Match Review confirmed successfully.'),
														indicator: 'green'
													});
													report.refresh();
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
			}, __('Select Payment Evidence to Confirm'), __('Confirm'));
		});
	},
	after_refresh(report) {
		forceOperationalPrimaryAction(report);
	}
};
