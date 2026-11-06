from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_non_vue_published_bundle_does_not_require_shared_vue_bridge(self):
        self.make("retail_helpers.bundle.js", "console.log('retail helpers');")
        self.save_manifest()
        self.assertEqual(guard.validate_bridge_contract(guard.inspect(self.bench)), [])

    def test_rejects_hidden_vue_runtime_from_indirect_js_import(self):
        # Vue can be imported via a JS module, without .vue in entry source.
        self.make("indirect_vue.bundle.js", "__v_isVNode")
        self.save_manifest()
        issues = guard.validate_bridge_contract(guard.inspect(self.bench))
        self.assertTrue(any("indirect_vue.bundle.js" in issue for issue in issues))

    def test_non_direct_bundle_with_shared_bridge_is_accepted(self):
        self.make("indirect_bridge.bundle.js", guard.BRIDGE_MARKER)
        self.save_manifest()
        self.assertEqual(guard.validate_bridge_contract(guard.inspect(self.bench)), [])

    def test_rejects_duplicate_vue_even_when_bridge_marker_is_present(self):
        self.make("professional_selling.bundle.js", guard.BRIDGE_MARKER + " __v_isVNode")
        self.assertTrue(any("professional_selling.bundle.js" in issue for issue in
                            guard.validate_bridge_contract(guard.inspect(self.bench))))

    def test_rejects_missing_bundles(self):
        self.manifest.pop("stock_adjustment.bundle.js")
        self.save_manifest()
        self.assertTrue(any("stock_adjustment.bundle.js" in issue for issue in
                            guard.validate_bridge_contract(guard.inspect(self.bench))))

    def test_app_install_can_precede_shared_runtime_build(self):
        # Frappe runs each app's after_build after its own scoped compilation.
        self.manifest.pop(guard.SHARED_BUNDLE)
        self.save_manifest()
        rows = guard.inspect(self.bench)
        self.assertEqual(guard.validate_bridge_contract(rows, require_shared=False), [])
        self.assertTrue(
            any("Shared EdgeSuite" in issue for issue in guard.validate_bridge_contract(rows))
        )

    def test_scoped_build_still_rejects_duplicate_product_vue(self):
        self.manifest.pop(guard.SHARED_BUNDLE)
        self.make("professional_selling.bundle.js", "__v_isVNode")
        self.save_manifest()
        issues = guard.validate_bridge_contract(guard.inspect(self.bench), require_shared=False)
        self.assertTrue(any("professional_selling.bundle.js" in issue for issue in issues))

    def test_scoped_build_still_requires_mandatory_product_bundle(self):
        self.manifest.pop(guard.SHARED_BUNDLE)
        self.manifest.pop("make_sale.bundle.js")
        self.save_manifest()
        issues = guard.validate_bridge_contract(guard.inspect(self.bench), require_shared=False)
        self.assertTrue(any("make_sale.bundle.js" in issue for issue in issues))

    def test_present_but_invalid_shared_runtime_rejected_even_when_scoped(self):
        self.make(guard.SHARED_BUNDLE, "console.log('invalid shared bundle')")
        issues = guard.validate_bridge_contract(guard.inspect(self.bench), require_shared=False)
        self.assertTrue(any("Shared EdgeSuite" in issue for issue in issues))

    def test_actual_after_build_hook_allows_missing_shared_during_install(self):
        self.manifest.pop(guard.SHARED_BUNDLE)
        self.save_manifest()
        with patch("frappe.utils.get_bench_path", return_value=str(self.bench)):
            guard.verify_retailedge_after_build()

    def test_actual_after_build_hook_rejects_embedded_product_vue(self):
        self.manifest.pop(guard.SHARED_BUNDLE)
        self.make("professional_selling.bundle.js", guard.BRIDGE_MARKER + " __v_isVNode")
        self.save_manifest()
        with patch("frappe.utils.get_bench_path", return_value=str(self.bench)):
            with self.assertRaisesRegex(RuntimeError, "professional_selling.bundle.js"):
                guard.verify_retailedge_after_build()

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
