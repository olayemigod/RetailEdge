import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CSS_ROOT = APP_ROOT / "public" / "css"
JS_ROOT = APP_ROOT / "public" / "js"


class TestSalesEntryUsabilityContract(unittest.TestCase):
	def test_sale_entry_styles_are_loaded_and_keep_summary_visible_on_wide_screens(self):
		loader = (CSS_ROOT / "retailedge_workspace_home.css").read_text(encoding="utf-8")
		styles = (CSS_ROOT / "retailedge_sales_entry.css").read_text(encoding="utf-8")

		self.assertIn('retailedge_sales_entry.css', loader)
		self.assertIn('@media (min-width: 1180px)', styles)
		self.assertIn('form.make-sale-form', styles)
		self.assertIn('.guided-invoice-form', styles)
		self.assertIn('> .sales-commercial-summary', styles)
		self.assertIn('position: sticky', styles)
		self.assertIn('grid-column: 1 / -1', styles)
		self.assertIn('@media (max-width: 1179px)', styles)
		self.assertIn('position: static', styles)

	def test_shared_child_table_remains_the_sale_item_surface(self):
		make_sale = (JS_ROOT / "make_sale" / "MakeSale.vue").read_text(encoding="utf-8")
		quick_sale = (JS_ROOT / "retailedge_business_hub" / "SimpleSalesInvoiceDialog.vue").read_text(encoding="utf-8")
		styles = (CSS_ROOT / "retailedge_sales_entry.css").read_text(encoding="utf-8")

		self.assertIn('<EdgeChildTable', make_sale)
		self.assertIn('<EdgeChildTable', quick_sale)
		self.assertNotIn('display: table', styles)
		self.assertNotIn('display: grid-table', styles)

	def test_tax_template_help_is_bound_business_facing_text(self):
		controls = (JS_ROOT / "selling" / "SalesCommercialTermsControls.vue").read_text(encoding="utf-8")

		self.assertIn(':description="values.tax_category ?', controls)
		self.assertNotIn('description="values.tax_category ?', controls)
		self.assertIn('Leave blank for automatic tax treatment.', controls)
		self.assertIn('Automatic tax treatment', controls)
		self.assertNotIn('ERPNext automatic tax treatment', controls)
		self.assertNotIn('ERPNext automatic tax', controls)


if __name__ == "__main__":
	unittest.main()
