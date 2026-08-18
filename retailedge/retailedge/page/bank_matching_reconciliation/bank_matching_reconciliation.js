frappe.pages["bank-matching-reconciliation"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Bank Matching & Reconciliation"),
		single_column: true,
	});

	const state = {
		direction: "All",
		queue: "To Match",
	};

	const $root = $("<div class='retailedge-bank-reconciliation'></div>").appendTo(page.main);
	const $toolbar = $("<div class='mb-4'></div>").appendTo($root);
	const $direction = $("<div class='btn-group mr-2' role='group'></div>").appendTo($toolbar);
	const $queues = $("<div class='btn-group' role='group'></div>").appendTo($toolbar);
	const $content = $("<div class='retailedge-bank-reconciliation-content'></div>").appendTo($root);

	["All", "Inflows", "Outflows"].forEach((label) => {
		const value = label === "Inflows" ? "Inflow" : label === "Outflows" ? "Outflow" : "All";
		const $button = $(`<button class='btn btn-sm btn-default'>${__(label)}</button>`).appendTo($direction);
		$button.on("click", () => {
			state.direction = value;
			refresh();
		});
	});

	["To Match", "To Reconcile", "Exceptions", "Reconciled"].forEach((label) => {
		const $button = $(`<button class='btn btn-sm btn-default'>${__(label)}</button>`).appendTo($queues);
		$button.on("click", () => {
			state.queue = label;
			refresh();
		});
	});

	page.set_primary_action(__("Refresh"), () => refresh());
	page.add_menu_item(__("Open Matching Report"), () => {
		frappe.set_route("query-report", "RetailEdge Bank Transaction Matching");
	});
	page.add_menu_item(__("Open Reconciliation Readiness"), () => {
		frappe.set_route("query-report", "RetailEdge Bank Match Reconciliation Readiness");
	});

	function set_active_buttons() {
		$direction.find("button").each(function () {
			const label = $(this).text();
			const value = label === __("Inflows") ? "Inflow" : label === __("Outflows") ? "Outflow" : "All";
			$(this).toggleClass("btn-primary", value === state.direction).toggleClass("btn-default", value !== state.direction);
		});
		$queues.find("button").each(function () {
			const active = $(this).text() === __(state.queue);
			$(this).toggleClass("btn-primary", active).toggleClass("btn-default", !active);
		});
	}

	function refresh() {
		set_active_buttons();
		$content.html(`<div class='text-muted'>${__("Loading bank matching and reconciliation queue...")}</div>`);
		frappe.call({
			method: "retailedge.banking_workspace.get_banking_workspace_rows",
			args: {
				direction: state.direction,
				queue: state.queue,
				limit: 100,
			},
			callback(r) {
				render_rows((r && r.message) || {});
			},
			error() {
				$content.html(`<div class='text-danger'>${__("Unable to load the banking queue.")}</div>`);
			},
		});
	}

	function render_rows(payload) {
		const rows = payload.rows || [];
		if (!rows.length) {
			$content.html(`<div class='text-muted'>${__("No transactions in this queue for the selected direction.")}</div>`);
			return;
		}
		const body = rows
			.map((row) => `
				<tr>
					<td><a href='/app/bank-transaction/${encodeURIComponent(row.bank_transaction || "")}'>${frappe.utils.escape_html(row.bank_transaction || "")}</a></td>
					<td>${frappe.utils.escape_html(row.direction || "")}</td>
					<td>${frappe.utils.escape_html(row.transaction_category || "")}</td>
					<td>${frappe.utils.escape_html(row.operational_status || "")}</td>
					<td>${frappe.utils.escape_html(row.suggested_document_type || "")}</td>
					<td>${frappe.utils.escape_html(row.suggested_document || "")}</td>
					<td class='text-right'>${format_currency(row.bank_amount || 0)}</td>
					<td>${render_action(row)}</td>
				</tr>`)
			.join("");
		$content.html(`
			<div class='mb-3 text-muted'>${__("{0} transaction(s)", [rows.length])}</div>
			<div class='table-responsive'>
				<table class='table table-bordered table-hover'>
					<thead><tr>
						<th>${__("Bank Transaction")}</th><th>${__("Direction")}</th><th>${__("Category")}</th>
						<th>${__("Status")}</th><th>${__("Candidate Type")}</th><th>${__("Candidate")}</th>
						<th class='text-right'>${__("Amount")}</th><th>${__("Action")}</th>
					</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>`);
		$content.find("[data-retailedge-action='reconcile']").on("click", function () {
			confirm_and_reconcile($(this).data("match-name"));
		});
		$content.find("[data-retailedge-action='find-candidates']").on("click", function () {
			find_candidates($(this).data("bank-transaction"));
		});
	}

	function render_action(row) {
		if (row.operational_status === "Ready to Reconcile") {
			return `<button class='btn btn-xs btn-primary' data-retailedge-action='reconcile' data-match-name='${frappe.utils.escape_html(row.match_name || "")}'>${__("Match & Reconcile")}</button>`;
		}
		if (!row.match_name && state.queue === "To Match") {
			return `<button class='btn btn-xs btn-primary' data-retailedge-action='find-candidates' data-bank-transaction='${frappe.utils.escape_html(row.bank_transaction || "")}'>${__("Find Candidates")}</button>`;
		}
		if (row.match_name) {
			return `<a class='btn btn-xs btn-default' href='/app/retailedge-bank-transaction-match/${encodeURIComponent(row.match_name)}'>${__("Review")}</a>`;
		}
		return "";
	}

	function find_candidates(bankTransaction) {
		frappe.call({
			method: "retailedge.bank_candidate_engine.get_direction_aware_bank_candidates",
			args: { bank_transaction_name: bankTransaction, limit: 20 },
			freeze: true,
			freeze_message: __("Finding accounting matches..."),
			callback(r) {
				show_candidate_dialog(bankTransaction, (r && r.message) || {});
			},
		});
	}

	function show_candidate_dialog(bankTransaction, payload) {
		const rows = payload.candidates || [];
		const dialog = new frappe.ui.Dialog({
			title: __("Matching Candidates for {0}", [bankTransaction]),
			fields: [{ fieldname: "candidate_html", fieldtype: "HTML" }],
			size: "extra-large",
		});
		if (!rows.length) {
			dialog.fields_dict.candidate_html.$wrapper.html(`<div class='text-muted'>${__("No safe candidate reached the matching threshold.")}</div>`);
			dialog.show();
			return;
		}
		const body = rows.map((row) => {
			const reviewSupported = Number(row.review_supported) !== 0;
			const action = reviewSupported
				? `<button class='btn btn-xs btn-primary' data-retailedge-candidate-action='review' data-document-type='${frappe.utils.escape_html(row.document_type || "")}' data-document-name='${frappe.utils.escape_html(row.document_name || "")}'>${__("Review Match")}</button>`
				: `<span class='text-muted' title='${frappe.utils.escape_html(row.review_block_reason || "")}'>${__("Bridge Review Pending")}</span>`;
			return `
			<tr>
				<td>${frappe.utils.escape_html(row.document_type || "")}</td>
				<td>${frappe.utils.escape_html(row.document_name || "")}</td>
				<td>${frappe.utils.escape_html(row.transaction_category || row.candidate_category || "")}</td>
				<td>${frappe.utils.escape_html(row.candidate_category || "")}</td>
				<td class='text-right'>${frappe.utils.escape_html(String(row.match_score || 0))}</td>
				<td class='text-right'>${frappe.utils.escape_html(String(row.fuzzy_score || 0))}</td>
				<td>${frappe.utils.escape_html(row.fuzzy_confidence || "")}</td>
				<td>${action}</td>
			</tr>`;
		}).join("");
		dialog.fields_dict.candidate_html.$wrapper.html(`
			<div class='mb-2 text-muted'>${__("Direction: {0}. Fuzzy similarity only ranks candidates that already passed hard accounting checks.", [payload.direction || ""])}</div>
			<div class='table-responsive'><table class='table table-bordered table-hover'>
				<thead><tr><th>${__("Type")}</th><th>${__("Document")}</th><th>${__("Business Category")}</th><th>${__("Match Basis")}</th><th>${__("Score")}</th><th>${__("Fuzzy")}</th><th>${__("Confidence")}</th><th>${__("Action")}</th></tr></thead>
				<tbody>${body}</tbody>
			</table></div>`);
		dialog.fields_dict.candidate_html.$wrapper.find("[data-retailedge-candidate-action='review']").on("click", function () {
			prepare_candidate_review(
				bankTransaction,
				$(this).data("document-type"),
				$(this).data("document-name"),
				dialog,
			);
		});
		dialog.show();
	}

	function prepare_candidate_review(bankTransaction, documentType, documentName, dialog) {
		frappe.call({
			method: "retailedge.bank_candidate_engine.prepare_direction_aware_bank_candidate",
			args: {
				bank_transaction_name: bankTransaction,
				document_type: documentType,
				document_name: documentName,
			},
			freeze: true,
			freeze_message: __("Revalidating candidate..."),
			callback(r) {
				const result = (r && r.message) || {};
				if (!result.match_name) {
					frappe.msgprint(result.message || __("This candidate cannot enter review yet."));
					return;
				}
				dialog.hide();
				frappe.set_route("Form", "RetailEdge Bank Transaction Match", result.match_name);
			},
		});
	}

	function confirm_and_reconcile(matchName) {
		frappe.confirm(
			__("This will use ERPNext native bank reconciliation after a fresh safety check. Continue?"),
			() => {
				frappe.call({
					method: "retailedge.banking_operations.match_and_reconcile",
					args: {
						match_name: matchName,
						confirm_match: 1,
						confirm_reconciliation: 1,
					},
					freeze: true,
					freeze_message: __("Reconciling through ERPNext..."),
					callback(r) {
						const result = (r && r.message) || {};
						frappe.show_alert({ message: result.message || result.status || __("Reconciliation processed."), indicator: result.status === "Executed" ? "green" : "orange" });
						refresh();
					},
				});
			},
		);
	}

	refresh();
};
