from __future__ import annotations

from unittest.mock import patch
import unittest

from retailedge.api import get_cost_visibility_rules


class CostVisibilityRulesTests(unittest.TestCase):
	@patch("retailedge.api._should_hide_cost_price", return_value=False)
	def test_rules_return_hidden_zero_for_unrestricted_user(self, _mock_should_hide):
		result = get_cost_visibility_rules()
		self.assertEqual(result["hide_cost_price"], 0)
		self.assertEqual(result["fieldnames"], [])
		self.assertEqual(result["label_keywords"], [])

	@patch("retailedge.api._should_hide_cost_price", return_value=True)
	def test_rules_return_fieldnames_for_restricted_user(self, _mock_should_hide):
		result = get_cost_visibility_rules()
		self.assertEqual(result["hide_cost_price"], 1)
		self.assertTrue(result["fieldnames"])
		self.assertTrue(result["label_keywords"])

	@patch("retailedge.api._should_hide_cost_price", return_value=False)
	def test_administrator_does_not_receive_hidden_rules(self, _mock_should_hide):
		result = get_cost_visibility_rules()
		self.assertEqual(result["hide_cost_price"], 0)
		self.assertEqual(result["fieldnames"], [])

	@patch("retailedge.api._should_hide_cost_price", return_value=False)
	def test_system_manager_does_not_receive_hidden_rules(self, _mock_should_hide):
		result = get_cost_visibility_rules()
		self.assertEqual(result["hide_cost_price"], 0)
		self.assertEqual(result["label_keywords"], [])

	@patch("retailedge.api._should_hide_cost_price", return_value=False)
	def test_feature_disabled_returns_no_hidden_rules(self, _mock_should_hide):
		result = get_cost_visibility_rules()
		self.assertEqual(result["hide_cost_price"], 0)
