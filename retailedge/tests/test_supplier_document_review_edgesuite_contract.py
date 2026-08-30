from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestSupplierDocumentReviewEdgeSuiteContract(unittest.TestCase):
	def test_page_requires_edgesuite_runtime_and_governed_shells(self):
		bundle = (APP_ROOT / "public" / "js" / "supplier_document_review.bundle.js").read_text()
		page_js = (APP_ROOT / "retailedge" / "page" / "supplier_document_review" / "supplier_document_review.js").read_text()
		vue = (APP_ROOT / "public" / "js" / "supplier_document_review" / "SupplierDocumentReview.vue").read_text()
		self.assertIn("window.EdgeSuiteUI", bundle)
		self.assertIn("edgeUI.createEdgeApp", bundle)
		self.assertIn("edgeui.bundle.js", page_js)
		self.assertIn("window.EdgeSuiteUI?.components", page_js)
		for component in (
			"<EdgeAppShell",
			"<EdgeDashboardShell",
			"<EdgeDashboardGrid",
			"<EdgeDashboardSection",
			"<EdgeLinkField",
		):
			self.assertIn(component, vue)
		for component_name in (
			'"EdgeAppShell"',
			'"EdgeDashboardShell"',
			'"EdgeDashboardGrid"',
			'"EdgeDashboardSection"',
			'"EdgeLinkField"',
		):
			self.assertIn(component_name, vue)
		self.assertIn("edge-button edge-button--primary", vue)
		self.assertIn("class=\"edge-input\"", vue)
		self.assertNotIn("window.EdgeUI", bundle + page_js + vue)
		self.assertNotIn("frappe.ui.Dialog", vue)
		self.assertNotIn("frappe.prompt", vue)

	def test_frontend_only_sends_intake_or_extraction_identity_for_authoritative_actions(self):
		vue = (APP_ROOT / "public" / "js" / "supplier_document_review" / "SupplierDocumentReview.vue").read_text()
		self.assertIn("intake_name: this.modal.row.intake", vue)
		self.assertIn("extraction_name: row.extraction", vue)
		self.assertIn("extraction_name: this.modal.row.extraction", vue)
		self.assertNotIn("supplier: this.modal.row.supplier", vue)
		self.assertNotIn("company: this.modal.row.company", vue)
		self.assertNotIn("purchase_order: this.modal.row.purchase_order", vue)

	def test_page_exposes_human_review_before_draft_handoff(self):
		vue = (APP_ROOT / "public" / "js" / "supplier_document_review" / "SupplierDocumentReview.vue").read_text()
		for label in (
			"Start Review",
			"Record Extraction",
			"Accept Extraction",
			"Reject Extraction",
			"Accept Document",
			"Reject Document",
			"Prepare Draft PI",
		):
			self.assertIn(label, vue)
		self.assertIn("creates drafts only", vue)
		self.assertNotIn(".submit()", vue)

	def test_page_roles_are_internal_buying_and_accounts_only(self):
		schema = (APP_ROOT / "retailedge" / "page" / "supplier_document_review" / "supplier_document_review.json").read_text()
		self.assertIn('"Purchase User"', schema)
		self.assertIn('"Purchase Manager"', schema)
		self.assertIn('"Accounts User"', schema)
		self.assertIn('"Accounts Manager"', schema)
		self.assertNotIn('"Supplier"', schema)


if __name__ == "__main__":
	unittest.main()
