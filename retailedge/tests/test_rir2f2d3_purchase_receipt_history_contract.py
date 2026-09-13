from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_purchase_receipt.py"
CONTROLLER = ROOT / "retailedge" / "page" / "professional_purchasing" / "professional_purchasing.js"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchaseReceiptHistoryOverlay.vue"
BUNDLE = ROOT / "public" / "js" / "professional_purchase_receipt_history.bundle.js"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _history_function(source: str) -> str:
	return source.split("def get_professional_purchase_receipt_history", 1)[1]


def test_history_is_permission_company_and_branch_scoped_with_bounded_results():
	source = _read(BACKEND)
	history = _history_function(source)
	for contract in (
		"_assert_read(PURCHASE_RECEIPT_DOCTYPE)",
		"_resolve_scope(company, branch)",
		"_branch_scoped_filters(",
		'filters.update({"docstatus": 1, "is_return": 0})',
		"frappe.get_list(",
		"MAX_RECEIPT_HISTORY = 100",
		"min(cint(limit) or 50, MAX_RECEIPT_HISTORY)",
	):
		assert contract in source or contract in history
	assert 'filters["supplier"] = supplier' in history
	assert '_assert_read("Supplier", supplier)' in history


def test_child_purchase_order_references_are_limited_to_permission_scoped_receipt_parents():
	source = _read(BACKEND)
	history = _history_function(source)
	assert 'names = [str(row.get("name") or "") for row in rows if row.get("name")]' in history
	assert 'filters={"parent": ["in", names]}' in history
	assert 'fields=["parent", "purchase_order"]' in history
	assert '"purchase_orders": purchase_orders.get' in history


def test_receipt_history_button_is_edgesuite_owned_and_raw_label_is_capture_safe():
	controller = _read(CONTROLLER)
	assert 'const RECEIPT_HISTORY_TRIGGER_LABEL = "Receipt History"' in controller
	assert "OPEN_PURCHASE_RECEIPT_HISTORY_EVENT" in controller
	assert 'button.setAttribute("data-retailedge-receipt-history", "true")' in controller
	assert "[PURCHASE_RECEIPTS_TRIGGER_LABEL, RECEIPT_HISTORY_TRIGGER_LABEL].includes(label)" in controller
	assert "event.preventDefault()" in controller
	assert "event.stopImmediatePropagation()" in controller
	hidden = controller.split("hiddenButtonLabels:", 1)[1].split("],", 1)[0]
	assert "PURCHASE_RECEIPTS_TRIGGER_LABEL" not in hidden


def test_history_overlay_uses_smart_cascading_filters_and_sortable_table():
	overlay = _read(OVERLAY)
	for contract in (
		"EdgeLinkField",
		"companySearch",
		"branchSearch",
		"supplierSearch",
		'searchOptions("branch", txt)',
		'searchOptions("supplier", txt)',
		'this.filters.branch = ""; this.filters.supplier = ""',
		"sortBy('name')",
		"sortBy('posting_date')",
		"sortBy('supplier_name')",
		"sortBy('total_qty')",
		"sortBy('status')",
	):
		assert contract in overlay
	assert 'limit: 50' in overlay


def test_receipt_rows_do_not_disguise_native_links_and_advanced_access_is_explicit():
	overlay = _read(OVERLAY)
	assert "<strong>{{ row.name }}</strong>" in overlay
	assert "Advanced: Open in ERPNext" in overlay
	assert "Advanced: Purchase Receipts in ERPNext" in overlay
	assert "nativeFallbackEnabled" in overlay
	assert 'frappe.set_route("Form", "Purchase Receipt", name)' in overlay
	assert 'frappe.set_route("List", "Purchase Receipt")' in overlay
	assert "@click=\"openAdvancedReceipt(row.name)\"" in overlay


def test_history_asset_is_loaded_and_mounted_without_replacing_preview_or_posting():
	controller = _read(CONTROLLER)
	bundle = _read(BUNDLE)
	backend = _read(BACKEND)
	assert 'const PURCHASE_RECEIPT_HISTORY_ASSET = "professional_purchase_receipt_history.bundle.js"' in controller
	assert "requireAsync(PURCHASE_RECEIPT_HISTORY_ASSET)" in controller
	assert "mountRetailEdgeProfessionalPurchaseReceiptHistory" in controller
	assert "mountRetailEdgeProfessionalPurchaseReceiptHistory" in bundle
	assert "get_professional_purchase_receipt_preview" in backend
	assert "submit_standard_purchase_receipt" in backend
