from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge import master_experience


class TestRIR2B3BankingReadinessPromotionContract(unittest.TestCase):
	def _navigation(self):
		return [
			{
				"key": "money",
				"label": "Money",
				"items": [
					{
						"label": "Payments",
						"target_type": "DocType",
						"target": "Payment Entry",
					},
					{
						"label": "Bank Matching",
						"target_type": "Page",
						"target": "bank-matching-reconciliation",
					},
				],
			}
		]

	def test_banking_readiness_target_is_the_hardened_page(self):
		self.assertEqual(master_experience.BANKING_READINESS_ITEM["target_type"], "Page")
		self.assertEqual(master_experience.BANKING_READINESS_ITEM["target"], "banking-readiness")

	def test_page_is_not_promoted_when_current_reader_cannot_open_it(self):
		navigation = self._navigation()
		with patch.object(master_experience, "_can_open_page", return_value=False):
			master_experience._promote_banking_readiness(navigation)

		targets = [item["target"] for item in navigation[0]["items"]]
		self.assertNotIn("banking-readiness", targets)

	def test_permitted_page_is_promoted_immediately_before_bank_matching(self):
		navigation = self._navigation()
		with patch.object(master_experience, "_can_open_page", return_value=True):
			master_experience._promote_banking_readiness(navigation)

		targets = [item["target"] for item in navigation[0]["items"]]
		self.assertEqual(
			targets,
			["Payment Entry", "banking-readiness", "bank-matching-reconciliation"],
		)

	def test_promotion_is_idempotent(self):
		navigation = self._navigation()
		with patch.object(master_experience, "_can_open_page", return_value=True):
			master_experience._promote_banking_readiness(navigation)
			master_experience._promote_banking_readiness(navigation)

		targets = [item["target"] for item in navigation[0]["items"]]
		self.assertEqual(targets.count("banking-readiness"), 1)

	def test_compact_workspace_is_not_part_of_this_controlled_promotion(self):
		source = __import__("retailedge.workspace_home", fromlist=["HOME_WORKSPACE_ITEMS"])
		targets = {(item.link_type, item.link_to) for item in source.HOME_WORKSPACE_ITEMS}
		self.assertNotIn(("Page", "banking-readiness"), targets)


if __name__ == "__main__":
	unittest.main()
