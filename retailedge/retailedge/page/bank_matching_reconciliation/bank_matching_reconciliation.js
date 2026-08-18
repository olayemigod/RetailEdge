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
			method: "retailedge.banking_operations.get_banking_workspace_rows",
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
			const matchName = $(this).data("match-name");
			confirm_and_reconcile(matchName);
		});
	}

	function render_action(row) {
		if (row.operational_status === "Ready to Reconcile") {
			return `<button class='btn btn-xs btn-primary' data-retailedge-action='reconcile' data-match-name='${frappe.utils.escape_html(row.match_name || "")}'>${__("Match & Reconcile")}</button>`;
		}
		if (row.match_name) {
			return `<a class='btn btn-xs btn-default' href='/app/retailedge-bank-transaction-match/${encodeURIComponent(row.match_name)}'>${__("Review")}</a>`;
		}
		return "";
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
