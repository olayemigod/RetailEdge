from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_profile import get_exact_branch_profile
from retailedge.operating_context import get_operating_context

RECENT_LIMIT = 12
SCOPE_NATIVE_PERMISSION = "native_permission"
SCOPE_COMPANY = "company"
SCOPE_CONFIGURED_BRANCH_STOCK = "configured_branch_stock"
SUPPORTED_PREVIEW_SCOPES = {
	SCOPE_NATIVE_PERMISSION,
	SCOPE_COMPANY,
	SCOPE_CONFIGURED_BRANCH_STOCK,
}
BRANCH_STOCK_PROFILE_FIELDS = (
	"default_warehouse",
	"default_source_warehouse",
	"default_target_warehouse",
	"default_returns_warehouse",
)

WORKSPACES: dict[str, dict[str, Any]] = {
	"service-warranty": {
		"page_route": "service-warranty-control",
		"title": "Service & Warranty",
		"eyebrow": "After-sales Control",
		"description": "Review warranty and maintenance activity in EdgeSuite, then use ERPNext for authoritative creation, editing, submission, scheduling, and lifecycle actions.",
		"sources": (
			{
				"kind": "doctype",
				"label": "Warranty Claims",
				"target": "Warranty Claim",
				"description": "Customer warranty cases, serial eligibility, complaint status, and ERPNext resolution lifecycle.",
				"fields": ("customer", "serial_no", "complaint_date", "status"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "doctype",
				"label": "Maintenance Schedules",
				"target": "Maintenance Schedule",
				"description": "Authoritative ERPNext schedules and planned after-sales service visits.",
				"fields": ("customer", "transaction_date", "status"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "doctype",
				"label": "Maintenance Visits",
				"target": "Maintenance Visit",
				"description": "Recorded maintenance visits and their native ERPNext document status.",
				"fields": ("customer", "mntc_date", "completion_status", "status"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
		),
	},
	"sales-team": {
		"page_route": "sales-team-control",
		"title": "Sales Team, Targets & Commissions",
		"eyebrow": "Sales Performance Control",
		"description": "Keep the RetailEdge sales-team experience in EdgeSuite while ERPNext remains authoritative for Sales Person, Sales Partner, targets, and commission reports.",
		"sources": (
			{
				"kind": "page",
				"label": "Salesperson Performance",
				"target": "salesperson-performance-dashboard",
				"description": "Open the existing RetailEdge EdgeSuite salesperson performance dashboard.",
			},
			{
				"kind": "doctype",
				"label": "Sales People",
				"target": "Sales Person",
				"description": "ERPNext Sales Person hierarchy and target ownership.",
				"fields": ("sales_person_name", "parent_sales_person", "is_group", "enabled"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "doctype",
				"label": "Sales Partners",
				"target": "Sales Partner",
				"description": "ERPNext partner master data used by selling and commission reporting.",
				"fields": ("partner_name", "commission_rate", "territory"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "report",
				"label": "Sales Person Commissions",
				"target": "Sales Person Commission Summary",
				"description": "Open ERPNext's authoritative Sales Person commission summary.",
			},
			{
				"kind": "report",
				"label": "Sales Partner Commissions",
				"target": "Sales Partner Commission Summary",
				"description": "Open ERPNext's authoritative Sales Partner commission summary.",
			},
			{
				"kind": "report",
				"label": "Sales Person Targets",
				"target": "Sales Person Target Variance Based On Item Group",
				"description": "Review ERPNext target variance by item group for Sales People.",
			},
			{
				"kind": "report",
				"label": "Sales Partner Targets",
				"target": "Sales Partner Target Variance based on Item Group",
				"description": "Review ERPNext target variance by item group for Sales Partners.",
			},
		),
	},
	"budget-control": {
		"page_route": "budget-control",
		"title": "Budgeting & Cost Control",
		"eyebrow": "Accounting Control",
		"description": "Review budgets and cost-centre structure in EdgeSuite while ERPNext remains authoritative for budget rules, enforcement, submission, and variance calculations.",
		"sources": (
			{
				"kind": "doctype",
				"label": "Budgets",
				"target": "Budget",
				"description": "ERPNext budgets against Cost Center or Project, including fiscal period and control settings.",
				"fields": ("company", "budget_against", "from_fiscal_year", "to_fiscal_year"),
				"scope": SCOPE_COMPANY,
			},
			{
				"kind": "report",
				"label": "Budget Variance",
				"target": "Budget Variance Report",
				"description": "Open ERPNext's authoritative budget-versus-actual report with its native filters and accounting dimensions.",
			},
			{
				"kind": "doctype",
				"label": "Cost Centers",
				"target": "Cost Center",
				"description": "ERPNext cost-centre hierarchy used for accounting classification and budget control.",
				"fields": ("company", "parent_cost_center", "is_group", "disabled"),
				"scope": SCOPE_COMPANY,
			},
		),
	},
	"assets": {
		"page_route": "assets-control",
		"title": "Assets",
		"eyebrow": "Fixed Asset Control",
		"description": "Review the fixed-asset register and category configuration in EdgeSuite while ERPNext remains authoritative for depreciation, movement, maintenance, adjustment, sale, scrap and accounting lifecycle actions.",
		"sources": (
			{
				"kind": "doctype",
				"label": "Fixed Assets",
				"target": "Asset",
				"description": "ERPNext fixed assets with company, category, location, status, custody and lifecycle context.",
				"fields": (
					"asset_name",
					"item_code",
					"company",
					"asset_category",
					"location",
					"status",
					"custodian",
					"maintenance_required",
					"calculate_depreciation",
					"next_depreciation_date",
				),
				"scope": SCOPE_COMPANY,
			},
			{
				"kind": "doctype",
				"label": "Asset Categories",
				"target": "Asset Category",
				"description": "ERPNext asset categories and their depreciation/CWIP classification context.",
				"fields": ("asset_category_name", "enable_cwip_accounting", "non_depreciable_category"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
		),
	},
	"stock-traceability": {
		"page_route": "stock-traceability-control",
		"title": "Stock Traceability",
		"eyebrow": "Batch & Serial Control",
		"description": "Review batch and serial traceability in EdgeSuite while ERPNext remains authoritative for stock quantities, expiry, warranty, movement, valuation and Serial and Batch Bundle transactions.",
		"sources": (
			{
				"kind": "doctype",
				"label": "Batches",
				"target": "Batch",
				"description": "ERPNext batches with item, quantity, manufacturing/expiry date and source context.",
				"fields": ("item", "item_name", "batch_qty", "stock_uom", "manufacturing_date", "expiry_date", "disabled", "supplier"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "doctype",
				"label": "Serial Numbers",
				"target": "Serial No",
				"description": "ERPNext serialized stock with batch, location, status, customer and warranty/AMC context.",
				"fields": (
					"item_code",
					"item_name",
					"batch_no",
					"warehouse",
					"status",
					"company",
					"customer",
					"warranty_expiry_date",
					"amc_expiry_date",
					"maintenance_status",
				),
				"scope": SCOPE_CONFIGURED_BRANCH_STOCK,
			},
			{
				"kind": "report",
				"label": "Batch Expiry Status",
				"target": "Batch Item Expiry Status",
				"description": "Open ERPNext's native batch expiry-status report under its own report permissions.",
			},
			{
				"kind": "report",
				"label": "Available Batches",
				"target": "Available Batch Report",
				"description": "Open ERPNext's native available-batch report for current batch availability.",
			},
			{
				"kind": "report",
				"label": "Available Serial Numbers",
				"target": "Available Serial No",
				"description": "Open ERPNext's native available-serial-number report for current availability.",
			},
		),
	},
	"pricing-promotions": {
		"page_route": "pricing-promotions-control",
		"title": "Pricing & Promotions",
		"eyebrow": "Commercial Control",
		"description": "Review pricing, promotions, coupons and loyalty configuration in EdgeSuite while ERPNext remains authoritative for master data, pricing evaluation and transaction-time enforcement.",
		"sources": (
			{
				"kind": "doctype",
				"label": "Price Lists",
				"target": "Price List",
				"description": "ERPNext selling and buying price-list masters used by transaction pricing.",
				"fields": ("enabled", "selling", "buying", "currency"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "doctype",
				"label": "Item Prices",
				"target": "Item Price",
				"description": "ERPNext item-level rates, validity dates, UOM and price-list assignments.",
				"fields": ("item_code", "price_list", "price_list_rate", "currency", "valid_from", "valid_upto"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "doctype",
				"label": "Pricing Rules",
				"target": "Pricing Rule",
				"description": "ERPNext conditional pricing and product-discount rules applied during selling or buying.",
				"fields": ("title", "apply_on", "price_or_product_discount", "selling", "buying", "valid_from", "valid_upto", "disable"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "doctype",
				"label": "Promotional Schemes",
				"target": "Promotional Scheme",
				"description": "ERPNext promotional schemes used to generate and govern promotional pricing rules.",
				"fields": ("apply_on", "selling", "buying", "valid_from", "valid_upto", "disable"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "doctype",
				"label": "Coupon Codes",
				"target": "Coupon Code",
				"description": "ERPNext coupon codes and their validity or usage limits for eligible pricing rules.",
				"fields": ("coupon_code", "valid_from", "valid_upto", "maximum_use", "used"),
				"scope": SCOPE_NATIVE_PERMISSION,
			},
			{
				"kind": "doctype",
				"label": "Loyalty Programs",
				"target": "Loyalty Program",
				"description": "ERPNext loyalty programmes, programme dates and points conversion configuration.",
				"fields": ("company", "customer_group", "from_date", "to_date", "conversion_factor", "expiry_duration"),
				"scope": SCOPE_COMPANY,
			},
		),
	},
}


@frappe.whitelist()
def get_native_visual_workspace(workspace: str) -> dict[str, Any]:
	"""Return a bounded, permission-aware EdgeSuite overview over native ERPNext capabilities."""
	_assert_authenticated()
	workspace = str(workspace or "").strip()
	config = WORKSPACES.get(workspace)
	if not config:
		frappe.throw(_("Unsupported RetailEdge control workspace."))

	# Resolve one authoritative server-side context for both the banner and every
	# context-aware preview. Client parameters can never widen this scope.
	operating_context = get_operating_context()
	company = str(operating_context.get("company") or "")
	branch = str(operating_context.get("branch") or "")

	sources: list[dict[str, Any]] = []
	for source in config["sources"]:
		resolved = _resolve_source(source, operating_context=operating_context)
		if resolved:
			sources.append(resolved)

	if not sources:
		frappe.throw(
			_("You do not have permission to open any of the ERPNext capabilities in this workspace."),
			frappe.PermissionError,
		)

	return {
		"workspace": workspace,
		"page_route": config["page_route"],
		"title": _(config["title"]),
		"eyebrow": _(config["eyebrow"]),
		"description": _(config["description"]),
		"company": company,
		"branch": branch,
		"user_name": frappe.utils.get_fullname(frappe.session.user),
		"sources": sources,
		"recent_limit": RECENT_LIMIT,
		"source_of_truth": "ERPNext",
		"read_only_overview": 1,
		"native_handoff": 1,
	}


def _resolve_source(source: dict[str, Any], *, operating_context: dict[str, Any]) -> dict[str, Any] | None:
	kind = source["kind"]
	if kind == "doctype":
		return _resolve_doctype_source(source, operating_context=operating_context)
	if kind == "report":
		return _resolve_report_source(source)
	if kind == "page":
		return _resolve_page_source(source)
	return None


def _resolve_doctype_source(
	source: dict[str, Any],
	*,
	operating_context: dict[str, Any],
) -> dict[str, Any] | None:
	doctype = source["target"]
	if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		return None

	meta = frappe.get_meta(doctype)
	candidate_fields = [field for field in source.get("fields", ()) if meta.has_field(field)]
	fields = ["name", "modified", "docstatus", *candidate_fields]
	scope_plan = _build_preview_scope_plan(
		source,
		doctype=doctype,
		meta=meta,
		operating_context=operating_context,
	)
	rows = []
	if scope_plan["query_allowed"]:
		rows = frappe.get_list(
			doctype,
			fields=fields,
			filters=scope_plan["filters"],
			order_by="modified desc",
			limit_page_length=RECENT_LIMIT,
		)
	columns = [
		{"fieldname": "name", "label": _("ID")},
		*[
			{
				"fieldname": fieldname,
				"label": _(meta.get_field(fieldname).label or fieldname.replace("_", " ").title()),
			}
			for fieldname in candidate_fields
		],
		{"fieldname": "modified", "label": _("Modified")},
	]
	return {
		"kind": "doctype",
		"label": _(source["label"]),
		"target": doctype,
		"description": _(source["description"]),
		"can_create": int(bool(frappe.has_permission(doctype, "create"))),
		"columns": columns,
		"rows": [dict(row) for row in rows],
		"preview_label": _("Recent {0}").format(min(len(rows), RECENT_LIMIT)),
		"scope": scope_plan["scope"],
		"scope_state": scope_plan["state"],
		"scope_message": _(scope_plan["message"]) if scope_plan.get("message") else "",
	}


def _build_preview_scope_plan(
	source: dict[str, Any],
	*,
	doctype: str,
	meta: Any,
	operating_context: dict[str, Any],
) -> dict[str, Any]:
	"""Build server-authoritative preview filters without weakening native permissions."""
	scope = str(source.get("scope") or SCOPE_NATIVE_PERMISSION).strip()
	if scope not in SUPPORTED_PREVIEW_SCOPES:
		return _blocked_scope_plan(
			scope=scope,
			message=f"Unsupported preview scope configured for {doctype}.",
		)

	static_filters = source.get("filters") or {}
	if not isinstance(static_filters, dict):
		return _blocked_scope_plan(
			scope=scope,
			message=f"Invalid preview filters configured for {doctype}.",
		)
	filters = dict(static_filters)
	company = str(operating_context.get("company") or "").strip()
	branch = str(operating_context.get("branch") or "").strip()

	if scope == SCOPE_NATIVE_PERMISSION:
		return {
			"scope": scope,
			"state": "native_permission",
			"message": "",
			"filters": filters,
			"query_allowed": True,
		}

	if not company:
		return _blocked_scope_plan(
			scope=scope,
			message="Choose an operating Company to load this preview.",
			filters=filters,
		)

	if scope == SCOPE_COMPANY:
		if not meta.has_field("company"):
			return _blocked_scope_plan(
				scope=scope,
				message=f"{doctype} cannot be safely limited to the operating Company on this ERPNext schema.",
				filters=filters,
			)
		filters["company"] = company
		return {
			"scope": scope,
			"state": "applied",
			"message": "",
			"filters": filters,
			"query_allowed": True,
		}

	if not branch:
		return _blocked_scope_plan(
			scope=scope,
			message="Choose an operating Branch to load this preview.",
			filters=filters,
		)
	if not meta.has_field("warehouse"):
		return _blocked_scope_plan(
			scope=scope,
			message=f"{doctype} cannot be safely limited to configured Branch stock locations on this ERPNext schema.",
			filters=filters,
		)

	warehouses = _get_configured_branch_stock_locations(company=company, branch=branch)
	if not warehouses:
		return _blocked_scope_plan(
			scope=scope,
			message="Configure at least one Branch stock location before loading this preview.",
			filters=filters,
		)
	filters["warehouse"] = ["in", warehouses]
	if meta.has_field("company"):
		filters["company"] = company
	return {
		"scope": scope,
		"state": "applied",
		"message": "",
		"filters": filters,
		"query_allowed": True,
	}


def _blocked_scope_plan(
	*,
	scope: str,
	message: str,
	filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
	return {
		"scope": scope,
		"state": "blocked",
		"message": message,
		"filters": dict(filters or {}),
		"query_allowed": False,
	}


def _get_configured_branch_stock_locations(*, company: str, branch: str) -> list[str]:
	"""Return only stock locations bound to the exact enabled Company + Branch profile."""
	profile = get_exact_branch_profile(company=company, branch=branch, active_only=True)
	if not profile:
		return []
	warehouses = [
		str(getattr(profile, fieldname, None) or "").strip()
		for fieldname in BRANCH_STOCK_PROFILE_FIELDS
	]
	return list(dict.fromkeys(warehouse for warehouse in warehouses if warehouse))


def _resolve_report_source(source: dict[str, Any]) -> dict[str, Any] | None:
	try:
		from frappe.desk.query_report import get_report_doc

		get_report_doc(source["target"])
	except frappe.PermissionError:
		return None
	except Exception:
		return None
	return {
		"kind": "report",
		"label": _(source["label"]),
		"target": source["target"],
		"description": _(source["description"]),
		"can_create": 0,
		"columns": [],
		"rows": [],
	}


def _resolve_page_source(source: dict[str, Any]) -> dict[str, Any] | None:
	if not frappe.db.exists("Page", source["target"]):
		return None
	return {
		"kind": "page",
		"label": _(source["label"]),
		"target": source["target"],
		"description": _(source["description"]),
		"can_create": 0,
		"columns": [],
		"rows": [],
	}


def _assert_authenticated() -> None:
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Sign in to open this RetailEdge control workspace."), frappe.PermissionError)
