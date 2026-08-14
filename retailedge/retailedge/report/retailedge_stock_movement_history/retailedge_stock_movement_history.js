frappe.query_reports["RetailEdge Stock Movement History"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			on_change() {
				const company = frappe.query_report.get_filter_value("company");
				for (const fieldname of ["branch", "warehouse"]) {
					if (frappe.query_report.get_filter_value(fieldname)) {
						frappe.query_report.set_filter_value(fieldname, "");
					}
				}
				if (company) frappe.query_report.refresh();
			},
		},
		{
			fieldname: "date_range_preset",
			label: __("Date Range Preset"),
			fieldtype: "Select",
			options: [
				"This Month",
				"Today",
				"Yesterday",
				"This Week",
				"This Quarter",
				"This Year",
				"Last Week",
				"Last Month",
				"Last Quarter",
				"Last Year",
				"Custom Period",
			].join("\n"),
			default: "This Month",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			reqd: 1,
			get_query() {
				return { filters: { disabled: 0, is_stock_item: 1 } };
			},
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
			get_query() {
				const company = frappe.query_report.get_filter_value("company");
				return { filters: company ? { company } : {} };
			},
			on_change() {
				frappe.query_report.set_filter_value("warehouse", "");
			},
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			reqd: 1,
			get_query() {
				const company = frappe.query_report.get_filter_value("company");
				const filters = { is_group: 0 };
				if (company) filters.company = company;
				return { filters };
			},
		},
		{
			fieldname: "compare_uom",
			label: __("Compare UOM"),
			fieldtype: "Link",
			options: "UOM",
		},
		{
			fieldname: "movement_type",
			label: __("Movement Type"),
			fieldtype: "Select",
			options: [
				"",
				"Purchase Receipt",
				"Sale",
				"Sales Return",
				"Purchase Return",
				"Internal Transfer",
				"Material Issue",
				"Material Receipt",
				"Manufacture",
				"Repack",
				"Adjustment In",
				"Adjustment Out",
				"Incoming",
				"Outgoing",
			].join("\n"),
		},
		{
			fieldname: "voucher_type",
			label: __("Voucher Type"),
			fieldtype: "Link",
			options: "DocType",
		},
		{
			fieldname: "voucher_no",
			label: __("Voucher Number"),
			fieldtype: "Data",
		},
		{
			fieldname: "batch_no",
			label: __("Batch Number"),
			fieldtype: "Link",
			options: "Batch",
		},
	],

	onload(report) {
		report.ignore_prepared_report = true;
		report.prepared_report = false;
		if (window.retailedge && typeof window.retailedge.setupDateRangePresets === "function") {
			window.retailedge.setupDateRangePresets(report);
		}
		const originalRefresh = report.refresh.bind(report);
		report.refresh = function () {
			const fromDate = report.get_filter_value("from_date");
			const toDate = report.get_filter_value("to_date");
			if (
				fromDate &&
				toDate &&
				frappe.datetime.str_to_obj(fromDate) > frappe.datetime.str_to_obj(toDate)
			) {
				frappe.throw(__("From Date cannot be after To Date."));
			}
			return originalRefresh();
		};
	},
};
