from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
EDGE_NAV = APP_ROOT / "edgesuite_ui.py"
WORKSPACE_HOME = APP_ROOT / "workspace_home.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_edgesuite_customers_menu_uses_customer_receivables_as_primary_and_keeps_detailed_erpnext_report():
	source = _read(EDGE_NAV)
	assert '{"label": "Customer Receivables", "target_type": "Page", "target": "customer-receivables"' in source
	assert '{"label": "Accounts Receivable (Detailed)", "target_type": "Report", "target": "Accounts Receivable"' in source
	assert '{"label": "Receivables", "target_type": "Report", "target": "Accounts Receivable"' not in source


def test_native_workspace_generator_matches_receivables_primary_and_detailed_routes():
	source = _read(WORKSPACE_HOME)
	assert 'WorkspaceHomeItem("Customer Receivables", "Page", "customer-receivables", "Customers"' in source
	assert 'WorkspaceHomeItem("Accounts Receivable (Detailed)", "Report", "Accounts Receivable", "Customers"' in source
	assert 'WorkspaceHomeItem("Receivables", "Report", "Accounts Receivable", "Customers"' not in source


def test_stock_movement_remains_qa_gated_during_receivables_alignment():
	edge_source = _read(EDGE_NAV)
	workspace_source = _read(WORKSPACE_HOME)
	assert '{"label": "Stock Movement History", "target_type": "Report", "target": "RetailEdge Stock Movement History"' in edge_source
	assert 'WorkspaceHomeItem("Stock Movement History", "Report", "RetailEdge Stock Movement History"' in workspace_source
