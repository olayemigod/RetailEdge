from __future__ import annotations

from collections.abc import Callable

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.pdf import get_pdf

from retailedge.branch_performance_dashboard import get_branch_performance_dashboard_data
from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.reporting_files import (
	MIME_TYPES,
	_csv_bytes,
	_normalise_dataset,
	_normalize_options,
	_report_html,
	_select_columns,
	_set_download_response,
	_table_matrix,
	_xlsx_bytes,
)

DashboardHandler = Callable[[dict], dict]


def _dashboard_handler(scope_key: str) -> DashboardHandler:
	handlers: dict[str, DashboardHandler] = {
		"branch-performance": lambda filters: get_branch_performance_dashboard_data(filters=filters),
	}
	handler = handlers.get(scope_key)
	if not handler:
		frappe.throw(_("Unsupported RetailEdge dashboard export scope."))
	return handler


def get_dashboard_dataset(scope_key: str, filters: dict) -> dict:
	return _dashboard_handler(scope_key)(filters)


@frappe.whitelist()
def download_dashboard(scope_key: str, filters=None, options=None):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else dict(filters or {})
	options = _normalize_options(options)
	require_dashboard_action(
		scope_key,
		"export",
		company=filters.get("company"),
		branch=filters.get("branch"),
	)
	dataset = get_dashboard_dataset(scope_key, filters)
	columns, rows, summary = _normalise_dataset(dataset)
	columns = _select_columns(columns, options["columns"])
	title = str(dataset.get("title") or scope_key.replace("-", " ").title())
	matrix, header_index = _table_matrix(title, filters, columns, rows, summary, options)
	file_format = options["format"]
	if file_format == "csv":
		content = _csv_bytes(matrix)
	elif file_format == "xlsx":
		content = _xlsx_bytes(matrix, title, header_index, options["include_filters"])
	else:
		pdf_html = _report_html(title, filters, columns, rows, summary, options)
		orientation = "Landscape" if options["orientation"] == "landscape" else "Portrait"
		content = get_pdf(pdf_html, options={"orientation": orientation})
	_set_download_response(content, scope_key, file_format)
	frappe.local.response.content_type = MIME_TYPES[file_format]


@frappe.whitelist()
def get_dashboard_print_html(scope_key: str, filters=None) -> dict:
	filters = frappe.parse_json(filters) if isinstance(filters, str) else dict(filters or {})
	require_dashboard_action(
		scope_key,
		"print",
		company=filters.get("company"),
		branch=filters.get("branch"),
	)
	dataset = get_dashboard_dataset(scope_key, filters)
	columns, rows, summary = _normalise_dataset(dataset)
	options = {
		"include_title": True,
		"include_generated_metadata": True,
		"include_filters": True,
		"include_summary": True,
		"include_letterhead": True,
		"repeat_table_headings": True,
	}
	title = str(dataset.get("title") or scope_key.replace("-", " ").title())
	return {
		"html": _report_html(title, filters, _select_columns(columns, []), rows, summary, options),
		"title": title,
		"row_count": cint(len(rows)),
	}
