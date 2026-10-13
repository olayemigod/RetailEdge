import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CONTROLS = (
	APP_ROOT
	/ "public"
	/ "js"
	/ "selling"
	/ "SalesCommercialTermsControls.vue"
)


class TestSalesCommercialTermsControlsContract(unittest.TestCase):
	def test_manual_discount_mode_remains_selectable_before_value_entry(self):
		source = CONTROLS.read_text(encoding="utf-8")

		# The selected mode must have local UI state. Deriving it only from a
		# non-zero discount makes Percentage / Fixed amount immediately collapse
		# back to No manual discount before the operator can enter a value.
		self.assertIn("selectedDiscountMode", source)
		self.assertIn("discountModeFromValues", source)
		self.assertIn("this.selectedDiscountMode = next", source)
		self.assertIn('this.selectedDiscountMode = "percentage"', source)
		self.assertIn('this.selectedDiscountMode = "amount"', source)

		# Zero-value mode selection is editing intent only; it is not an applied
		# discount until a real percentage or amount is entered.
		self.assertIn('Number(this.values.additional_discount_percentage || 0) > 0', source)
		self.assertIn('Number(this.values.discount_amount || 0) > 0', source)

	def test_tax_helper_import_supports_older_erpnext_v16_upgrade_baselines(self):
		source = (APP_ROOT / "sales_commercial_terms.py").read_text(encoding="utf-8")

		self.assertIn("from erpnext.accounts.services.taxes import get_taxes_and_charges", source)
		self.assertIn("except ImportError:", source)
		self.assertIn("from erpnext.controllers.accounts_controller import (", source)
		self.assertIn("_get_taxes_and_charges as get_taxes_and_charges", source)


if __name__ == "__main__":
	unittest.main()
