from __future__ import annotations

import frappe

from retailedge.cost_visibility import get_cost_price_visibility_context
from retailedge.integrations.coreedge import get_coreedge_status
from retailedge.posting_date_control import get_posting_date_context


def boot_session(bootinfo):
	bootinfo.retailedge = {}

	for key, getter in {
		"posting_date": get_posting_date_context,
		"cost_visibility": get_cost_price_visibility_context,
		"coreedge": get_coreedge_status,
	}.items():
		try:
			bootinfo.retailedge[key] = getter()
		except Exception:
			bootinfo.retailedge[key] = {}
			frappe.logger("retailedge.boot").exception("Failed to populate RetailEdge boot context for %s", key)
