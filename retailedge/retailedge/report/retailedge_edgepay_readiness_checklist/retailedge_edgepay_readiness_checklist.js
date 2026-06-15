// Copyright (c) 2026, ProcessEdge Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["RetailEdge EdgePay Readiness Checklist"] = {
	filters: [],
	onload(report) {
		report.ignore_prepared_report = true;
		report.prepared_report = false;
		report.prepared_report_name = null;
		report.prepared_report_document = null;
		
		if (report.page && typeof report.page.set_primary_action === "function") {
			report.page.set_primary_action(__("Refresh Checklist"), () => {
				report.refresh();
			});
		}
	},
	after_refresh(report) {
		if (report.page && typeof report.page.set_primary_action === "function") {
			report.page.set_primary_action(__("Refresh Checklist"), () => {
				report.refresh();
			});
		}
	}
};
