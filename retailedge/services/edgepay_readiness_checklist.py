from __future__ import annotations

import frappe

from retailedge.integrations.edgepay_service import get_edgepay_service_config, is_edgepay_service_configured


def get_edgepay_retail_readiness_summary():
	"""Compile RetailEdge-side readiness for the remote EdgePay service boundary.

	RetailEdge owns only service connectivity, local evidence, reconciliation and
	accounting handoff. Provider credentials, provider readiness and payment
	processing governance belong to the centrally hosted EdgePay service.
	"""
	config = get_edgepay_service_config()
	service_configured = is_edgepay_service_configured()

	return {
		"service": {
			"configured": service_configured,
			"url_configured": bool(config["base_url"]),
			"authentication_configured": bool(
				config["bearer_token"] or (config["api_key"] and config["api_secret"])
			),
			"authentication_mode": (
				"Bearer Token"
				if config["bearer_token"]
				else "Frappe API Token"
				if config["api_key"] and config["api_secret"]
				else "Not Configured"
			),
			"verify_ssl": bool(config["verify_ssl"]),
			"timeout_seconds": config["timeout"],
			"provider_configuration_owned_by_edgepay": True,
			"local_edgepay_app_required": False,
		},
		"doctypes": {
			"evidence_doctype_exists": bool(
				frappe.db.exists("DocType", "RetailEdge EdgePay Payment Evidence")
			),
			"handoff_log_doctype_exists": bool(frappe.db.exists("DocType", "RetailEdge EdgePay Handoff Log")),
		},
		"reports": {
			"readiness_report_exists": bool(
				frappe.db.exists("Report", "RetailEdge EdgePay Reconciliation Readiness")
			),
			"summary_report_exists": bool(
				frappe.db.exists("Report", "RetailEdge EdgePay Payment Evidence Summary")
			),
			"lifecycle_report_exists": bool(
				frappe.db.exists("Report", "RetailEdge EdgePay Lifecycle Status")
			),
			"rollout_monitor_report_exists": bool(
				frappe.db.exists("Report", "RetailEdge EdgePay Rollout Monitor")
			),
		},
		"endpoints": {"endpoints_gated_against_guest": True},
		"counts": {
			"pending_handoff_count": _count_if_available(
				"RetailEdge EdgePay Handoff Log", {"processing_status": "Pending"}
			),
			"failed_handoff_count": _count_if_available(
				"RetailEdge EdgePay Handoff Log", {"processing_status": "Failed"}
			),
			"blocked_evidence_count": _count_if_available(
				"RetailEdge EdgePay Payment Evidence", {"reconciliation_status": "Blocked"}
			),
			"exception_evidence_count": _count_if_available(
				"RetailEdge EdgePay Payment Evidence", {"reconciliation_status": "Exception"}
			),
		},
	}


def _count_if_available(doctype, filters):
	if not frappe.db.exists("DocType", doctype):
		return 0
	return frappe.db.count(doctype, filters)
