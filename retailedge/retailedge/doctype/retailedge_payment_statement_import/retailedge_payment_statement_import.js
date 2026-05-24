frappe.ui.form.on("RetailEdge Payment Statement Import", {
	refresh(frm) {
		frm.clear_custom_buttons();

		if (frm.is_new()) {
			return;
		}

		apply_statement_row_pagination(frm);
		add_statement_import_action_buttons(frm);
	},
});

function add_statement_import_action_buttons(frm) {
	frm.add_custom_button(
		__("Preview Statement Rows"),
		function () {
			call_statement_import_action({
				frm,
				method: "retailedge.api.preview_payment_statement_import_rows",
				args: {
					import_name: frm.doc.name,
				},
				freeze_message: __("Previewing statement rows..."),
				title: __("Statement Row Preview"),
			});
		},
		__("Import Actions")
	);

	frm.add_custom_button(
		__("Import Statement Rows"),
		function () {
			frappe.confirm(__("Import statement rows for this statement?"), function () {
				call_statement_import_action({
					frm,
					method: "retailedge.api.import_payment_statement_rows",
					args: {
						import_name: frm.doc.name,
						replace_rows: 1,
					},
					freeze_message: __("Importing statement rows..."),
					title: __("Statement Rows Imported"),
					reload: true,
				});
			});
		},
		__("Import Actions")
	);

	frm.add_custom_button(
		__("Preview Bank Transactions"),
		function () {
			call_statement_import_action({
				frm,
				method: "retailedge.api.preview_bank_transaction_import",
				args: {
					statement_import_name: frm.doc.name,
				},
				freeze_message: __("Previewing bank transactions..."),
				title: __("Bank Transaction Preview"),
			});
		},
		__("Bank Transactions")
	);

	frm.add_custom_button(
		__("Create Bank Transactions"),
		function () {
			frappe.confirm(
				__("Create or link ERPNext Bank Transactions for valid statement rows?"),
				function () {
					call_statement_import_action({
						frm,
						method: "retailedge.api.import_statement_rows_to_bank_transactions",
						args: {
							statement_import_name: frm.doc.name,
							force: 0,
						},
						freeze_message: __("Creating bank transactions..."),
						title: __("Bank Transaction Import Summary"),
						reload: true,
					});
				}
			);
		},
		__("Bank Transactions")
	);

	frm.add_custom_button(
		__("Review Possible Duplicates"),
		function () {
			open_possible_duplicate_review_dialog(frm);
		},
		__("Bank Transactions")
	);

	if (frm.page && frm.page.set_inner_btn_group_as_primary) {
		frm.page.set_inner_btn_group_as_primary(__("Bank Transactions"));
	}
}

function call_statement_import_action(options) {
	frappe.call({
		method: options.method,
		args: options.args || {},
		freeze: true,
		freeze_message: options.freeze_message,
		callback: function (r) {
			show_statement_import_summary(r && r.message, options.title);

			if (options.reload && options.frm) {
				options.frm.reload_doc();
			}
		},
	});
}

function apply_statement_row_pagination(frm) {
	const field = frm.get_field("rows");
	const grid = field && field.grid;
	if (!grid) {
		return;
	}

	grid.meta.grid_page_length = 10;
	if (grid.grid_pagination) {
		grid.grid_pagination.page_length = 10;
		grid.grid_pagination.page_index = 1;
	}
	grid.refresh();
}

function open_possible_duplicate_review_dialog(frm) {
	frappe.call({
		method: "retailedge.api.get_possible_duplicate_statement_rows",
		args: {
			statement_import_name: frm.doc.name,
		},
		freeze: true,
		freeze_message: __("Loading possible duplicates..."),
		callback: function (r) {
			const rows = Array.isArray(r && r.message) ? r.message : [];
			if (!rows.length) {
				frappe.msgprint({
					title: __("Review Possible Duplicates"),
					message: __("No possible duplicates found for this statement import."),
					indicator: "blue",
				});
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: __("Review Possible Duplicates"),
				fields: [
					{
						fieldname: "row_name",
						fieldtype: "Select",
						label: __("Possible Duplicate Row"),
						reqd: 1,
						options: rows.map((row) => ({
							label: build_possible_duplicate_option_label(row),
							value: row.name,
						})),
						onchange() {
							render_possible_duplicate_details(dialog, rows);
						},
					},
					{
						fieldname: "row_details",
						fieldtype: "HTML",
					},
					{
						fieldname: "acceptance_note",
						fieldtype: "Small Text",
						label: __("Acceptance Note"),
						reqd: 1,
					},
				],
				primary_action_label: __("Accept Selected Row"),
				primary_action(values) {
					if (!values.row_name) {
						frappe.msgprint(__("Select a possible duplicate row first."));
						return;
					}

					frappe.call({
						method: "retailedge.api.accept_possible_duplicate_statement_row",
						args: {
							row_name: values.row_name,
							acceptance_note: values.acceptance_note || "",
						},
						freeze: true,
						freeze_message: __("Accepting possible duplicate..."),
						callback: function (response) {
							const result = response && response.message ? response.message : {};
							const bankTransaction = result.bank_transaction
								? __("Bank Transaction {0} was created/linked.", [result.bank_transaction])
								: __("The row was accepted.");
							frappe.msgprint({
								title: __("Possible Duplicate Accepted"),
								message: `${frappe.utils.escape_html(bankTransaction)}<br><br>${frappe.utils.escape_html(
									__(
										"No Payment Entry, Journal Entry, GL Entry, or Sales Invoice accounting field was changed."
									)
								)}`,
								indicator: "green",
							});
							dialog.hide();
							frm.reload_doc();
						},
						error: function (error) {
							const message =
								(error && error.message) ||
								__(
									"This row is an exact duplicate and cannot be accepted. Same date, amount, reference, bank account, company, and direction already exist."
								);
							frappe.msgprint({
								title: __("Possible Duplicate Not Accepted"),
								message: frappe.utils.escape_html(message),
								indicator: "red",
							});
						},
					});
				},
			});

			dialog.show();
			dialog.set_value("row_name", rows[0].name);
			render_possible_duplicate_details(dialog, rows);
		},
	});
}

function render_possible_duplicate_details(dialog, rows) {
	const rowName = dialog.get_value("row_name");
	const row = rows.find((item) => item.name === rowName);
	const wrapper = dialog.get_field("row_details").$wrapper;
	if (!row) {
		wrapper.html("");
		return;
	}

	const details = [
		[__("Row"), row.name],
		[__("Transaction Date"), row.transaction_date || ""],
		[__("Bank Account"), row.bank_account || ""],
		[__("Reference"), row.reference || ""],
		[__("Narration"), row.narration || ""],
		[__("Amount"), format_currency(row.amount || 0)],
		[__("Direction"), row.direction || ""],
		[__("Duplicate Status"), row.duplicate_status || ""],
		[__("Import Status"), row.import_status || ""],
		[__("Existing Bank Transaction"), row.existing_bank_transaction || ""],
		[__("Reason"), row.reason || ""],
	];

	wrapper.html(`
		<table class="table table-bordered table-sm" style="margin-bottom: 0;">
			<tbody>
				${details
					.map(
						([label, value]) =>
							`<tr><td style="width: 38%;"><strong>${frappe.utils.escape_html(label)}</strong></td><td>${frappe.utils.escape_html(
								String(value || "")
							)}</td></tr>`
					)
					.join("")}
			</tbody>
		</table>
	`);
}

function build_possible_duplicate_option_label(row) {
	return [row.name, row.transaction_date, format_currency(row.amount || 0), row.reference || __("No Reference")]
		.filter(Boolean)
		.join(" | ");
}

function show_statement_import_summary(result, title) {
	if (!result) {
		frappe.msgprint({
			title: title,
			message: __("No result returned."),
			indicator: "orange",
		});
		return;
	}

	const indicator = result.status === "Failed" || result.status === "Invalid" ? "red" : "green";
	const html = build_statement_import_summary_html(result);

	frappe.msgprint({
		title: title,
		message: html,
		indicator,
	});
}

function build_statement_import_summary_html(result) {
	const summaryRows = [];
	const totalRows = asInt(result.total_rows || result.row_count);
	const readyRows = asInt(result.ready_rows);
	const importedRows = asInt(result.imported_rows || result.imported_row_count || result.imported);
	const alreadyImported = asInt(result.already_imported);
	const possibleDuplicates =
		asInt(result.possible_duplicates) ||
		asInt(result.duplicate_suspected) ||
		asInt(getNestedCount(result, "duplicate_status", "Possible Duplicate"));
	const exactDuplicates =
		asInt(result.exact_duplicates) ||
		asInt(getNestedCount(result, "duplicate_status", "Exact Duplicate")) +
			asInt(getNestedCount(result, "duplicate_status", "Already Imported"));
	const skippedRows =
		asInt(result.skipped_rows) || asInt(getNestedCount(result, "import_status", "Skipped"));
	const failedRows =
		asInt(result.failed_rows) ||
		asInt(result.invalid) ||
		asInt(result.failed) ||
		asInt(getNestedCount(result, "import_status", "Invalid")) +
			asInt(getNestedCount(result, "import_status", "Failed"));
	const linkedBankTransactions =
		asInt(result.linked_bank_transactions) || asInt(result.linked_bank_transaction_count);

	pushSummaryRow(summaryRows, __("Total Rows"), totalRows);
	pushSummaryRow(summaryRows, __("Ready Rows"), readyRows);
	pushSummaryRow(summaryRows, __("Imported Rows"), importedRows);
	pushSummaryRow(summaryRows, __("Already Imported"), alreadyImported);
	pushSummaryRow(summaryRows, __("Possible Duplicates"), possibleDuplicates);
	pushSummaryRow(summaryRows, __("Exact Duplicates"), exactDuplicates);
	pushSummaryRow(summaryRows, __("Skipped Rows"), skippedRows);
	pushSummaryRow(summaryRows, __("Failed Rows"), failedRows);
	pushSummaryRow(summaryRows, __("Linked Bank Transactions"), linkedBankTransactions);

	const rowPreview = buildRowPreviewTable(result.rows || []);
	const guidance = buildGuidanceNotes(result, possibleDuplicates, exactDuplicates);
	const reason = result.reason
		? `<p style="margin-top: 12px;">${frappe.utils.escape_html(result.reason)}</p>`
		: "";

	return `
		<div>
			<table class="table table-bordered" style="margin-bottom: 12px;">
				<tbody>${summaryRows.join("")}</tbody>
			</table>
			${guidance}
			${rowPreview}
			${reason}
		</div>
	`;
}

function pushSummaryRow(rows, label, value) {
	if (value === 0 || value) {
		rows.push(
			`<tr><td style="width: 60%;"><strong>${frappe.utils.escape_html(label)}</strong></td><td>${frappe.utils.escape_html(
				String(value)
			)}</td></tr>`
		);
	}
}

function buildGuidanceNotes(result, possibleDuplicates, exactDuplicates) {
	const notes = [__("No Payment Entry, Journal Entry, GL Entry, or bank reconciliation was created by this action.")];

	if (possibleDuplicates > 0) {
		notes.push(
			__(
				"Some rows need review because the reference is missing, weak, or ambiguous. Open the statement rows marked Possible Duplicate and use Accept Possible Duplicate only if you confirm they are valid."
			)
		);
	}

	if (exactDuplicates > 0 || asInt(result.already_imported) > 0) {
		notes.push(
			__(
				"Exact duplicates were skipped because the same date, amount, reference, account, and direction already exist."
			)
		);
	}

	if (!notes.length) {
		return "";
	}

	return `<ul style="margin: 0 0 12px 18px;">${notes
		.map((note) => `<li>${frappe.utils.escape_html(note)}</li>`)
		.join("")}</ul>`;
}

function buildRowPreviewTable(rows) {
	if (!Array.isArray(rows) || !rows.length) {
		return "";
	}

	const sample = rows.slice(0, 10);
	const body = sample
		.map((row) => {
			return `<tr>
				<td>${frappe.utils.escape_html(String(row.statement_row || row.row_index || ""))}</td>
				<td>${frappe.utils.escape_html(String(row.status || row.import_status || ""))}</td>
				<td>${frappe.utils.escape_html(String(row.reference || row.normalized_reference || ""))}</td>
				<td>${frappe.utils.escape_html(String(row.amount || row.normalized_amount || ""))}</td>
				<td>${frappe.utils.escape_html(String(row.reason || row.row_error || ""))}</td>
			</tr>`;
		})
		.join("");

	const footer =
		rows.length > 10
			? `<p style="margin-top: 8px;">${frappe.utils.escape_html(
					__("Showing first 10 rows. Open Statement Import Rows for full details.")
			  )}</p>`
			: "";

	return `
		<div>
			<table class="table table-bordered table-sm">
				<thead>
					<tr>
						<th>${frappe.utils.escape_html(__("Row"))}</th>
						<th>${frappe.utils.escape_html(__("Status"))}</th>
						<th>${frappe.utils.escape_html(__("Reference"))}</th>
						<th>${frappe.utils.escape_html(__("Amount"))}</th>
						<th>${frappe.utils.escape_html(__("Reason"))}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
			${footer}
		</div>
	`;
}

function getNestedCount(result, key, childKey) {
	if (!result || !result[key] || typeof result[key] !== "object") {
		return 0;
	}
	return result[key][childKey] || 0;
}

function asInt(value) {
	const parsed = parseInt(value, 10);
	return Number.isNaN(parsed) ? 0 : parsed;
}
