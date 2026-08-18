from __future__ import annotations

import unittest
from pathlib import Path


class BankingPageContractTests(unittest.TestCase):
    def test_banking_page_calls_workspace_service(self):
        page_js = Path(
            "retailedge/retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
        ).read_text()
        self.assertIn(
            "retailedge.banking_workspace.get_banking_workspace_rows",
            page_js,
        )
        self.assertIn("All", page_js)
        self.assertIn("Inflows", page_js)
        self.assertIn("Outflows", page_js)
        self.assertIn("To Match", page_js)
        self.assertIn("To Reconcile", page_js)
        self.assertIn("Exceptions", page_js)
        self.assertIn("Reconciled", page_js)


if __name__ == "__main__":
    unittest.main()
