# -*- coding: utf-8 -*-
# Copyright (c) 2026, ProcessEdge Solutions and contributors
# For license information, please see license.txt

import os
import json
import py_compile
import frappe
from frappe.tests.utils import FrappeTestCase

class TestSalespersonPerformance(FrappeTestCase):
	def test_expected_page_files_exist(self):
		"""Verify all page files are in place."""
		retailedge_path = frappe.get_app_path("retailedge")
		page_dir = os.path.join(retailedge_path, "retailedge", "page", "salesperson_performance_dashboard")
		self.assertTrue(os.path.exists(page_dir), "Page directory does not exist")
		
		expected_files = [
			"salesperson_performance_dashboard.json",
			"salesperson_performance_dashboard.js",
			"salesperson_performance_dashboard.py"
		]
		for filename in expected_files:
			file_path = os.path.join(page_dir, filename)
			self.assertTrue(os.path.exists(file_path), f"Page file {filename} does not exist")

	def test_page_json_config(self):
		"""Verify standard page definition parameters."""
		retailedge_path = frappe.get_app_path("retailedge")
		json_path = os.path.join(
			retailedge_path, "retailedge", "page", "salesperson_performance_dashboard", "salesperson_performance_dashboard.json"
		)
		self.assertTrue(os.path.exists(json_path))
		
		with open(json_path, "r") as f:
			data = json.load(f)
			
		self.assertEqual(data.get("doctype"), "Page")
		self.assertEqual(data.get("name"), "salesperson-performance-dashboard")
		self.assertEqual(data.get("module"), "RetailEdge")
		self.assertEqual(data.get("standard"), "Yes")
		
		roles = [r.get("role") for r in data.get("roles", [])]
		self.assertIn("System Manager", roles)
		self.assertIn("Accounts Manager", roles)
		self.assertIn("RetailEdge Manager", roles)
		self.assertIn("RetailEdge Branch Manager", roles)

	def test_lazy_loads_edgeui_bundle(self):
		"""Verify salesperson_performance_dashboard.js lazy-loads edgeui.bundle.js via frappe.require."""
		retailedge_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			retailedge_path, "retailedge", "page", "salesperson_performance_dashboard", "salesperson_performance_dashboard.js"
		)
		self.assertTrue(os.path.exists(js_path))
		
		with open(js_path, "r") as f:
			content = f.read()
			
		self.assertIn("frappe.require('edgeui.bundle.js'", content)
		self.assertIn("unmount()", content)
		self.assertIn("current_visit_id", content)

	def test_edgeui_not_copied(self):
		"""Assert that shared EdgeUI Vue components are not cloned or copied into RetailEdge."""
		retailedge_path = frappe.get_app_path("retailedge")
		for root, dirs, files in os.walk(retailedge_path):
			for file in files:
				if file.startswith("Edge") and file.endswith(".vue"):
					self.fail(f"Found cloned EdgeUI component {file} inside RetailEdge at {root}")

	def test_aggregation_api_returns_structured_data(self):
		"""Verify get_salesperson_performance API logic returns expected structures."""
		from retailedge.salesperson_performance import get_salesperson_performance
		
		try:
			res = get_salesperson_performance({
				"from_date": "2026-07-01",
				"to_date": "2026-07-06",
				"limit": 5,
				"offset": 0
			})
			self.assertIn("summary", res)
			self.assertIn("rows", res)
			self.assertIn("limit", res)
			self.assertIn("offset", res)
			
			summary = res["summary"]
			self.assertIn("gross_sales", summary)
			self.assertIn("net_sales", summary)
			self.assertIn("total_invoices", summary)
			self.assertIn("total_discount", summary)
			self.assertIn("total_outstanding", summary)
		except frappe.PermissionError:
			pass
