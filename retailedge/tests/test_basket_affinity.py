from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.basket_affinity import (
	MAX_ITEMS_PER_BASKET,
	MAX_UNIQUE_PAIRS,
	build_basket_affinity_rows,
)


class TestBasketAffinity(FrappeTestCase):
	def test_duplicate_item_lines_count_once_per_basket(self):
		rows, stats = build_basket_affinity_rows(
			[
				frappe._dict(parent="SINV-1", item_code="A", item_group="Group A", qty=1),
				frappe._dict(parent="SINV-1", item_code="A", item_group="Group A", qty=2),
				frappe._dict(parent="SINV-1", item_code="B", item_group="Group B", qty=1),
			]
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["pair_invoice_count"], 1)
		self.assertEqual(rows[0]["item_a_invoice_count"], 1)
		self.assertEqual(rows[0]["item_b_invoice_count"], 1)
		self.assertEqual(stats["eligible_baskets"], 1)

	def test_support_share_and_directional_confidence_are_invoice_based(self):
		rows, stats = build_basket_affinity_rows(
			[
				frappe._dict(parent="SINV-1", item_code="A", item_group="G1", qty=1),
				frappe._dict(parent="SINV-1", item_code="B", item_group="G2", qty=1),
				frappe._dict(parent="SINV-2", item_code="A", item_group="G1", qty=1),
				frappe._dict(parent="SINV-2", item_code="B", item_group="G2", qty=1),
				frappe._dict(parent="SINV-3", item_code="A", item_group="G1", qty=1),
				frappe._dict(parent="SINV-3", item_code="C", item_group="G3", qty=1),
			]
		)
		pair = next(row for row in rows if {row["item_a"], row["item_b"]} == {"A", "B"})
		self.assertEqual(pair["pair_invoice_count"], 2)
		self.assertAlmostEqual(pair["basket_share_percent"], 200 / 3)
		self.assertAlmostEqual(pair["confidence_a_to_b_percent"], 200 / 3)
		self.assertEqual(pair["confidence_b_to_a_percent"], 100)
		self.assertEqual(stats["eligible_baskets"], 3)

	def test_non_positive_quantity_rows_do_not_create_purchase_pairs(self):
		rows, stats = build_basket_affinity_rows(
			[
				frappe._dict(parent="SINV-1", item_code="A", item_group="G1", qty=1),
				frappe._dict(parent="SINV-1", item_code="RETURN-LINE", item_group="G2", qty=-1),
			]
		)
		self.assertEqual(rows, [])
		self.assertEqual(stats["eligible_baskets"], 0)
		self.assertEqual(stats["unique_items"], 1)

	def test_item_anchor_filters_pairs_without_removing_companions(self):
		items = [
			frappe._dict(parent="SINV-1", item_code="A", item_group="G1", qty=1),
			frappe._dict(parent="SINV-1", item_code="B", item_group="G2", qty=1),
			frappe._dict(parent="SINV-2", item_code="B", item_group="G2", qty=1),
			frappe._dict(parent="SINV-2", item_code="C", item_group="G3", qty=1),
		]
		rows, _stats = build_basket_affinity_rows(items, anchor_item="A")
		self.assertEqual(len(rows), 1)
		self.assertEqual({rows[0]["item_a"], rows[0]["item_b"]}, {"A", "B"})

	def test_item_group_anchor_keeps_cross_group_companion(self):
		rows, _stats = build_basket_affinity_rows(
			[
				frappe._dict(parent="SINV-1", item_code="A", item_group="Batteries", qty=1),
				frappe._dict(parent="SINV-1", item_code="B", item_group="Inverters", qty=1),
			],
			anchor_item_group="Batteries",
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual({rows[0]["item_a_group"], rows[0]["item_b_group"]}, {"Batteries", "Inverters"})

	def test_single_item_invoice_counts_for_confidence_denominator_not_pair_support(self):
		rows, stats = build_basket_affinity_rows(
			[
				frappe._dict(parent="SINV-1", item_code="A", item_group="G1", qty=1),
				frappe._dict(parent="SINV-1", item_code="B", item_group="G2", qty=1),
				frappe._dict(parent="SINV-2", item_code="A", item_group="G1", qty=1),
			]
		)
		self.assertEqual(stats["eligible_baskets"], 1)
		self.assertEqual(rows[0]["pair_invoice_count"], 1)
		self.assertEqual(rows[0]["confidence_a_to_b_percent"], 50)
		self.assertEqual(rows[0]["confidence_b_to_a_percent"], 100)

	def test_per_basket_product_cap_fails_closed(self):
		items = [
			frappe._dict(parent="SINV-LARGE", item_code=f"ITEM-{index:03d}", item_group="G", qty=1)
			for index in range(MAX_ITEMS_PER_BASKET + 1)
		]
		with self.assertRaises(frappe.ValidationError):
			build_basket_affinity_rows(items)

	@patch("retailedge.basket_affinity.MAX_UNIQUE_PAIRS", 1)
	def test_global_unique_pair_cap_fails_closed(self):
		items = [
			frappe._dict(parent="SINV-1", item_code="A", item_group="G", qty=1),
			frappe._dict(parent="SINV-1", item_code="B", item_group="G", qty=1),
			frappe._dict(parent="SINV-1", item_code="C", item_group="G", qty=1),
		]
		with self.assertRaises(frappe.ValidationError):
			build_basket_affinity_rows(items)

	def test_pair_cap_constant_is_explicit(self):
		self.assertEqual(MAX_UNIQUE_PAIRS, 5000)


if __name__ == "__main__":
	unittest.main()
