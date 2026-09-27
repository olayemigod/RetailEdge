from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import call, patch

from retailedge.patches import migrate_price_list_governance_v2 as migration


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPriceListGovernanceMigration(unittest.TestCase):
	def test_patch_runs_before_model_sync(self):
		patches = (APP_ROOT / "patches.txt").read_text(encoding="utf-8")
		pre_model = patches.split("[post_model_sync]", 1)[0]
		self.assertIn(
			"retailedge.patches.migrate_price_list_governance_v2",
			pre_model,
		)

	def test_legacy_policy_translation_preserves_priority_and_safe_fallbacks(self):
		self.assertEqual(
			migration._translate_policy(
				"selling",
				"Party > POS > Branch > Assigned Choice",
			),
			[
				"party_default",
				"pos_profile",
				"branch_default",
				"user_default",
				"user_permission",
				"erpnext_default",
				"standard_price_list",
			],
		)
		self.assertEqual(
			migration._translate_policy(
				"selling",
				"Assigned Choice > Party > POS > Branch",
			)[:5],
			[
				"user_default",
				"user_permission",
				"party_default",
				"pos_profile",
				"branch_default",
			],
		)

	@patch.object(migration, "_raw_set_single_value")
	@patch.object(migration, "_raw_single_value")
	@patch.object(migration, "_table_exists", return_value=True)
	@patch.object(migration, "_persisted_docfield_exists")
	def test_legacy_disabled_switch_stays_disabled_across_all_v2_sources(
		self, mock_field, _mock_table, mock_value, mock_set
	):
		def persisted(_parent, fieldname):
			return fieldname == "allow_price_list_switch"

		mock_field.side_effect = persisted
		mock_value.side_effect = lambda fieldname: {
			"selling_price_list_policy": "Party > Branch > POS > Assigned Choice",
			"buying_price_list_policy": "Branch > Party > Assigned Choice",
			"allow_price_list_switch": "0",
		}.get(fieldname)

		migration._migrate_legacy_price_list_settings()

		values = {args[0]: args[1] for args, _kwargs in (entry for entry in mock_set.call_args_list)}
		self.assertEqual(values["enable_assigned_price_list_switching"], "0")
		for fieldname in (
			"allow_price_list_switch_from_party_default",
			"allow_price_list_switch_from_pos_default",
			"allow_price_list_switch_from_branch_default",
			"allow_price_list_switch_from_user_default",
			"allow_price_list_switch_from_system_default",
		):
			self.assertEqual(values[fieldname], "0")
		self.assertEqual(
			values["selling_price_list_precedence"].splitlines()[:3],
			["party_default", "branch_default", "pos_profile"],
		)
		self.assertEqual(
			values["buying_price_list_precedence"].splitlines()[:2],
			["branch_default", "party_default"],
		)

	@patch.object(migration, "_raw_set_single_value")
	@patch.object(migration, "_table_exists", return_value=True)
	@patch.object(migration, "_persisted_docfield_exists", return_value=True)
	def test_migration_noops_after_v2_schema_is_already_persisted(
		self, _mock_field, _mock_table, mock_set
	):
		migration._migrate_legacy_price_list_settings()
		mock_set.assert_not_called()

	@patch.object(migration, "_table_exists", return_value=True)
	@patch.object(migration.frappe.db, "sql")
	def test_branch_assignment_child_parentfield_is_migrated_idempotently(
		self, mock_sql, _mock_table
	):
		migration._migrate_branch_assignment_parentfield()
		sql, params = mock_sql.call_args.args
		self.assertIn("SET parentfield = 'allowed_price_lists'", sql)
		self.assertIn("parentfield = 'price_lists'", sql)
		self.assertEqual(params, ("RetailEdge Branch Assignment",))


if __name__ == "__main__":
	unittest.main()
