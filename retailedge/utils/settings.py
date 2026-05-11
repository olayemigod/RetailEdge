import frappe


def get_retailedge_settings():
	return frappe.get_cached_doc("RetailEdge Settings")
