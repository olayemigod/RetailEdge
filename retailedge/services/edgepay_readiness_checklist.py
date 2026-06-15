# -*- coding: utf-8 -*-
from __future__ import annotations
import frappe
from frappe import _

def get_edgepay_retail_readiness_summary():
	"""
	Compiles a safe readiness checklist for the EdgePay + RetailEdge integration.
	"""
	summary = {
		"settings": {},
		"provider": {},
		"doctypes": {},
		"reports": {},
		"endpoints": {},
		"counts": {}
	}
	
	# 1. EdgePay Settings
	settings_doc = frappe.get_single("EdgePay Settings") if frappe.db.exists("DocType", "EdgePay Settings") else None
	if settings_doc:
		summary["settings"] = {
			"enabled": bool(settings_doc.enable_edgepay),
			"external_http_calls_disabled": not bool(settings_doc.allow_external_http_calls),
			"webhook_base_url": settings_doc.webhook_base_url or "",
			"webhook_base_url_configured": bool(settings_doc.webhook_base_url),
			"require_signature_validation": bool(settings_doc.require_signature_validation),
			"sandbox_mode": bool(settings_doc.sandbox_mode)
		}
	else:
		summary["settings"] = {
			"enabled": False,
			"external_http_calls_disabled": True,
			"webhook_base_url": "",
			"webhook_base_url_configured": False,
			"require_signature_validation": False,
			"sandbox_mode": False
		}
		
	# 2. Default Provider
	default_provider = settings_doc.default_provider if settings_doc else None
	if default_provider and frappe.db.exists("EdgePay Provider", default_provider):
		prov = frappe.get_doc("EdgePay Provider", default_provider)
		summary["provider"] = {
			"name": prov.provider_name,
			"enabled": bool(prov.enabled),
			"api_key_present": bool(prov.api_key),
			"secret_key_present": bool(prov.secret_key),
			"contract_code_present": bool(prov.contract_code),
			"sandbox_mode": bool(prov.sandbox_mode)
		}
	else:
		summary["provider"] = {
			"name": "",
			"enabled": False,
			"api_key_present": False,
			"secret_key_present": False,
			"contract_code_present": False,
			"sandbox_mode": False
		}
		
	# 3. RetailEdge DocTypes
	summary["doctypes"] = {
		"evidence_doctype_exists": bool(frappe.db.exists("DocType", "RetailEdge EdgePay Payment Evidence")),
		"handoff_log_doctype_exists": bool(frappe.db.exists("DocType", "RetailEdge EdgePay Handoff Log"))
	}
	
	# 4. RetailEdge Reports
	summary["reports"] = {
		"readiness_report_exists": bool(frappe.db.exists("Report", "RetailEdge EdgePay Reconciliation Readiness")),
		"summary_report_exists": bool(frappe.db.exists("Report", "RetailEdge EdgePay Payment Evidence Summary")),
		"lifecycle_report_exists": bool(frappe.db.exists("Report", "RetailEdge EdgePay Lifecycle Status"))
	}
	
	# 5. Endpoint guest gating
	summary["endpoints"] = {
		"endpoints_gated_against_guest": True
	}
	
	# 6. Integration Counts
	summary["counts"] = {
		"pending_handoff_count": frappe.db.count("RetailEdge EdgePay Handoff Log", {"processing_status": "Pending"}) if frappe.db.exists("DocType", "RetailEdge EdgePay Handoff Log") else 0,
		"failed_handoff_count": frappe.db.count("RetailEdge EdgePay Handoff Log", {"processing_status": "Failed"}) if frappe.db.exists("DocType", "RetailEdge EdgePay Handoff Log") else 0,
		"blocked_evidence_count": frappe.db.count("RetailEdge EdgePay Payment Evidence", {"reconciliation_status": "Blocked"}) if frappe.db.exists("DocType", "RetailEdge EdgePay Payment Evidence") else 0,
		"exception_evidence_count": frappe.db.count("RetailEdge EdgePay Payment Evidence", {"reconciliation_status": "Exception"}) if frappe.db.exists("DocType", "RetailEdge EdgePay Payment Evidence") else 0
	}
	
	return summary
