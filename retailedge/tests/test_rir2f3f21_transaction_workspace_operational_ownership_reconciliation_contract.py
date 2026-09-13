from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/transaction_workspace/TransactionWorkspace.vue"
DOC = ROOT.parent / "docs/rir2f3f21_transaction_workspace_operational_ownership_reconciliation.md"


def _source() -> str:
	return COMPONENT.read_text(encoding="utf-8")


def test_transaction_workspace_consumes_final_native_desk_capability():
	source = _source()
	assert "canUseNativeDesk: false" in source
	assert "this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);" in source
	assert ':nativeFallbackEnabled="canUseNativeDesk"' in source
	assert 'if ((item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk) return;' in source
	assert "if (!this.canUseNativeDesk || !doctype) return;" in source


def test_existing_edgesuite_owners_replace_stale_native_transaction_handoffs():
	source = _source()
	assert 'if (["Sales Order", "Delivery Note"].includes(action?.doctype)) return "professional-selling";' in source
	assert 'if (["Purchase Order", "Purchase Receipt"].includes(action?.doctype)) return "professional-purchasing";' in source
	assert 'if (action?.doctype === "Purchase Invoice") return "purchase-register";' in source
	assert "const owner = this.createOwnerPage(action);" in source
	assert "const owner = this.readOwnerPage(action);" in source
	assert "if (owner && this.hasPageTarget(owner))" in source
	assert 'return "Open Selling";' in source
	assert 'return "Open Purchasing";' in source


def test_native_compatibility_fallback_requires_final_capability():
	source = _source()
	assert 'v-if="canUseNativeDesk && pos?.opening_doctype"' in source
	assert 'v-if="canUseNativeDesk && pos?.closing_doctype"' in source
	assert "if (!this.canUseNativeDesk) return;" in source
	assert 'return "Advanced: Create in ERPNext";' in source
	assert 'return "Advanced: View in ERPNext";' in source


def test_stock_history_parity_hold_is_not_bypassed():
	source = _source()
	assert 'GUIDED_DOCTYPES = new Set(["Sales Invoice", "Purchase Invoice", "Stock Entry"])' in source
	assert 'if (action.doctype === "Stock Entry")' in source
	assert "this.simpleStockTransferOpen = true;" in source
	assert '"stock-movement-history"' not in source


def test_slice_is_frontend_ownership_only():
	doc = DOC.read_text(encoding="utf-8")
	assert "No backend transaction engine is added" in doc
	assert "Stock Movement History parity hold" in doc
	assert "ERPNext remains" in doc
