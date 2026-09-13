from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_CONTROLLER = APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js"


class TestBusinessHubBootIdempotencyContract(unittest.TestCase):
	def test_boot_reuses_an_already_mounted_business_hub(self):
		source = PAGE_CONTROLLER.read_text()
		start = source.index("\tfunction bootBusinessHub(wrapper) {")
		end = source.index("\n\tasync function mountBusinessHub(wrapper)", start)
		boot_block = source[start:end]

		mounted_index = boot_block.index("const mountedComponent = getMountedComponent(wrapper)")
		mount_index = boot_block.index("mountBusinessHub(wrapper)")
		self.assertLess(mounted_index, mount_index)
		self.assertIn("if (mountedComponent)", boot_block)
		self.assertIn("return Promise.resolve(wrapper._retailedgeBusinessHub)", boot_block)

	def test_mounted_boot_does_not_clear_or_refresh_the_hub(self):
		source = PAGE_CONTROLLER.read_text()
		start = source.index("\tfunction bootBusinessHub(wrapper) {")
		end = source.index("\n\tasync function mountBusinessHub(wrapper)", start)
		boot_block = source[start:end]

		mounted_start = boot_block.index("if (mountedComponent)")
		mounted_end = boot_block.index("\n\t\t}", mounted_start)
		mounted_branch = boot_block[mounted_start:mounted_end]
		self.assertNotIn("clearPreviousMount", mounted_branch)
		self.assertNotIn("refreshContext", mounted_branch)
		self.assertIn("enforceCreateVisibility", mounted_branch)

	def test_page_show_retains_the_explicit_context_refresh_path(self):
		source = PAGE_CONTROLLER.read_text()
		self.assertIn('if (component && typeof component.refreshContext === "function")', source)
		self.assertIn("return component.refreshContext().finally", source)


if __name__ == "__main__":
	unittest.main()
