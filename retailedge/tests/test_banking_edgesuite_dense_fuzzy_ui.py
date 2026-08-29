from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = APP_ROOT / "public/js/bank_matching_fuzzy_discovery_adapter.js"
DENSE_CSS = APP_ROOT / "public/css/bank_matching_dense_workspace.css"
LOADER = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"


class BankingEdgeSuiteDenseFuzzyUITests(unittest.TestCase):
    def test_fuzzy_adapter_is_valid_javascript(self):
        completed = subprocess.run(
            ["node", "--check", str(ADAPTER)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_adapter_redirects_workspace_discovery_without_touching_reconciliation(self):
        asset = ADAPTER.read_text()
        self.assertIn("retailedge.banking_workspace.get_banking_workspace_rows", asset)
        self.assertIn("retailedge.banking_workspace_fuzzy.get_fuzzy_banking_workspace_rows", asset)
        self.assertIn("DEFAULT_DATE_TOLERANCE_DAYS = 3", asset)
        self.assertIn("get_direction_aware_bank_candidates", asset)
        self.assertNotIn("match_and_reconcile", asset)
        self.assertNotIn("confirm_bank_transaction_match", asset)

    def test_dense_css_removes_desktop_horizontal_scroll_contract(self):
        css = DENSE_CSS.read_text()
        self.assertIn("overflow-x: hidden !important", css)
        self.assertIn("min-width: 0 !important", css)
        self.assertIn("table-layout: fixed", css)
        self.assertIn("padding: .46rem .5rem !important", css)
        self.assertIn("@media (max-width: 900px)", css)
        self.assertIn("display: block", css)

    def test_loader_orders_fuzzy_and_dense_assets_before_workspace(self):
        loader = LOADER.read_text()
        self.assertIn("bank_matching_fuzzy_discovery_adapter.js", loader)
        self.assertIn("bank_matching_dense_workspace.css", loader)
        self.assertIn("bank_matching_edgesuite_workspace.js", loader)
        self.assertLess(loader.index("FUZZY_DISCOVERY_ASSET"), loader.index("WORKSPACE_ASSET"))
        self.assertLess(loader.index("DENSE_WORKSPACE_CSS"), loader.index("WORKSPACE_ASSET"))


if __name__ == "__main__":
    unittest.main()
