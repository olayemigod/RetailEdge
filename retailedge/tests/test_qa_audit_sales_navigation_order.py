from __future__ import annotations

from retailedge.navigation_consolidation import _prioritize_sales_navigation


def test_make_sale_is_first_when_professional_selling_arrives_first():
	groups = [
		{
			"key": "sales",
			"label": "Sales",
			"items": [
				{"label": "Professional Selling", "target_type": "Page", "target": "professional-selling"},
				{"label": "Make Sale", "target_type": "Page", "target": "make-sale"},
				{"label": "Document Output & Sharing", "target_type": "Page", "target": "document-output-sharing"},
			],
		}
	]

	_prioritize_sales_navigation(groups)

	assert [item["target"] for item in groups[0]["items"]] == [
		"make-sale",
		"professional-selling",
		"document-output-sharing",
	]


def test_sales_ordering_preserves_permission_filtered_items_when_make_sale_is_absent():
	groups = [
		{
			"key": "sales",
			"items": [
				{"label": "Professional Selling", "target_type": "Page", "target": "professional-selling"},
				{"label": "Document Output & Sharing", "target_type": "Page", "target": "document-output-sharing"},
			],
		}
	]

	_prioritize_sales_navigation(groups)

	assert [item["target"] for item in groups[0]["items"]] == [
		"professional-selling",
		"document-output-sharing",
	]
