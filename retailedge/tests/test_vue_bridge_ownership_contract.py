from __future__ import annotations

import json
import unittest
from pathlib import Path


class TestVueBridgeOwnershipContract(unittest.TestCase):
	def test_retailedge_vue_alias_is_owned_by_edgesuite_ui(self):
		repo_root = Path(__file__).resolve().parents[2]
		config = json.loads((repo_root / "tsconfig.json").read_text())
		paths = config.get("compilerOptions", {}).get("paths", {})

		self.assertEqual(
			paths.get("vue"),
			["../edgesuite_ui/edgesuite_ui/public/js/edgeui/vue-bridge.js"],
		)

	def test_retailedge_tsconfig_does_not_reference_coreedge_runtime(self):
		repo_root = Path(__file__).resolve().parents[2]
		config_text = (repo_root / "tsconfig.json").read_text().lower()
		self.assertNotIn("coreedge", config_text)


if __name__ == "__main__":
	unittest.main()
