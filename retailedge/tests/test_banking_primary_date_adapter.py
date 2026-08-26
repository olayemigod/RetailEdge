from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
PRIMARY_DATE_JS = APP_ROOT / "public/js/bank_matching_primary_date_adapter.js"
PRIMARY_DATE_CSS = APP_ROOT / "public/css/bank_matching_primary_date.css"


class BankingPrimaryDateAdapterTests(unittest.TestCase):
	def test_loader_includes_primary_date_assets_after_page_enhancements(self):
		page = PAGE_JS.read_text()
		self.assertIn("/assets/retailedge/js/bank_matching_primary_date_adapter.js", page)
		self.assertIn("/assets/retailedge/css/bank_matching_primary_date.css", page)
		self.assertLess(
			page.index("frappe.require(PAGE_ENHANCEMENTS_ASSET)"),
			page.index("frappe.require(PRIMARY_DATE_ASSET)"),
		)

	def test_adapter_keeps_only_smart_date_visible(self):
		asset = PRIMARY_DATE_JS.read_text()
		for marker in (
			'edgeInputField(filterBar, "From Date")',
			'edgeInputField(filterBar, "To Date")',
			'internalizeLegacyDateField(fromDate)',
			'internalizeLegacyDateField(toDate)',
			'fieldsHost.insertBefore(smartDate, fromDate)',
			'label.textContent = t("Date")',
			'Last 3 weeks, This Month, Last 90 days',
		):
			self.assertIn(marker, asset)

	def test_internal_date_fields_are_hidden_but_not_removed(self):
		asset = PRIMARY_DATE_JS.read_text()
		css = PRIMARY_DATE_CSS.read_text()
		self.assertIn('field.hidden = true', asset)
		self.assertIn('field.setAttribute("aria-hidden", "true")', asset)
		self.assertIn("retailedge-bank-internal-date-filter", asset)
		self.assertIn("display: none !important", css)
		self.assertNotIn("remove()", asset)

	def test_adapter_is_valid_javascript(self):
		completed = subprocess.run(
			["node", "--check", str(PRIMARY_DATE_JS)],
			capture_output=True,
			text=True,
			check=False,
		)
		self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
	unittest.main()
