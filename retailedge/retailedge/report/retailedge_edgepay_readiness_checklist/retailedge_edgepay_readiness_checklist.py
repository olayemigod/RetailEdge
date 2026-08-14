from __future__ import annotations

from frappe import _

from retailedge.services.edgepay_readiness_checklist import get_edgepay_retail_readiness_summary


def execute(filters=None):
	summary = get_edgepay_retail_readiness_summary()
	rows = []

	def add_check(category, check_name, passed, details):
		rows.append(
			{
				"category": category,
				"check_name": check_name,
				"status": "Pass" if passed else "Fail",
				"details": details,
			}
		)

	service = summary.get("service", {})
	add_check(
		"EdgePay Service",
		"Service URL Configured",
		service.get("url_configured"),
		"EdgePay service URL is configured."
		if service.get("url_configured")
		else "EdgePay service URL is not configured for this site.",
	)
	add_check(
		"EdgePay Service",
		"Service Authentication Configured",
		service.get("authentication_configured"),
		f"Authentication mode: {service.get('authentication_mode')}."
		if service.get("authentication_configured")
		else "A scoped EdgePay service credential is not configured.",
	)
	add_check(
		"EdgePay Service",
		"TLS Certificate Verification Enabled",
		service.get("verify_ssl"),
		"Remote EdgePay TLS certificates will be verified."
		if service.get("verify_ssl")
		else "WARNING: TLS certificate verification is disabled.",
	)
	add_check(
		"EdgePay Service",
		"EdgePay App Not Required Locally",
		service.get("local_edgepay_app_required") is False,
		"RetailEdge connects to EdgePay through the service adapter; no EdgePay app is required on this site.",
	)
	add_check(
		"EdgePay Service",
		"Provider Configuration Owned by EdgePay",
		service.get("provider_configuration_owned_by_edgepay"),
		"Provider credentials and provider governance remain inside the EdgePay service.",
	)

	doctypes = summary.get("doctypes", {})
	add_check(
		"RetailEdge Local Evidence",
		"Payment Evidence DocType Exists",
		doctypes.get("evidence_doctype_exists"),
		"RetailEdge local payment evidence storage exists.",
	)
	add_check(
		"RetailEdge Local Evidence",
		"Handoff Log DocType Exists",
		doctypes.get("handoff_log_doctype_exists"),
		"RetailEdge local EdgePay handoff audit log exists.",
	)

	reports = summary.get("reports", {})
	add_check(
		"RetailEdge Reports",
		"Reconciliation Readiness Report Exists",
		reports.get("readiness_report_exists"),
		"RetailEdge EdgePay Reconciliation Readiness report exists.",
	)
	add_check(
		"RetailEdge Reports",
		"Payment Evidence Summary Report Exists",
		reports.get("summary_report_exists"),
		"RetailEdge EdgePay Payment Evidence Summary report exists.",
	)
	add_check(
		"RetailEdge Reports",
		"Lifecycle Status Report Exists",
		reports.get("lifecycle_report_exists"),
		"RetailEdge EdgePay Lifecycle Status report exists.",
	)
	add_check(
		"RetailEdge Reports",
		"Rollout Monitor Report Exists",
		reports.get("rollout_monitor_report_exists"),
		"RetailEdge EdgePay Rollout Monitor report exists.",
	)

	endpoints = summary.get("endpoints", {})
	add_check(
		"Role & Permission Safety",
		"Sensitive Endpoints Block Guest Access",
		endpoints.get("endpoints_gated_against_guest"),
		"Sensitive confirmation and submission endpoints block guest access.",
	)

	counts = summary.get("counts", {})
	add_check(
		"Intake / Evidence Queues",
		"Pending Handoff Events",
		counts.get("pending_handoff_count") == 0,
		f"Pending handoffs: {counts.get('pending_handoff_count')}",
	)
	add_check(
		"Intake / Evidence Queues",
		"Failed Handoff Events",
		counts.get("failed_handoff_count") == 0,
		f"Failed handoffs: {counts.get('failed_handoff_count')}",
	)
	add_check(
		"Intake / Evidence Queues",
		"Blocked Evidence Count",
		counts.get("blocked_evidence_count") == 0,
		f"Blocked evidence: {counts.get('blocked_evidence_count')}",
	)
	add_check(
		"Intake / Evidence Queues",
		"Exception Evidence Count",
		counts.get("exception_evidence_count") == 0,
		f"Exception evidence: {counts.get('exception_evidence_count')}",
	)

	return get_columns(), rows, None, None, get_report_summary(rows)


def get_columns():
	return [
		{"label": _("Check Category"), "fieldname": "category", "fieldtype": "Data", "width": 220},
		{
			"label": _("Requirement Check"),
			"fieldname": "check_name",
			"fieldtype": "Data",
			"width": 280,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Details / Reason"), "fieldname": "details", "fieldtype": "Data", "width": 400},
	]


def get_report_summary(rows):
	passes = sum(1 for row in rows if row["status"] == "Pass")
	fails = sum(1 for row in rows if row["status"] == "Fail")
	return [
		{"label": _("Passed Checks"), "value": passes, "datatype": "Int", "indicator": "Green"},
		{
			"label": _("Failed Checks"),
			"value": fails,
			"datatype": "Int",
			"indicator": "Red" if fails > 0 else "Green",
		},
	]
