from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]
GUARD = APP_ROOT / "public" / "js" / "retailedge_persistent_page_route_guard.js"
BOOTSTRAP = APP_ROOT / "public" / "js" / "retailedge_business_hub_bootstrap.js"


class TestPersistentTransactionPageRouteGuard(TestCase):
	def test_guard_is_bounded_to_known_persistent_transaction_pages(self):
		source = GUARD.read_text(encoding="utf-8")

		for page in (
			"make-sale",
			"record-purchase",
			"transfer-stock",
			"stock-adjustment",
		):
			self.assertIn(f'"{page}"', source)

		self.assertIn('^\\/(?:app|desk)\\/retailedge\\/([^/?#]+)\\/?$', source)
		self.assertIn("PERSISTENT_TRANSACTION_PAGES.has(value)", source)
		self.assertIn("window.location.replace", source)
		self.assertIn("window.location.assign", source)
		self.assertIn("/desk/${target}", source)
		self.assertNotIn("retailedge-business-hub", source)

	def test_desk_bootstrap_loads_guard_before_business_hub_controller(self):
		source = BOOTSTRAP.read_text(encoding="utf-8")

		self.assertIn(
			'const ROUTE_GUARD_ASSET = "/assets/retailedge/js/retailedge_persistent_page_route_guard.js";',
			source,
		)
		self.assertIn("function loadRouteGuard()", source)
		self.assertIn("loadRouteGuard();", source)
		self.assertIn("correctPersistentTransactionPageRoute", source)


if __name__ == "__main__":
	import unittest

	unittest.main()
