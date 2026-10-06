from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = APP_ROOT / "public" / "js" / "retailedge_business_hub_bootstrap.js"
BROWSER_ACCEPTANCE = APP_ROOT.parent / "browser-tests" / "retailedge_rc3_acceptance.spec.cjs"


class TestPersistentTransactionPageRouting(TestCase):
	def test_desk_bootstrap_does_not_rewrite_frappe_page_routes(self):
		source = BOOTSTRAP.read_text(encoding="utf-8")

		self.assertIn(
			'const CONTROLLER_ASSET = "/assets/retailedge/js/retailedge_business_hub_page.js";',
			source,
		)
		self.assertNotIn("retailedge_persistent_page_route_guard", source)
		self.assertNotIn("ROUTE_GUARD_ASSET", source)
		self.assertNotIn("correctPersistentTransactionPageRoute", source)
		self.assertNotIn("window.location.replace", source)

	def test_browser_acceptance_allows_frappe_v16_module_prefixed_page_routes(self):
		source = BROWSER_ACCEPTANCE.read_text(encoding="utf-8")

		for page in ("transfer-stock", "record-purchase", "make-sale"):
			self.assertIn(
				f'/(?:retailedge\\/)?{page}(?:$|[?#])/',
				source,
			)

		self.assertIn('openProductPage(page, "stock-adjustment", "Stock Adjustment")', source)


if __name__ == "__main__":
	import unittest

	unittest.main()
