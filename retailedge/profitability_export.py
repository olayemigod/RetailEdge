from __future__ import annotations

from typing import Any

from frappe import _

from retailedge.profitability_intelligence import get_profitability_intelligence


def build_profitability_export_dataset(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	result = get_profitability_intelligence(filters)
	rows: list[dict[str, Any]] = []

	for row in result.get("rows") or []:
		rows.append(
			{
				"section": _("Item Profitability"),
				"dimension": row.get("item_code") or "",
				"net_sales": row.get("net_sales"),
				"cost_of_sales": row.get("cost_of_sales"),
				"gross_profit": row.get("gross_profit"),
				"gross_margin_percent": row.get("gross_margin_percent"),
				"invoice_count": row.get("invoice_count"),
			}
		)

	labels = {
		"branch": _("Branch"),
		"item_group": _("Item Group"),
		"customer": _("Customer"),
		"salesperson": _("Salesperson"),
	}
	for key, label in labels.items():
		for row in (result.get("dimensions") or {}).get(key) or []:
			rows.append(
				{
					"section": label,
					"dimension": row.get("key") or "",
					"net_sales": row.get("net_sales"),
					"cost_of_sales": row.get("cost_of_sales"),
					"gross_profit": row.get("gross_profit"),
					"gross_margin_percent": row.get("gross_margin_percent"),
					"invoice_count": row.get("invoice_count"),
				}
			)

	return {
		"title": _("Profitability Intelligence"),
		"columns": [
			{"fieldname": "section", "label": _("Section"), "fieldtype": "Data", "width": 150},
			{"fieldname": "dimension", "label": _("Item / Dimension"), "fieldtype": "Data", "width": 220},
			{"fieldname": "net_sales", "label": _("Net Sales"), "fieldtype": "Currency", "width": 140},
			{"fieldname": "cost_of_sales", "label": _("Cost of Sales"), "fieldtype": "Currency", "width": 140},
			{"fieldname": "gross_profit", "label": _("Gross Profit"), "fieldtype": "Currency", "width": 140},
			{"fieldname": "gross_margin_percent", "label": _("Gross Margin %"), "fieldtype": "Percent", "width": 120},
			{"fieldname": "invoice_count", "label": _("Invoices"), "fieldtype": "Int", "width": 90},
		],
		"rows": rows,
		"summary": result.get("summary") or [],
		"filters": result.get("scope") or {},
	}
