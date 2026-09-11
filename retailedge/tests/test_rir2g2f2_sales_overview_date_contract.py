from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "public/js/sales_dashboard/SalesDashboard.vue"


def test_sales_overview_formats_recent_invoice_posting_date_for_user():
	source = PAGE.read_text(encoding="utf-8")
	assert "formatDate(row.posting_date)" in source
	assert "{{ row.posting_date }}" not in source
	assert "frappe.datetime.str_to_user" in source


def test_sales_overview_date_inputs_remain_native_iso_controls():
	source = PAGE.read_text(encoding="utf-8")
	assert 'type="date"' in source
	assert "filters.from_date" in source
	assert "filters.to_date" in source
