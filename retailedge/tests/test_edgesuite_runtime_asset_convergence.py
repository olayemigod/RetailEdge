from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestEdgeSuiteRuntimeAssetConvergence(unittest.TestCase):
    def test_all_retailedge_page_loaders_use_collision_safe_asset(self):
        """Old asset names must not silently select the CoreEdge manifest entry."""
        page_sources = sorted((APP_ROOT / "retailedge" / "page").glob("*/*.js"))
        self.assertGreaterEqual(len(page_sources), 70)

        legacy = [
            str(path.relative_to(APP_ROOT))
            for path in page_sources
            if '"edgeui.bundle.js"' in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(legacy, [], f"Legacy EdgeSuite UI asset name remains: {legacy}")

        migrated = [
            path
            for path in page_sources
            if '"edgesuite_ui.bundle.js"' in path.read_text(encoding="utf-8")
        ]
        self.assertGreaterEqual(len(migrated), 60)

    def test_retailedge_shell_context_does_not_load_collision_prone_runtime(self):
        shell = (APP_ROOT / "public" / "js" / "retailedge_shell_context.js").read_text(encoding="utf-8")
        self.assertIn('frappe.require("edgesuite_ui.bundle.js", start)', shell)
        self.assertNotIn('frappe.require("edgeui.bundle.js", start)', shell)


if __name__ == "__main__":
    unittest.main()
