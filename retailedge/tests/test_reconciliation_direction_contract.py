from __future__ import annotations

import unittest
from pathlib import Path


class ReconciliationDirectionContractTests(unittest.TestCase):
	def test_preflight_uses_canonical_bank_transaction_direction(self):
		bridge_path = Path(__file__).resolve().parents[1] / "reconciliation_bridge.py"
		source = bridge_path.read_text()

		self.assertIn("normalize_bank_transaction(row.get(\"bank_transaction\"))", source)
		self.assertIn('bank_direction not in {"Inflow", "Outflow"}', source)
		self.assertIn('"direction": bank_direction', source)
		self.assertIn('combined["direction"] = bank_direction', source)
		self.assertNotIn('"direction": "Inflow",', source)


if __name__ == "__main__":
	unittest.main()
