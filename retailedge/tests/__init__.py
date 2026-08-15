"""RetailEdge test-package compatibility helpers.

The standalone CI site intentionally does not install POSNext. Unit tests that
exercise mocked POSNext shift-query internals must therefore bypass Frappe's
Link-query input decorator, which validates the real target DocType before the
mocked function body can run.

This changes test-process imports only; production runtime code remains
unchanged and continues to use Frappe's sanitized whitelisted endpoint.
"""

from retailedge import daily_sales_audit as _daily_sales_audit


def _unwrap_search_query(function):
	while hasattr(function, "__wrapped__"):
		function = function.__wrapped__
	return function


_daily_sales_audit.search_daily_sales_audit_opening_shifts = _unwrap_search_query(
	_daily_sales_audit.search_daily_sales_audit_opening_shifts
)
