from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "retailedge"
GUARD_BUNDLE = "retailedge_edgesuite_only_operational_guard.bundle.js"


class TestEdgeSuiteOnlyOperationalGuardContract(unittest.TestCase):
	def test_guard_bundle_exports_shared_installer(self):
		guard = (APP / "public" / "js" / GUARD_BUNDLE).read_text()
		self.assertIn("window.retailedgeInstallEdgesuiteOnlyOperationalGuard = install", guard)

	def test_everyday_operational_pages_load_same_guard_bundle(self):
		for page in ("professional_selling", "professional_purchasing"):
			page_js = (
				APP
				/ "retailedge"
				/ "page"
				/ page
				/ f"{page}.js"
			).read_text()
			self.assertIn(f'RESTRICTED_GUARD_ASSET = "{GUARD_BUNDLE}"', page_js)
			self.assertIn("await requireAsync(RESTRICTED_GUARD_ASSET)", page_js)
			self.assertIn("window.retailedgeInstallEdgesuiteOnlyOperationalGuard", page_js)


if __name__ == "__main__":
	unittest.main()
