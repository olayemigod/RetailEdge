# -*- coding: utf-8 -*-
from __future__ import annotations
import frappe
from frappe import _
from retailedge.services.edgepay_readiness_checklist import get_edgepay_retail_readiness_summary

def execute(filters=None):
	summary = get_edgepay_retail_readiness_summary()
	
	rows = []
	
	# Helper to append rows
	def add_check(category, check_name, passed, details):
		status = "Pass" if passed else "Fail"
		rows.append({
			"category": category,
			"check_name": check_name,
			"status": status,
			"details": details
		})

	# EdgePay Settings Checks
	settings = summary.get("settings", {})
	add_check("EdgePay Settings", "EdgePay Enabled", settings.get("enabled"), "EdgePay integration is enabled." if settings.get("enabled") else "EdgePay integration is disabled.")
	add_check("EdgePay Settings", "External HTTP Calls Disabled By Default", settings.get("external_http_calls_disabled"), "Live API calls are disabled by default (safer)." if settings.get("external_http_calls_disabled") else "WARNING: Live API calls are allowed.")
	add_check("EdgePay Settings", "Webhook Signature Validation Required", settings.get("require_signature_validation"), "Signature validation is required." if settings.get("require_signature_validation") else "WARNING: Signature validation is disabled.")
	add_check("EdgePay Settings", "Webhook Base URL Configured", settings.get("webhook_base_url_configured"), f"Webhook base URL: {settings.get('webhook_base_url')}" if settings.get("webhook_base_url_configured") else "Webhook base URL is not set.")

	# Provider Checks
	provider = summary.get("provider", {})
	provider_label = f"Provider ({provider.get('name') or 'None'})"
	add_check(provider_label, "Provider Enabled", provider.get("enabled"), "Provider is enabled." if provider.get("enabled") else "Provider is disabled.")
	add_check(provider_label, "API Key / Public Key Present", provider.get("api_key_present"), "API key exists (value is hidden)." if provider.get("api_key_present") else "API key is missing.")
	add_check(provider_label, "Secret Key Present", provider.get("secret_key_present"), "Secret key exists (value is hidden)." if provider.get("secret_key_present") else "Secret key is missing.")
	add_check(provider_label, "Contract Code Present", provider.get("contract_code_present"), "Contract code exists." if provider.get("contract_code_present") else "Contract code is missing.")
	add_check(provider_label, "Sandbox Mode", provider.get("sandbox_mode"), "Provider is running in sandbox mode." if provider.get("sandbox_mode") else "Provider is running in live/production mode.")

	# DocType existence
	doctypes = summary.get("doctypes", {})
	add_check("RetailEdge DocTypes", "Payment Evidence DocType Exists", doctypes.get("evidence_doctype_exists"), "RetailEdge EdgePay Payment Evidence DocType exists.")
	add_check("RetailEdge DocTypes", "Handoff Log DocType Exists", doctypes.get("handoff_log_doctype_exists"), "RetailEdge EdgePay Handoff Log DocType exists.")

	# Report existence
	reports = summary.get("reports", {})
	add_check("RetailEdge Reports", "Reconciliation Readiness Report Exists", reports.get("readiness_report_exists"), "RetailEdge EdgePay Reconciliation Readiness report exists.")
	add_check("RetailEdge Reports", "Payment Evidence Summary Report Exists", reports.get("summary_report_exists"), "RetailEdge EdgePay Payment Evidence Summary report exists.")
	add_check("RetailEdge Reports", "Lifecycle Status Report Exists", reports.get("lifecycle_report_exists"), "RetailEdge EdgePay Lifecycle Status report exists.")
	add_check("RetailEdge Reports", "Rollout Monitor Report Exists", reports.get("rollout_monitor_report_exists"), "RetailEdge EdgePay Rollout Monitor report exists.")

	# Endpoint safety gating
	endpoints = summary.get("endpoints", {})
	add_check("Role & Permission Safety", "Sensitive Endpoints Block Guest Access", endpoints.get("endpoints_gated_against_guest"), "All sensitive confirmation/submit endpoints block guest access." if endpoints.get("endpoints_gated_against_guest") else "WARNING: Some sensitive endpoints are accessible by guests.")

	# Handoff and Evidence queues
	counts = summary.get("counts", {})
	add_check("Intake / Evidence Queues", "Pending Handoff Events", counts.get("pending_handoff_count") == 0, f"Pending handoffs: {counts.get('pending_handoff_count')}")
	add_check("Intake / Evidence Queues", "Failed Handoff Events", counts.get("failed_handoff_count") == 0, f"Failed handoffs: {counts.get('failed_handoff_count')}")
	add_check("Intake / Evidence Queues", "Blocked Evidence Count", counts.get("blocked_evidence_count") == 0, f"Blocked evidence: {counts.get('blocked_evidence_count')}")
	add_check("Intake / Evidence Queues", "Exception Evidence Count", counts.get("exception_evidence_count") == 0, f"Exception evidence: {counts.get('exception_evidence_count')}")

	return get_columns(), rows, None, None, get_report_summary(rows)

def get_columns():
	return [
		{"label": _("Check Category"), "fieldname": "category", "fieldtype": "Data", "width": 220},
		{"label": _("Requirement Check"), "fieldname": "check_name", "fieldtype": "Data", "width": 280},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Details / Reason"), "fieldname": "details", "fieldtype": "Data", "width": 400}
	]

def get_report_summary(rows):
	passes = sum(1 for r in rows if r["status"] == "Pass")
	fails = sum(1 for r in rows if r["status"] == "Fail")
	return [
		{"label": _("Passed Checks"), "value": passes, "datatype": "Int", "indicator": "Green"},
		{"label": _("Failed Checks"), "value": fails, "datatype": "Int", "indicator": "Red" if fails > 0 else "Green"}
	]
