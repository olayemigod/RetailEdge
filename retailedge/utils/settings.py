import frappe


RETAILEDGE_SETTINGS_DOCTYPE = "RetailEdge Settings"


def get_retailedge_settings(use_cache=True):
	if use_cache:
		return frappe.get_cached_doc(RETAILEDGE_SETTINGS_DOCTYPE)
	return frappe.get_single(RETAILEDGE_SETTINGS_DOCTYPE)


def clear_retailedge_settings_cache():
	frappe.clear_document_cache(RETAILEDGE_SETTINGS_DOCTYPE, RETAILEDGE_SETTINGS_DOCTYPE)
