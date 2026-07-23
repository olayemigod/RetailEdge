from __future__ import annotations

from retailedge.api.permission import has_app_permission


def get_product_availability() -> dict | None:
	"""Return RetailEdge only when it is available to the current user.

	EdgeSuite UI consumes this final availability result. It must not reproduce
	RetailEdge permission or access rules in the browser.
	"""
	if not has_app_permission():
		return None
	return {
		"key": "retailedge",
		"label": "RetailEdge",
		"product": "RetailEdge",
		"icon": "grid",
		"home_route": "/app/retailedge-home",
		"route_patterns": [
			"/app/retailedge*",
			"/app/salesperson-performance-dashboard*",
			"/app/query-report/RetailEdge*",
		],
		"order": 20,
	}
