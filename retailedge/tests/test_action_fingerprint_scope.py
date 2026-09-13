from __future__ import annotations

from hashlib import sha256
import unittest

from retailedge.action_follow_up import action_fingerprint


class TestActionFingerprintScope(unittest.TestCase):
	def test_empty_scope_preserves_legacy_six_field_hash(self):
		values = [
			"Example Company",
			"Lagos",
			"receivables",
			"overdue",
			"Overdue receivables",
			"/app/customer-receivables",
		]
		legacy = sha256("|".join(values).encode("utf-8")).hexdigest()
		current = action_fingerprint(
			company=values[0],
			branch=values[1],
			source=values[2],
			kind=values[3],
			label=values[4],
			route=values[5],
		)
		self.assertEqual(current, legacy)

	def test_non_empty_scope_isolates_period_dependent_action(self):
		common = dict(
			company="Example Company",
			branch="Lagos",
			source="r11_customer_opportunity",
			kind="customer_retention_follow_up",
			label="Customers need retention follow-up",
			route="/app/customer-opportunity-intelligence",
		)
		august = action_fingerprint(**common, scope="period:2026-08-01:2026-08-31")
		july = action_fingerprint(**common, scope="period:2026-07-01:2026-07-31")
		self.assertNotEqual(august, july)


if __name__ == "__main__":
	unittest.main()
