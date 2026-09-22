from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.master_experience import get_retailedge_business_hub_context


REPORT_GROUPS: tuple[dict[str, Any], ...] = (
	{
		"key": "sales",
		"label": "Sales",
		"description": "Sales performance, customers, salespeople and transaction detail.",
		"icon": "chart",
		"items": (
			{
				"label": "Sales Analysis",
				"description": "Group submitted sales by time, item, category, customer, Branch, salesperson or warehouse.",
				"target_type": "Page",
				"target": "sales-analysis",
				"tags": ("sales", "analysis", "trend", "category", "branch", "warehouse"),
			},
			{
				"label": "Sales Invoice Register",
				"description": "Review submitted sales, returns, tax and outstanding balances.",
				"target_type": "Page",
				"target": "sales-invoice-register",
				"tags": ("sales", "invoice", "returns", "outstanding"),
			},
			{
				"label": "Sales by Item",
				"description": "See quantity, returns, net sales and average selling price by item.",
				"target_type": "Page",
				"target": "sales-by-item",
				"tags": ("sales", "item", "product", "quantity"),
			},
			{
				"label": "Salesperson Performance",
				"description": "Review salesperson activity and performance in the permitted scope.",
				"target_type": "Page",
				"target": "salesperson-performance-dashboard",
				"tags": ("sales", "salesperson", "team", "performance"),
			},
			{
				"label": "Branch Performance",
				"description": "Compare permitted Branch performance and operating signals.",
				"target_type": "Page",
				"target": "branch-performance-dashboard",
				"tags": ("sales", "branch", "performance"),
			},
			{
				"label": "Customer & Sales Intelligence",
				"description": "Understand customer contribution, retention and sales behaviour.",
				"target_type": "Page",
				"target": "customer-sales-intelligence",
				"tags": ("sales", "customer", "retention", "intelligence"),
			},
			{
				"label": "Discount & Sales Quality",
				"description": "Review discounts, returns and sales-quality signals.",
				"target_type": "Page",
				"target": "sales-quality-intelligence",
				"tags": ("sales", "discount", "returns", "quality"),
			},
		),
	},
	{
		"key": "purchases",
		"label": "Purchases",
		"description": "Purchase activity and supplier transaction detail.",
		"icon": "shopping-bag",
		"items": (
			{
				"label": "Purchase Register",
				"description": "Review submitted purchases, returns and supplier invoice detail.",
				"target_type": "Page",
				"target": "purchase-register",
				"tags": ("purchase", "supplier", "invoice", "returns"),
			},
		),
	},
	{
		"key": "stock",
		"label": "Stock",
		"description": "Current position, movement, ageing and replenishment intelligence.",
		"icon": "layers",
		"items": (
			{
				"label": "Stock Position",
				"description": "Review on-hand, reserved, available, projected and reorder status.",
				"target_type": "Page",
				"target": "stock-position",
				"tags": ("stock", "inventory", "available", "reorder"),
			},
			{
				"label": "Inventory Intelligence",
				"description": "Review movement, cover, replenishment and stock-risk signals.",
				"target_type": "Page",
				"target": "inventory-intelligence",
				"tags": ("stock", "inventory", "movement", "replenishment"),
			},
			{
				"label": "Inventory Ageing",
				"description": "Review ageing and slow-moving inventory using the existing stock truth.",
				"target_type": "Page",
				"target": "inventory-ageing",
				"tags": ("stock", "inventory", "ageing", "slow moving"),
			},
			{
				"label": "Transfer Opportunities",
				"description": "Identify stock transfer opportunities between permitted locations.",
				"target_type": "Page",
				"target": "inventory-transfer-opportunities",
				"tags": ("stock", "transfer", "branch", "warehouse"),
			},
			{
				"label": "Stock Movement History",
				"description": "Trace stock movements in the hardened ProcessEdge Retail view.",
				"target_type": "Page",
				"target": "stock-movement-history",
				"tags": ("stock", "movement", "ledger", "trace"),
			},
		),
	},
	{
		"key": "money",
		"label": "Money",
		"description": "Receivables, payables, cash movement and known commitments.",
		"icon": "wallet",
		"items": (
			{
				"label": "Customer Receivables",
				"description": "Review current outstanding customer balances and ageing.",
				"target_type": "Page",
				"target": "customer-receivables",
				"tags": ("receivable", "customer", "ageing", "outstanding"),
			},
			{
				"label": "Supplier Payables",
				"description": "Review current outstanding supplier balances and ageing.",
				"target_type": "Page",
				"target": "supplier-payables",
				"tags": ("payable", "supplier", "ageing", "outstanding"),
			},
			{
				"label": "Cash Movement",
				"description": "Review posted Cash and Bank movements from ERPNext General Ledger truth.",
				"target_type": "Page",
				"target": "cash-movement",
				"tags": ("cash", "bank", "money in", "money out"),
			},
			{
				"label": "Cash Commitments",
				"description": "Review the 13-week schedule of known receivable and payable commitments.",
				"target_type": "Page",
				"target": "cash-flow-outlook",
				"tags": ("cash", "commitments", "receivable", "payable", "13 week"),
			},
		),
	},
	{
		"key": "expenses",
		"label": "Expenses",
		"description": "Posted expense activity and operational expense review.",
		"icon": "file-text",
		"items": (
			{
				"label": "Expense Register",
				"description": "Review consolidated posted expenses with Branch and category context.",
				"target_type": "Page",
				"target": "expense-register",
				"tags": ("expense", "spend", "category", "branch"),
			},
		),
	},
	{
		"key": "profitability",
		"label": "Profitability",
		"description": "Permission-gated contribution and inventory profitability intelligence.",
		"icon": "trending-up",
		"items": (
			{
				"label": "Profitability Intelligence",
				"description": "Review R8 transactional contribution while ERPNext remains accounting profit truth.",
				"target_type": "Page",
				"target": "profitability-intelligence",
				"tags": ("profit", "margin", "cost", "contribution"),
			},
			{
				"label": "Inventory + Profitability",
				"description": "Relate inventory position and movement to permitted profitability signals.",
				"target_type": "Page",
				"target": "inventory-profitability",
				"tags": ("inventory", "profit", "margin", "stock"),
			},
		),
	},
	{
		"key": "controls",
		"label": "Controls & Audit",
		"description": "Operational exceptions, reconciliation and integrity controls.",
		"icon": "shield",
		"items": (
			{
				"label": "Daily Sales Audit",
				"description": "Review daily sales completeness and control signals.",
				"target_type": "Page",
				"target": "daily-sales-audit",
				"tags": ("audit", "sales", "daily", "control"),
			},
			{
				"label": "Cash Shift Verification",
				"description": "Review cashier shift balances, variance and verification.",
				"target_type": "Page",
				"target": "cash-shift-verification",
				"tags": ("cash", "shift", "variance", "audit"),
			},
			{
				"label": "Expense Review",
				"description": "Review expense exceptions and approval-ready items.",
				"target_type": "Page",
				"target": "expense-review",
				"tags": ("expense", "review", "approval", "control"),
			},
			{
				"label": "Bank Matching & Reconciliation",
				"description": "Review matching, reconciliation readiness and banking exceptions.",
				"target_type": "Page",
				"target": "bank-matching-reconciliation",
				"tags": ("bank", "matching", "reconciliation", "exception"),
			},
			{
				"label": "Stock & Accounting Integrity",
				"description": "Review stock/accounting integrity exceptions without changing accounting truth.",
				"target_type": "Page",
				"target": "stock-accounting-integrity",
				"tags": ("stock", "accounting", "integrity", "audit"),
			},
			{
				"label": "Business Control Centre",
				"description": "Review cross-domain control signals and business exceptions.",
				"target_type": "Page",
				"target": "business-control-center",
				"tags": ("control", "exception", "business", "audit"),
			},
		),
	},
	{
		"key": "financial",
		"label": "Financial",
		"description": "ERPNext accounting statements and ledgers for authorised Native Desk users.",
		"icon": "book-open",
		"items": (
			{
				"label": "Profit & Loss",
				"description": "ERPNext Profit and Loss Statement — authoritative accounting profit.",
				"target_type": "Report",
				"target": "Profit and Loss Statement",
				"tags": ("profit", "loss", "income statement", "accounting"),
				"native_desk": True,
			},
			{
				"label": "Balance Sheet",
				"description": "ERPNext Balance Sheet — authoritative assets, liabilities and equity.",
				"target_type": "Report",
				"target": "Balance Sheet",
				"tags": ("balance sheet", "assets", "liabilities", "equity"),
				"native_desk": True,
			},
			{
				"label": "Cash Flow Statement",
				"description": "ERPNext Cash Flow statement from accounting truth.",
				"target_type": "Report",
				"target": "Cash Flow",
				"tags": ("cash flow", "financial", "accounting"),
				"native_desk": True,
			},
			{
				"label": "General Ledger",
				"description": "ERPNext General Ledger transaction detail.",
				"target_type": "Report",
				"target": "General Ledger",
				"tags": ("ledger", "gl", "accounting", "journal"),
				"native_desk": True,
			},
			{
				"label": "Trial Balance",
				"description": "ERPNext Trial Balance for account-level debit and credit validation.",
				"target_type": "Report",
				"target": "Trial Balance",
				"tags": ("trial balance", "debit", "credit", "accounting"),
				"native_desk": True,
			},
			{
				"label": "Budget Variance",
				"description": "ERPNext Budget Variance report for authorised accounting users.",
				"target_type": "Report",
				"target": "Budget Variance Report",
				"tags": ("budget", "variance", "financial", "accounting"),
				"native_desk": True,
			},
		),
	},
)


@frappe.whitelist()
def get_reports_centre_context() -> dict[str, Any]:
	"""Return the permission-filtered report catalogue without querying report datasets."""
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Sign in to open Reports Centre."), frappe.PermissionError)

	master = get_retailedge_business_hub_context() or {}
	access = dict(master.get("access") or {})
	context = dict(master.get("context") or {})
	can_use_native_desk = bool(access.get("can_use_native_desk"))
	groups: list[dict[str, Any]] = []

	for group in REPORT_GROUPS:
		items = []
		for spec in group["items"]:
			resolved = _resolve_report_item(spec, can_use_native_desk=can_use_native_desk)
			if resolved:
				items.append(resolved)
		if not items:
			continue
		groups.append(
			{
				"key": group["key"],
				"label": _(group["label"]),
				"description": _(group["description"]),
				"icon": group["icon"],
				"items": items,
			}
		)

	return {
		"title": _("Reports Centre"),
		"groups": groups,
		"context": {
			"company": context.get("company") or "",
			"company_label": context.get("company_label") or context.get("company") or "",
			"branch": context.get("branch") or "",
			"user_name": context.get("user_name") or "",
		},
		"access": {
			"can_use_native_desk": can_use_native_desk,
		},
		"navigation_groups": master.get("navigation_groups") or [],
		"metadata": {
			"catalogue_only": 1,
			"report_count": sum(len(group["items"]) for group in groups),
			"category_count": len(groups),
			"data_policy": "Reports Centre does not calculate report metrics; each destination remains authoritative for its own data.",
		},
	}


def _resolve_report_item(spec: dict[str, Any], *, can_use_native_desk: bool) -> dict[str, Any] | None:
	target_type = str(spec.get("target_type") or "").strip()
	target = str(spec.get("target") or "").strip()
	if not target:
		return None
	if spec.get("native_desk") and not can_use_native_desk:
		return None

	if target_type == "Page":
		if not _can_open_page(target):
			return None
	elif target_type == "Report":
		if not _can_open_report(target):
			return None
	else:
		return None

	return {
		"label": _(spec["label"]),
		"description": _(spec["description"]),
		"target_type": target_type,
		"target": target,
		"icon": spec.get("icon") or "report",
		"tags": list(spec.get("tags") or ()),
		"native_desk": int(bool(spec.get("native_desk"))),
	}


def _can_open_page(target: str) -> bool:
	try:
		if not frappe.db.exists("Page", target):
			return False
		return bool(frappe.get_doc("Page", target).is_permitted())
	except Exception:
		return False


def _can_open_report(target: str) -> bool:
	try:
		if not frappe.db.exists("Report", target):
			return False
		doc = frappe.get_doc("Report", target)
		if not doc.is_permitted() or doc.disabled:
			return False
		return bool(frappe.has_permission(doc.ref_doctype, "report"))
	except Exception:
		return False
