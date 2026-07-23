from __future__ import annotations

import json
import unittest
from pathlib import Path

import frappe

from retailedge.workspace_navigation import (
	navigation_target_key,
	normalize_grouped_navigation,
	normalize_sidebar_data,
	normalize_workspace_data,
)


class TestRetailEdgeNavigationQuality(unittest.TestCase):
	def app_path(self, *parts: str) -> Path:
		return Path(frappe.get_app_path("retailedge", *parts))

	def test_navigation_target_key_uses_link_type_and_real_target(self):
		self.assertEqual(
			navigation_target_key(
				{
					"type": "Link",
					"link_type": "Report",
					"link_to": "RetailEdge Reconciliation Handoff",
					"label": "Failed Reconciliation Repair",
				}
			),
			("Report", "RetailEdge Reconciliation Handoff"),
		)
		self.assertIsNone(navigation_target_key({"type": "Section Break", "label": "Reports"}))

	def test_grouped_navigation_keeps_first_target_and_drops_empty_sections(self):
		rows = [
			{"type": "Section Break", "label": "Review"},
			{
				"type": "Link",
				"label": "Reconciliation Handoff",
				"link_type": "Report",
				"link_to": "RetailEdge Reconciliation Handoff",
			},
			{"type": "Section Break", "label": "Reports"},
			{
				"type": "Link",
				"label": "Reconciliation Handoff Report",
				"link_type": "Report",
				"link_to": "RetailEdge Reconciliation Handoff",
			},
			{"type": "Section Break", "label": "Setup"},
			{
				"type": "Link",
				"label": "Branch Profile User",
				"link_type": "DocType",
				"link_to": "RetailEdge Branch Profile User",
			},
		]
		normalized = normalize_grouped_navigation(
			rows,
			section_types=frozenset({"Section Break"}),
		)
		self.assertEqual([row.get("label") for row in normalized], ["Review", "Reconciliation Handoff"])

	def test_optional_posnext_links_are_kept_when_targets_exist(self):
		rows = [
			{"type": "Section Break", "label": "Operations"},
			{
				"type": "Link",
				"label": "POS Opening Shift",
				"link_type": "DocType",
				"link_to": "POS Opening Shift",
			},
			{
				"type": "Link",
				"label": "POS Closing Shift",
				"link_type": "DocType",
				"link_to": "POS Closing Shift",
			},
		]
		normalized = normalize_grouped_navigation(
			rows,
			section_types=frozenset({"Section Break"}),
			target_exists=lambda link_type, target: True,
		)
		self.assertEqual(
			[row.get("label") for row in normalized],
			["Operations", "POS Opening Shift", "POS Closing Shift"],
		)

	def test_optional_posnext_links_are_omitted_when_targets_are_unavailable(self):
		rows = [
			{"type": "Section Break", "label": "Operations"},
			{
				"type": "Link",
				"label": "POS Opening Shift",
				"link_type": "DocType",
				"link_to": "POS Opening Shift",
			},
			{
				"type": "Link",
				"label": "RetailEdge Cashier Expense",
				"link_type": "DocType",
				"link_to": "RetailEdge Cashier Expense",
			},
		]
		normalized = normalize_grouped_navigation(
			rows,
			section_types=frozenset({"Section Break"}),
			target_exists=lambda link_type, target: target != "POS Opening Shift",
		)
		self.assertEqual(
			[row.get("label") for row in normalized],
			["Operations", "RetailEdge Cashier Expense"],
		)

	def test_source_workspace_normalization_removes_aliases_and_child_tables(self):
		workspace_path = self.app_path(
			"retailedge",
			"workspace",
			"retailedge",
			"retailedge.json",
		)
		data = normalize_workspace_data(json.loads(workspace_path.read_text()))
		links = [row for row in data.get("links", []) if row.get("type") == "Link"]
		labels = {row.get("label") for row in links}
		targets = [navigation_target_key(row) for row in links]

		self.assertEqual(len(targets), len(set(targets)))
		for removed_label in (
			"Branch Profile User",
			"Bank Transaction Matching Report",
			"Reconciliation Handoff Report",
			"Payment Statement Import Register",
			"Reconciliation Readiness",
			"Sales Invoice Verification Sync",
			"Bank Match Integrity Check",
			"Failed Reconciliation Repair",
		):
			self.assertNotIn(removed_label, labels)

	def test_source_sidebar_normalization_removes_duplicate_targets_and_empty_sections(self):
		sidebar_path = self.app_path(
			"retailedge",
			"workspace_sidebar",
			"retailedge",
			"retailedge.json",
		)
		data = normalize_sidebar_data(json.loads(sidebar_path.read_text()))
		items = data.get("items", [])
		links = [row for row in items if row.get("type") == "Link" and row.get("label") != "Home"]
		targets = [navigation_target_key(row) for row in links]
		labels = {row.get("label") for row in links}

		self.assertEqual(len(targets), len(set(targets)))
		self.assertNotIn("Branch Profile User", labels)
		self.assertNotIn("Reconciliation Handoff Report", labels)
		self.assertNotIn("Failed Reconciliation Repair", labels)

		for index, row in enumerate(items):
			if row.get("type") != "Section Break":
				continue
			next_row = items[index + 1] if index + 1 < len(items) else None
			self.assertIsNotNone(next_row)
			self.assertEqual(next_row.get("type"), "Link")

	def test_workspace_sync_and_product_menu_use_navigation_policy(self):
		workspace_sync = self.app_path("workspace_sync.py").read_text()
		product_menu = self.app_path("public", "js", "retailedge_product_menu.js").read_text()

		self.assertIn("normalize_workspace_data", workspace_sync)
		self.assertIn("normalize_sidebar_data", workspace_sync)
		self.assertIn("_navigation_target_exists", workspace_sync)
		self.assertIn("frappe.db.exists", workspace_sync)
		self.assertIn('"Reports & Analytics"', product_menu)
		self.assertIn("seenTargets", product_menu)
		self.assertIn("HIDDEN_NAVIGATION_TARGETS", product_menu)
		self.assertIn("navigationKey(normalized)", product_menu)
		self.assertNotIn('"Reports & Review"', product_menu)

	def test_ci_uses_file_urls_for_checked_out_apps(self):
		workflow = self.app_path("..", ".github", "workflows", "ci.yml").resolve().read_text()
		self.assertIn('bench get-app --skip-assets "file://$GITHUB_WORKSPACE/edgesuite-ui-source"', workflow)
		self.assertIn('bench get-app --skip-assets "file://$GITHUB_WORKSPACE"', workflow)
		self.assertNotIn('bench get-app --skip-assets edgesuite_ui "$GITHUB_WORKSPACE/edgesuite-ui-source"', workflow)

	def test_navigation_quality_phase_does_not_add_business_document_writes(self):
		paths = [
			self.app_path("workspace_navigation.py"),
			self.app_path("public", "js", "retailedge_product_menu.js"),
		]
		combined = "\n".join(path.read_text().lower() for path in paths)
		for forbidden in (
			"doc.save(",
			"doc.submit(",
			"frappe.db.set_value",
			"frappe.delete_doc",
			"make_payment_entry",
			"make_journal_entry",
			"reconcile_vouchers",
		):
			self.assertNotIn(forbidden, combined)
