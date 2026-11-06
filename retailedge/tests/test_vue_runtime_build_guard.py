from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from retailedge import vue_runtime_build_guard as guard

APP_ROOT = Path(__file__).resolve().parents[1]


class TestVueRuntimeBuildGuard(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bench = Path(self.temp.name)
        self.source = self.bench / "apps" / "retailedge" / "retailedge" / "public" / "js"
        self.source.mkdir(parents=True)
        self.assets = self.bench / "sites" / "assets"
        self.assets.mkdir(parents=True)
        self.manifest = {}

        def make(bundle, source):
            owner = "edgesuite_ui" if bundle == guard.SHARED_BUNDLE else "retailedge"
            url = f"/assets/{owner}/dist/js/{bundle[:-3]}.TEST.js"
            output = self.bench / "sites" / url.lstrip("/")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(source, encoding="utf-8")
            self.manifest[bundle] = url

        self.make = make
        self.make(guard.SHARED_BUNDLE, "__vue_app__ __v_isVNode")
        for bundle in guard.REQUIRED_PRODUCT_BUNDLES:
            self.make(bundle, guard.BRIDGE_MARKER)
        self.save_manifest()

    def save_manifest(self):
        (self.assets / "assets.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_valid_compilation_passes(self):
        self.assertEqual(guard.validate_bridge_contract(guard.inspect(self.bench)), [])

    def test_discovers_additional_vue_page_entrypoint(self):
        (self.source / "sales_reporting.bundle.js").write_text(
            'import Page from "./sales_reporting/SalesReporting.vue";', encoding="utf-8"
        )
        self.make("sales_reporting.bundle.js", guard.BRIDGE_MARKER)
        self.save_manifest()
        rows = guard.inspect(self.bench)
        self.assertIn("sales_reporting.bundle.js", [row["asset"] for row in rows])
        self.assertEqual(guard.validate_bridge_contract(rows), [])

    def test_rejects_miscompiled_extra_page_as_well_as_original_examples(self):
        (self.source / "reports_centre.bundle.js").write_text(
            "import UI from './reports_centre/Report.vue';", encoding="utf-8"
        )
        self.make("reports_centre.bundle.js", "__v_isVNode")
        self.save_manifest()
        self.assertTrue(any("reports_centre.bundle.js" in issue for issue in
                            guard.validate_bridge_contract(guard.inspect(self.bench))))

    def test_rejects_duplicate_vue_even_when_bridge_marker_is_present(self):
        self.make("professional_selling.bundle.js", guard.BRIDGE_MARKER + " __v_isVNode")
        self.assertTrue(any("professional_selling.bundle.js" in issue for issue in
                            guard.validate_bridge_contract(guard.inspect(self.bench))))

    def test_rejects_missing_bundles(self):
        self.manifest.pop("stock_adjustment.bundle.js")
        self.save_manifest()
        self.assertTrue(any("stock_adjustment.bundle.js" in issue for issue in
                            guard.validate_bridge_contract(guard.inspect(self.bench))))

    def test_standalone_audit_cli_requires_no_frappe_package_import(self):
        script = APP_ROOT.parent / "scripts" / "audit_vue_bundle_artifacts.py"
        result = subprocess.run(
            [sys.executable, "-S", str(script), "--bench", str(self.bench), "--strict"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Compiled Vue bridge gate PASS", result.stdout)

    def test_hooks_enforce_build_gate_after_compilation(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn(
            'after_build = "retailedge.vue_runtime_build_guard.verify_retailedge_after_build"',
            hooks,
        )
        self.assertNotIn("after_app_build = ", hooks)


if __name__ == "__main__":
    unittest.main()
