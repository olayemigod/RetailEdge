function canRetryCoreEdgeQuota() {
	return (
		frappe.session.user === "Administrator" ||
		["System Manager", "RetailEdge Manager", "RetailEdgeManager"].some((role) =>
			(frappe.user_roles || []).includes(role)
		)
	);
}

frappe.query_reports["RetailEdge CoreEdge Quota Review"] = {
	onload(report) {
		if (report?.page?.wrapper) {
			$(report.page.wrapper)
				.off("click.retailedgeQuotaReview", ".retailedge-quota-retry")
				.on("click.retailedgeQuotaReview", ".retailedge-quota-retry", function (event) {
					event.preventDefault();
					const operation = decodeURIComponent($(this).attr("data-operation") || "");
					if (!operation) {
						return;
					}
					frappe.call({
						method: "retailedge.coreedge_sales_quota.retry_sales_quota_finalize",
						args: { operation_name: operation },
						freeze: true,
						freeze_message: __("Retrying CoreEdge quota finalization..."),
						callback(response) {
							const result = response.message || {};
							frappe.show_alert({
								message: __("Quota operation status: {0}", [result.status || __("Unknown")]),
								indicator: result.status === "Finalized" ? "green" : "orange",
							});
							report.refresh();
						},
					});
				});
		}
	},

	formatter(value, row, column, data, default_formatter) {
		if (
			column.fieldname === "next_action" &&
			data?.status === "Pending Finalize" &&
			canRetryCoreEdgeQuota()
		) {
			const operation = encodeURIComponent(data.name || "");
			return [
				'<button class="btn btn-xs btn-default retailedge-quota-retry"',
				' data-operation="' + operation + '">',
				__("Retry Finalize"),
				"</button>",
			].join("");
		}
		return default_formatter(value, row, column, data);
	},

	filters: [
		{
			fieldname: "needs_attention_only",
			label: __("Needs Attention Only"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nPending Finalize\nNeeds Review\nFinalized",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			on_change(queryReport) {
				queryReport.set_filter_value("branch", "");
			},
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
			get_query() {
				const company = frappe.query_report.get_filter_value("company");
				return company ? { filters: { company } } : {};
			},
		},
		{
			fieldname: "source_doctype",
			label: __("Source Type"),
			fieldtype: "Select",
			options: "\nSales Invoice\nPOS Invoice",
		},
		{
			fieldname: "entitlement_key",
			label: __("Entitlement"),
			fieldtype: "Data",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};
