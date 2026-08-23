from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, today

from erpnext.stock.report.stock_ageing.stock_ageing import (
	FIFO_DATE_INDEX,
	FIFO_VALUE_INDEX,
	FIFOSlots,
	get_average_age,
	get_report_fifo_queue,
	get_slot_qty,
)

from retailedge.cost_visibility import should_hide_cost_price
from retailedge.stock_position import (
	MAX_ITEM_SCOPE,
	_assert_report_access,
	_coerce_filters,
	_resolve_item_scope,
	_resolve_warehouse_scope,
	_validate_filters,
)

DEFAULT_AGE_RANGES = (30, 60, 90, 180)
DEFAULT_AGED_THRESHOLD_DAYS = 90
MAX_AGE_BUCKETS = 6
MAX_AGE_RANGE_DAYS = 3650
MAX_AGEING_SLE_ROWS = 50000
MAX_BUNDLE_ENTRY_ROWS = 50000

_BASE_SLE_FIELDS = (
	"name",
	"posting_date",
	"item_code",
	"warehouse",
	"actual_qty",
	"voucher_type",
	"voucher_no",
	"voucher_detail_no",
	"serial_no",
	"batch_no",
	"qty_after_transaction",
	"serial_and_batch_bundle",
)
_COST_SLE_FIELDS = ("stock_value_difference", "valuation_rate")


@frappe.whitelist()
def get_inventory_ageing(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Return current inventory ageing using ERPNext v16 FIFO-slot semantics.

	RetailEdge owns only permission-safe scope resolution, bounded reads, cost
	visibility, and presentation. ERPNext ``FIFOSlots`` remains the ageing engine.
	The service is intentionally lazy because accurate ageing requires complete
	stock-ledger history for the selected scope.
	"""
	filters = _coerce_filters(filters)
	_normalise_filters(filters)
	_validate_filters(filters)
	_assert_report_access(filters)
	_assert_sle_read_permission()

	warehouses = _resolve_warehouse_scope(filters)
	item_scope = _resolve_item_scope(filters)
	age_ranges = _normalise_age_ranges(filters.get("age_ranges"))
	aged_threshold_days = _normalise_aged_threshold(filters.get("aged_threshold_days"))
	show_costs = not should_hide_cost_price()
	as_of_date = getdate(filters.as_of_date)

	if item_scope == []:
		return _empty_payload(
			filters,
			warehouses=warehouses,
			age_ranges=age_ranges,
			aged_threshold_days=aged_threshold_days,
			show_costs=show_costs,
		)

	sle_filters: dict[str, Any] = {
		"company": filters.company,
		"warehouse": ["in", warehouses],
		"posting_date": ["<=", str(as_of_date)],
		"is_cancelled": 0,
	}
	if filters.get("item_code"):
		sle_filters["item_code"] = filters.item_code
	elif item_scope is not None:
		sle_filters["item_code"] = ["in", item_scope]

	sle_rows = frappe.get_list(
		"Stock Ledger Entry",
		filters=sle_filters,
		fields=_sle_fields(show_costs=show_costs),
		order_by="posting_datetime asc, creation asc, name asc",
		limit=MAX_AGEING_SLE_ROWS + 1,
	)
	if len(sle_rows) > MAX_AGEING_SLE_ROWS:
		frappe.throw(
			_(
				"More than {0} stock ledger rows are required to reconstruct ageing for this scope. Narrow the Branch, Warehouse, Item Group, or Item before loading Inventory Ageing."
			).format(MAX_AGEING_SLE_ROWS)
		)

	item_codes = sorted({str(row.item_code) for row in sle_rows if row.item_code})
	item_map = _get_ageing_item_metadata(item_codes)
	permitted_sle = [row for row in sle_rows if str(row.item_code or "") in item_map]
	engine_rows = [
		_to_fifo_row(row, item=item_map[str(row.item_code)], show_costs=show_costs)
		for row in permitted_sle
	]

	bundle_serials, bundle_batches, batchwise_valuation, bundle_entry_count = _get_bundle_context(
		engine_rows,
		show_costs=show_costs,
	)
	valuation_methods = {
		item_code: str(item.get("valuation_method") or "")
		for item_code, item in item_map.items()
		if item.get("valuation_method")
	}

	engine = _ScopedFIFOSlots(
		filters=frappe._dict(
			{
				"company": filters.company,
				"to_date": str(as_of_date),
				"show_warehouse_wise_stock": 1,
			}
		),
		sle=engine_rows,
		bundle_serials=bundle_serials,
		bundle_batches=bundle_batches,
		batchwise_valuation=batchwise_valuation,
		valuation_methods=valuation_methods,
	)
	location_details = engine.generate()
	item_details = engine._aggregate_details_by_item(location_details)

	location_rows = _format_details(
		location_details,
		as_of_date=as_of_date,
		age_ranges=age_ranges,
		aged_threshold_days=aged_threshold_days,
		show_costs=show_costs,
		warehouse_wise=True,
	)
	item_rows = _format_details(
		item_details,
		as_of_date=as_of_date,
		age_ranges=age_ranges,
		aged_threshold_days=aged_threshold_days,
		show_costs=show_costs,
		warehouse_wise=False,
	)

	return {
		"columns": _columns(age_ranges, show_costs=show_costs),
		"rows": item_rows,
		"locations": location_rows,
		"summary": _summary(item_rows, show_costs=show_costs),
		"show_costs": int(show_costs),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
			"item_group": filters.get("item_group") or "",
			"item_code": filters.get("item_code") or "",
			"as_of_date": str(as_of_date),
			"age_ranges": list(age_ranges),
			"aged_threshold_days": aged_threshold_days,
		},
		"scan": {
			"sle_rows": len(sle_rows),
			"permitted_sle_rows": len(permitted_sle),
			"bundle_entry_rows": bundle_entry_count,
			"sle_limit": MAX_AGEING_SLE_ROWS,
			"bundle_entry_limit": MAX_BUNDLE_ENTRY_ROWS,
			"item_limit": MAX_ITEM_SCOPE,
		},
		"metadata": {
			"ageing_truth": "ERPNext v16 Stock Ageing FIFOSlots",
			"fifo_algorithm_reused": True,
			"full_history_required": True,
			"current_position_only": True,
			"cost_visibility": (
				"Value fields are queried and returned only when RetailEdge cost visibility allows them."
				if show_costs
				else "Stock value and valuation fields were not queried from Stock Ledger Entry or Serial and Batch Entry."
			),
			"child_query_contract": (
				"Serial and Batch Entry rows are read only for submitted bundle names referenced by permission-filtered Stock Ledger Entries."
			),
			"read_only": True,
			"persistent_derived_truth": False,
		},
	}


def _normalise_filters(filters: frappe._dict) -> None:
	if not filters.get("company"):
		filters.company = str(frappe.defaults.get_user_default("Company") or "").strip()
	requested_as_of = getdate(filters.get("as_of_date") or today())
	if requested_as_of != getdate(today()):
		frappe.throw(
			_(
				"Inventory Ageing is currently a current-position control. Historical As Of dates are not supported on this R10 view."
			)
		)
	filters.as_of_date = str(requested_as_of)


def _normalise_age_ranges(value: Any) -> tuple[int, ...]:
	if value in (None, ""):
		return DEFAULT_AGE_RANGES
	if isinstance(value, str):
		value = [part.strip() for part in value.split(",") if part.strip()]
	if not isinstance(value, (list, tuple)):
		frappe.throw(_("Inventory ageing ranges must be a comma-separated or list of day limits."))
	try:
		ranges = tuple(cint(part) for part in value)
	except (TypeError, ValueError):
		frappe.throw(_("Inventory ageing ranges contain an invalid day limit."))
	if not ranges or len(ranges) > MAX_AGE_BUCKETS:
		frappe.throw(_("Inventory ageing requires between 1 and {0} age limits.").format(MAX_AGE_BUCKETS))
	if any(day < 1 or day > MAX_AGE_RANGE_DAYS for day in ranges):
		frappe.throw(_("Inventory ageing day limits must be between 1 and {0}.").format(MAX_AGE_RANGE_DAYS))
	if tuple(sorted(set(ranges))) != ranges:
		frappe.throw(_("Inventory ageing day limits must be unique and strictly increasing."))
	return ranges


def _normalise_aged_threshold(value: Any) -> int:
	threshold = DEFAULT_AGED_THRESHOLD_DAYS if value in (None, "") else cint(value)
	if threshold < 1 or threshold > MAX_AGE_RANGE_DAYS:
		frappe.throw(_("Aged stock threshold must be between 1 and {0} days.").format(MAX_AGE_RANGE_DAYS))
	return threshold


def _sle_fields(*, show_costs: bool) -> list[str]:
	fields = list(_BASE_SLE_FIELDS)
	if show_costs:
		fields.extend(_COST_SLE_FIELDS)
	return fields


def _assert_sle_read_permission() -> None:
	if not frappe.has_permission("Stock Ledger Entry", "read"):
		frappe.throw(
			_("You do not have permission to view historical stock movements."),
			frappe.PermissionError,
		)


def _get_ageing_item_metadata(item_codes: list[str]) -> dict[str, frappe._dict]:
	if not item_codes:
		return {}
	rows = frappe.get_list(
		"Item",
		filters={"name": ["in", item_codes], "disabled": 0, "is_stock_item": 1},
		fields=[
			"name",
			"item_name",
			"description",
			"item_group",
			"brand",
			"stock_uom",
			"has_batch_no",
			"has_serial_no",
			"valuation_method",
		],
		order_by="name asc",
		limit=MAX_ITEM_SCOPE + 1,
	)
	if len(rows) > MAX_ITEM_SCOPE:
		frappe.throw(_("More than {0} permitted Items are in ageing scope. Narrow the Item Group or Item first.").format(MAX_ITEM_SCOPE))
	return {str(row.name): row for row in rows}


def _to_fifo_row(row: frappe._dict, *, item: frappe._dict, show_costs: bool) -> frappe._dict:
	return frappe._dict(
		{
			"name": str(row.item_code),
			"item_name": item.get("item_name") or row.item_code,
			"description": item.get("description") or "",
			"item_group": item.get("item_group") or "",
			"brand": item.get("brand") or "",
			"stock_uom": item.get("stock_uom") or "",
			"has_batch_no": cint(item.get("has_batch_no")),
			"has_serial_no": cint(item.get("has_serial_no")),
			"warehouse": row.get("warehouse"),
			"actual_qty": flt(row.get("actual_qty")),
			"stock_value_difference": flt(row.get("stock_value_difference")) if show_costs else 0.0,
			"valuation_rate": flt(row.get("valuation_rate")) if show_costs else 0.0,
			"posting_date": row.get("posting_date"),
			"voucher_type": row.get("voucher_type"),
			"voucher_no": row.get("voucher_no"),
			"voucher_detail_no": row.get("voucher_detail_no"),
			"serial_no": row.get("serial_no"),
			"batch_no": row.get("batch_no"),
			"qty_after_transaction": flt(row.get("qty_after_transaction")),
			"serial_and_batch_bundle": row.get("serial_and_batch_bundle"),
		}
	)


def _get_bundle_context(
	engine_rows: list[frappe._dict],
	*,
	show_costs: bool,
) -> tuple[frappe._dict, frappe._dict, dict[str, bool], int]:
	bundle_names = sorted({str(row.serial_and_batch_bundle) for row in engine_rows if row.serial_and_batch_bundle})
	direct_batch_names = {str(row.batch_no) for row in engine_rows if row.batch_no}
	if not bundle_names:
		batchwise = _get_batchwise_valuation(direct_batch_names)
		return frappe._dict(), frappe._dict(), batchwise, 0

	permitted_bundles = frappe.get_list(
		"Serial and Batch Bundle",
		filters={"name": ["in", bundle_names], "docstatus": 1},
		pluck="name",
		order_by="name asc",
		limit=len(bundle_names) + 1,
	)
	if set(permitted_bundles) != set(bundle_names):
		frappe.throw(
			_("You do not have permission to evaluate all Serial and Batch Bundles required for this ageing scope."),
			frappe.PermissionError,
		)

	entry = frappe.qb.DocType("Serial and Batch Entry")
	query = (
		frappe.qb.from_(entry)
		.select(entry.parent, entry.serial_no, entry.batch_no, entry.qty)
		.where(entry.parent.isin(permitted_bundles))
		.orderby(entry.parent)
		.orderby(entry.idx)
		.limit(MAX_BUNDLE_ENTRY_ROWS + 1)
	)
	if show_costs:
		query = query.select(entry.stock_value_difference)
	entry_rows = query.run(as_dict=True)
	if len(entry_rows) > MAX_BUNDLE_ENTRY_ROWS:
		frappe.throw(
			_("More than {0} Serial/Batch bundle rows are required for this ageing scope. Narrow the scope first.").format(MAX_BUNDLE_ENTRY_ROWS)
		)

	batch_names = set(direct_batch_names)
	batch_names.update(str(row.batch_no) for row in entry_rows if row.get("batch_no"))
	batchwise = _get_batchwise_valuation(batch_names)
	serials: dict[str, list[str]] = defaultdict(list)
	batches: dict[str, list[list[Any]]] = defaultdict(list)
	for row in entry_rows:
		parent = str(row.parent)
		if row.get("serial_no"):
			serials[parent].append(str(row.serial_no))
		if row.get("batch_no"):
			batch_no = str(row.batch_no)
			batches[parent].append(
				[
					batch_no.upper(),
					bool(batchwise.get(batch_no)),
					abs(flt(row.get("qty"))),
					abs(flt(row.get("stock_value_difference"))) if show_costs else 0.0,
				]
			)
	return frappe._dict(serials), frappe._dict(batches), batchwise, len(entry_rows)


def _get_batchwise_valuation(batch_names: set[str]) -> dict[str, bool]:
	batch_names = {name for name in batch_names if name}
	if not batch_names:
		return {}
	rows = frappe.get_list(
		"Batch",
		filters={"name": ["in", sorted(batch_names)]},
		fields=["name", "use_batchwise_valuation"],
		order_by="name asc",
		limit=len(batch_names) + 1,
	)
	result = {str(row.name): bool(cint(row.use_batchwise_valuation)) for row in rows}
	if set(result) != batch_names:
		frappe.throw(
			_("You do not have permission to evaluate all Batch records required for this ageing scope."),
			frappe.PermissionError,
		)
	return result


class _ScopedFIFOSlots(FIFOSlots):
	"""ERPNext FIFO engine with child lookups constrained to pre-approved scope."""

	def __init__(
		self,
		*,
		filters: frappe._dict,
		sle: list[frappe._dict],
		bundle_serials: frappe._dict,
		bundle_batches: frappe._dict,
		batchwise_valuation: dict[str, bool],
		valuation_methods: dict[str, str],
	):
		super().__init__(filters=filters, sle=sle)
		self._scoped_bundle_serials = bundle_serials
		self._scoped_bundle_batches = bundle_batches
		self.batchwise_valuation_by_batch.update(batchwise_valuation)
		self.valuation_method_by_item.update(valuation_methods)

	def _get_bundle_wise_details(self, stock_ledger_entries):
		return self._scoped_bundle_serials, self._scoped_bundle_batches

	def _get_batchwise_valuation(self, batch_no: str):
		if batch_no not in self.batchwise_valuation_by_batch:
			frappe.throw(
				_("Batch {0} is outside the permission-safe ageing context.").format(batch_no),
				frappe.PermissionError,
			)
		return self.batchwise_valuation_by_batch[batch_no]

	def prepare_stock_reco_voucher_wise_count(self):
		self.stock_reco_voucher_wise_count = frappe._dict()
		candidate_counts: dict[str, int] = defaultdict(int)
		candidate_voucher: dict[str, str] = {}
		for row in self.sle or []:
			if row.voucher_type != "Stock Reconciliation" or not row.has_serial_no or not row.voucher_detail_no:
				continue
			detail = str(row.voucher_detail_no)
			candidate_counts[detail] += 1
			candidate_voucher[detail] = str(row.voucher_no or "")
		candidates = sorted(detail for detail, count in candidate_counts.items() if count == 1)
		if not candidates:
			return

		voucher_names = sorted({candidate_voucher[detail] for detail in candidates if candidate_voucher.get(detail)})
		permitted_vouchers = frappe.get_list(
			"Stock Reconciliation",
			filters={"name": ["in", voucher_names], "docstatus": ["<", 2]},
			pluck="name",
			order_by="name asc",
			limit=len(voucher_names) + 1,
		)
		if set(permitted_vouchers) != set(voucher_names):
			frappe.throw(
				_("You do not have permission to evaluate Stock Reconciliation history required for serialised stock ageing."),
				frappe.PermissionError,
			)

		row_table = frappe.qb.DocType("Stock Reconciliation Item")
		rows = (
			frappe.qb.from_(row_table)
			.select(row_table.name, row_table.current_qty, row_table.qty)
			.where(row_table.name.isin(candidates))
			.where(row_table.parent.isin(permitted_vouchers))
		).run(as_dict=True)
		for row in rows:
			if row.get("qty") and row.get("current_qty"):
				self.stock_reco_voucher_wise_count[str(row.name)] = flt(row.current_qty)


def _format_details(
	details_map: dict,
	*,
	as_of_date,
	age_ranges: tuple[int, ...],
	aged_threshold_days: int,
	show_costs: bool,
	warehouse_wise: bool,
) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	for key, item_dict in details_map.items():
		total_qty = flt(item_dict.get("total_qty"))
		if not total_qty:
			continue
		details = item_dict.get("details") or frappe._dict()
		fifo_queue = get_report_fifo_queue(
			item_dict.get("fifo_queue") or [],
			bool(item_dict.get("has_batch_no")),
		)
		if not fifo_queue:
			continue
		warehouse = str(key[1]) if warehouse_wise and isinstance(key, tuple) and len(key) > 1 else ""
		rows.append(
			_format_fifo_row(
				item_code=str(details.get("name") or (key[0] if isinstance(key, tuple) else key)),
				item_name=str(details.get("item_name") or details.get("name") or ""),
				item_group=str(details.get("item_group") or ""),
				stock_uom=str(details.get("stock_uom") or ""),
				warehouse=warehouse,
				total_qty=total_qty,
				fifo_queue=fifo_queue,
				as_of_date=as_of_date,
				age_ranges=age_ranges,
				aged_threshold_days=aged_threshold_days,
				show_costs=show_costs,
			)
		)
	rows.sort(key=lambda row: (-flt(row.get("aged_qty")), -flt(row.get("average_age_days")), row["item_code"], row.get("warehouse") or ""))
	return rows


def _format_fifo_row(
	*,
	item_code: str,
	item_name: str,
	item_group: str,
	stock_uom: str,
	warehouse: str,
	total_qty: float,
	fifo_queue: list,
	as_of_date,
	age_ranges: tuple[int, ...],
	aged_threshold_days: int,
	show_costs: bool,
) -> dict[str, Any]:
	bucket_specs = _age_bucket_specs(age_ranges)
	buckets = [
		{"key": key, "from_days": start, "to_days": end, "qty": 0.0, "value": 0.0}
		for key, start, end in bucket_specs
	]
	aged_qty = 0.0
	aged_value = 0.0
	stock_value = 0.0
	for slot in fifo_queue:
		posting_date = slot[FIFO_DATE_INDEX]
		if not posting_date:
			continue
		age = max(date_diff(as_of_date, posting_date), 0)
		qty = flt(get_slot_qty(slot))
		value = flt(slot[FIFO_VALUE_INDEX]) if show_costs else 0.0
		for bucket in buckets:
			if age >= bucket["from_days"] and (bucket["to_days"] is None or age <= bucket["to_days"]):
				bucket["qty"] = flt(bucket["qty"]) + qty
				if show_costs:
					bucket["value"] = flt(bucket["value"]) + value
				break
		if age > aged_threshold_days:
			aged_qty += qty
			if show_costs:
				aged_value += value
		if show_costs:
			stock_value += value

	positive_total = max(flt(total_qty), 0.0)
	positive_aged = max(flt(aged_qty), 0.0)
	if positive_aged <= 0:
		status = "Current"
	elif positive_total and positive_aged >= positive_total:
		status = "Aged"
	else:
		status = "Mixed"
	result: dict[str, Any] = {
		"item_code": item_code,
		"item_name": item_name or item_code,
		"item_group": item_group,
		"stock_uom": stock_uom,
		"warehouse": warehouse,
		"stock_qty": flt(total_qty),
		"average_age_days": get_average_age(fifo_queue, str(as_of_date)),
		"oldest_stock_age_days": max(date_diff(as_of_date, fifo_queue[0][FIFO_DATE_INDEX]), 0),
		"youngest_stock_age_days": max(date_diff(as_of_date, fifo_queue[-1][FIFO_DATE_INDEX]), 0),
		"aged_threshold_days": aged_threshold_days,
		"aged_qty": flt(aged_qty),
		"ageing_status": status,
		"age_buckets": buckets,
	}
	for bucket in buckets:
		result[f"{bucket['key']}_qty"] = flt(bucket["qty"])
		if show_costs:
			result[f"{bucket['key']}_value"] = flt(bucket["value"])
	if show_costs:
		result["stock_value"] = flt(stock_value)
		result["aged_stock_value"] = flt(aged_value)
	return result


def _age_bucket_specs(age_ranges: tuple[int, ...]) -> list[tuple[str, int, int | None]]:
	specs: list[tuple[str, int, int | None]] = []
	start = 0
	for end in age_ranges:
		specs.append((f"age_{start}_{end}", start, end))
		start = end + 1
	specs.append((f"age_{start}_plus", start, None))
	return specs


def _columns(age_ranges: tuple[int, ...], *, show_costs: bool) -> list[dict[str, Any]]:
	columns = [
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item"},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data"},
		{"fieldname": "item_group", "label": _("Item Group"), "fieldtype": "Link", "options": "Item Group"},
		{"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM"},
		{"fieldname": "stock_qty", "label": _("Stock Qty"), "fieldtype": "Float"},
		{"fieldname": "average_age_days", "label": _("Average Age (Days)"), "fieldtype": "Float"},
		{"fieldname": "oldest_stock_age_days", "label": _("Oldest Stock (Days)"), "fieldtype": "Int"},
		{"fieldname": "youngest_stock_age_days", "label": _("Youngest Stock (Days)"), "fieldtype": "Int"},
		{"fieldname": "aged_qty", "label": _("Aged Qty"), "fieldtype": "Float"},
		{"fieldname": "ageing_status", "label": _("Ageing Status"), "fieldtype": "Data"},
	]
	if show_costs:
		columns.extend(
			[
				{"fieldname": "stock_value", "label": _("FIFO Stock Value"), "fieldtype": "Currency"},
				{"fieldname": "aged_stock_value", "label": _("Aged Stock Value"), "fieldtype": "Currency"},
			]
		)
	for key, start, end in _age_bucket_specs(age_ranges):
		label = f"{start}–{end} days" if end is not None else f"{start}+ days"
		columns.append({"fieldname": f"{key}_qty", "label": _("Qty {0}").format(label), "fieldtype": "Float"})
		if show_costs:
			columns.append({"fieldname": f"{key}_value", "label": _("Value {0}").format(label), "fieldtype": "Currency"})
	return columns


def _summary(rows: list[dict[str, Any]], *, show_costs: bool) -> list[dict[str, Any]]:
	positive_qty = sum(max(flt(row.get("stock_qty")), 0.0) for row in rows)
	weighted_age = sum(max(flt(row.get("stock_qty")), 0.0) * flt(row.get("average_age_days")) for row in rows)
	cards = [
		{"label": _("Items with Stock"), "value": len(rows), "datatype": "Int"},
		{
			"label": _("Weighted Average Stock Age"),
			"value": weighted_age / positive_qty if positive_qty else 0.0,
			"datatype": "Float",
		},
		{
			"label": _("Items with Aged Stock"),
			"value": sum(1 for row in rows if flt(row.get("aged_qty")) > 0),
			"datatype": "Int",
		},
		{
			"label": _("Aged Stock Quantity"),
			"value": sum(max(flt(row.get("aged_qty")), 0.0) for row in rows),
			"datatype": "Float",
		},
	]
	if show_costs:
		cards.append(
			{
				"label": _("Aged Stock Value"),
				"value": sum(flt(row.get("aged_stock_value")) for row in rows),
				"datatype": "Currency",
			}
		)
	return cards


def _empty_payload(
	filters: frappe._dict,
	*,
	warehouses: list[str],
	age_ranges: tuple[int, ...],
	aged_threshold_days: int,
	show_costs: bool,
) -> dict[str, Any]:
	return {
		"columns": _columns(age_ranges, show_costs=show_costs),
		"rows": [],
		"locations": [],
		"summary": _summary([], show_costs=show_costs),
		"show_costs": int(show_costs),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
			"as_of_date": filters.as_of_date,
			"age_ranges": list(age_ranges),
			"aged_threshold_days": aged_threshold_days,
		},
		"scan": {"sle_rows": 0, "permitted_sle_rows": 0, "bundle_entry_rows": 0, "sle_limit": MAX_AGEING_SLE_ROWS},
		"metadata": {
			"ageing_truth": "ERPNext v16 Stock Ageing FIFOSlots",
			"fifo_algorithm_reused": True,
			"read_only": True,
			"persistent_derived_truth": False,
		},
	}
