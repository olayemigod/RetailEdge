from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestOperatingContextDefaultsPhase3(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_new_document_seeding_uses_phase2_operating_context(self):
		source = self.read("branch_defaults_application.py")
		for contract in (
			"get_effective_operating_context",
			"_seed_new_doc_from_operating_context(doc)",
			"def _seed_new_doc_from_operating_context(doc):",
			'"Operating Context"',
			"_get_transaction_branch_field",
		):
			self.assertIn(contract, source)

	def test_existing_and_submitted_documents_are_never_recontextualized(self):
		source = self.read("branch_defaults_application.py")
		seed_start = source.index("def _seed_new_doc_from_operating_context")
		seed_end = source.index("\n\ndef _is_new_doc", seed_start)
		seed_source = source[seed_start:seed_end]
		self.assertIn('getattr(doc, "docstatus", 0) in (1, 2)', seed_source)
		self.assertIn("if not _is_new_doc(doc):", seed_source)
		self.assertIn('"existing_document"', seed_source)
		self.assertNotIn("db.set_value", seed_source)
		self.assertNotIn("save(", seed_source)
		self.assertNotIn("submit(", seed_source)

	def test_explicit_branch_stock_pos_and_shift_context_wins(self):
		source = self.read("branch_defaults_application.py")
		for fieldname in (
			'"branch"',
			'"retailedge_branch"',
			'"pos_profile"',
			'"linked_pos_opening_shift"',
			'"pos_opening_shift"',
			'"linked_pos_closing_shift"',
			'"pos_closing_shift"',
			'"set_warehouse"',
			'"from_warehouse"',
			'"to_warehouse"',
		):
			self.assertIn(fieldname, source)
		self.assertIn("_has_explicit_operational_context(doc)", source)
		self.assertIn('"explicit_context_preserved"', source)

	def test_existing_default_application_still_preserves_values(self):
		source = self.read("branch_defaults_application.py")
		self.assertIn('"existing_value_preserved"', source)
		self.assertIn("current not in (None, \"\") and not overwrite", source)
		self.assertIn('getattr(doc, "branch", None) or getattr(doc, "retailedge_branch", None)', source)

	def test_preview_api_requires_create_permission_and_never_saves(self):
		source = self.read("new_document_defaults.py")
		for contract in (
			"@frappe.whitelist()",
			"def get_new_document_operating_defaults(",
			'frappe.has_permission(doctype, "create")',
			'payload.pop("name", None)',
			'payload["docstatus"] = 0',
			"_seed_new_doc_from_operating_context(doc)",
			"apply_branch_profile_defaults_to_doc(doc, overwrite=False)",
			'"changes": changes',
			'"has_changes": bool(changes)',
		):
			self.assertIn(contract, source)
		for forbidden in (
			"frappe.db.set_value",
			"frappe.db.commit",
			"ignore_permissions",
			".save(",
			".insert(",
			".submit(",
			".cancel(",
		):
			self.assertNotIn(forbidden, source)

	def test_full_form_helper_is_loaded_once_and_scoped_to_new_transaction_forms(self):
		hooks = self.read("hooks.py")
		source = self.read("public/js/new_document_operating_defaults.js")
		self.assertEqual(hooks.count('"/assets/retailedge/js/new_document_operating_defaults.js"'), 1)
		for doctype in (
			"Sales Order",
			"Delivery Note",
			"Sales Invoice",
			"POS Invoice",
			"Purchase Order",
			"Purchase Receipt",
			"Purchase Invoice",
			"Material Request",
			"Stock Entry",
		):
			self.assertIn(f'"{doctype}"', source)
		self.assertIn("frm.is_new?.()", source)
		self.assertIn("Number(frm.doc?.docstatus || 0) === 0", source)
		self.assertIn("if (state.loading || state.loaded) return;", source)
		self.assertIn('method: "retailedge.new_document_defaults.get_new_document_operating_defaults"', source)

	def test_full_form_helper_preserves_user_edits_and_applies_scalar_defaults_only(self):
		source = self.read("public/js/new_document_operating_defaults.js")
		self.assertIn("SAFE_SCALAR_FIELDS", source)
		self.assertIn("if (!isEmpty(frm.doc?.[fieldname])) continue;", source)
		self.assertGreaterEqual(source.count("if (!isEmpty(frm.doc?.[fieldname])) continue;"), 2)
		self.assertIn('if (isEmpty(proposed) || Array.isArray(proposed) || typeof proposed === "object") continue;', source)
		self.assertIn("await frm.set_value(fieldname, proposed);", source)
		self.assertNotIn("frm.doc.items =", source)
		self.assertNotIn("frappe.model.set_value", source)
		self.assertNotIn("frm.save", source)

	def test_company_change_clears_only_owned_defaults_and_discards_stale_responses(self):
		source = self.read("public/js/new_document_operating_defaults.js")
		for contract in (
			"COMPANY_DEPENDENT_FIELDS",
			"autoApplied: {}",
			"generation: 0",
			"pendingRefresh: false",
			"state.autoApplied[fieldname] = proposed",
			"frm.doc?.[fieldname] === priorDefault",
			"delete state.autoApplied[fieldname]",
			"generation !== state.generation",
			"state.pendingRefresh = true",
			"async function handleCompanyChange(frm)",
			"state.generation += 1",
			"company(frm)",
		):
			self.assertIn(contract, source)

	def test_no_accounting_or_stock_posting_side_effects_added(self):
		source = self.read("branch_defaults_application.py")
		for forbidden in (
			"frappe.db.commit",
			"ignore_permissions",
			"make_gl_entries",
			"stock_ledger",
			"submit()",
			"cancel()",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
