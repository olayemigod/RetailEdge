from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
	return (ROOT / path).read_text(encoding="utf-8")


def test_saved_draft_item_removal_is_exposed_without_weakening_submit_boundaries():
	helper = _read("professional_draft_items.py")
	selling_service = _read("standard_selling_completion.py")
	delivery_service = _read("standard_delivery_completion.py")
	selling_dialog = _read("public/js/professional_selling/StandardSellingCompletionDialog.vue")
	delivery_dialog = _read("public/js/professional_selling/StandardDeliveryCompletionDialog.vue")

	assert "doc.remove(row)" in helper
	assert "cannot be removed here" not in helper
	assert "Existing item identity cannot be replaced here." in helper

	assert "Only draft documents can be edited here." in selling_service
	assert "Only draft Delivery Notes can be edited here." in delivery_service
	assert 'frappe.has_permission(doctype, "write", doc=doc)' in selling_service
	assert 'frappe.has_permission(DELIVERY_NOTE_DOCTYPE, "write", doc=doc)' in delivery_service

	for dialog in (selling_dialog, delivery_dialog):
		assert "removeDraftItem(index)" in dialog
		assert "draftItems.length !== original.length" in dialog
		assert 'title="Remove item"' in dialog
		assert "draftItems.length <= 1" in dialog
		assert "items: [...this.draftItems, ...additions]" in dialog
