from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BUSINESS_HUB_LOADER = APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js"


class TestRetailEdgeBusinessHubBootTiming(unittest.TestCase):
	def test_lazy_assets_wait_for_frappe_require(self):
		source = BUSINESS_HUB_LOADER.read_text(encoding="utf-8")

		self.assertIn('typeof global.frappe.require !== "function"', source)
		self.assertIn("FRAPPE_REQUIRE_POLL_MS", source)
		self.assertIn("global.setTimeout(attemptRequire, FRAPPE_REQUIRE_POLL_MS)", source)
		self.assertIn("global.frappe.require(asset, finish)", source)

	def test_loader_has_bounded_wait_and_does_not_mutate_frappe_require(self):
		source = BUSINESS_HUB_LOADER.read_text(encoding="utf-8")

		self.assertIn("LOAD_TIMEOUT_MS", source)
		self.assertIn("Timed out waiting for the Frappe asset loader", source)
		self.assertNotIn("global.frappe.require =", source)
		self.assertNotIn("frappe.require =", source)


if __name__ == "__main__":
	unittest.main()
