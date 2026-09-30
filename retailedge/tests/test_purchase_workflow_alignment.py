from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master_experience.py"
REGISTRY = ROOT / "edgesuite_ui.py"
RECORD_PURCHASE = ROOT / "public/js/record_purchase/RecordPurchase.vue"
QUICK_PURCHASE = ROOT / "public/js/retailedge_business_hub/SimplePurchaseInvoiceDialog.vue"
PROFESSIONAL = ROOT / "public/js/professional_purchasing/ProfessionalPurchasing.vue"
HUB = ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"


def test_purchase_operations_is_canonical_everyday_buying_entry():
    master = MASTER.read_text(encoding="utf-8")
    registry = REGISTRY.read_text(encoding="utf-8")
    assert '"label": "Purchase Operations"' in master
    assert '"target": "professional-purchasing"' in master
    assert "Purchase Order → Purchase Receipt → Purchase Invoice → Payment" in master
    assert "items.insert(0, deepcopy(existing_page or PROFESSIONAL_PURCHASING_ITEM))" in master
    assert '"label": "Purchase Operations", "target_type": "Page", "target": "professional-purchasing"' in registry


def test_direct_purchase_is_explicit_shortcut_not_standard_procurement():
    master = MASTER.read_text(encoding="utf-8")
    registry = REGISTRY.read_text(encoding="utf-8")
    quick = QUICK_PURCHASE.read_text(encoding="utf-8")
    assert '"label": "Direct Purchase"' in master
    assert "standard Purchase Order / Receipt path does not apply" in master
    assert '"key": "record-purchase", "label": "Direct Purchase"' in registry
    assert "Use Purchase Operations for the standard Purchase Order → Receipt → Invoice workflow." in registry
    assert ":title=\"'Direct Purchase'\"" in quick
    assert "For normal procurement use Purchase Operations" in quick


def test_purchase_entry_requires_business_intent_before_direct_invoice_form():
    source = RECORD_PURCHASE.read_text(encoding="utf-8")
    assert "showPurchaseIntentChooser" in source
    assert "entryIntent: \"choose\"" in source
    assert "Standard Purchase" in source
    assert "Receive &amp; Bill Now" in source
    assert "Bill Only" in source
    assert "startStandardPurchase()" in source
    assert "startDirectPurchase(true)" in source
    assert "startDirectPurchase(false)" in source
    assert 'entryIntent === \'direct\'' in source


def test_direct_stock_mode_is_explicit_and_not_a_generic_update_stock_checkbox():
    source = RECORD_PURCHASE.read_text(encoding="utf-8")
    assert 'values.update_stock = updateStock ? 1 : 0' in source
    assert '"Receive & Bill Now"' in source
    assert '"Bill Only"' in source
    assert "ERPNext will post the received stock when this Purchase Invoice is submitted." in source
    assert '<input v-model="values.update_stock" type="checkbox"' not in source


def test_standard_purchase_handoff_reuses_existing_erpnext_purchase_order_dialog():
    entry = RECORD_PURCHASE.read_text(encoding="utf-8")
    professional = PROFESSIONAL.read_text(encoding="utf-8")
    assert 'action: "new-purchase-order"' in entry
    assert 'frappe.set_route("professional-purchasing")' in entry
    assert 'if (target.action === "new-purchase-order")' in professional
    assert "this.newPurchaseOrder();" in professional
    assert "newPurchaseOrder() { dispatchEdgeSuiteEvent(OPEN_PURCHASE_ORDER_EVENT); }" in professional


def test_business_hub_distinguishes_purchase_operations_from_direct_purchase():
    source = HUB.read_text(encoding="utf-8")
    assert 'addPage("professional-purchasing", "Purchase Operations"' in source
    assert "Purchase Order → Purchase Receipt → Purchase Invoice → Payment" in source
    assert 'addPage("record-purchase", "Direct Purchase"' in source
