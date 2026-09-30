from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
EDGE_NAV = APP_ROOT / "edgesuite_ui.py"
WORKSPACE_HOME = APP_ROOT / "workspace_home.py"
REPORT_CENTRE = APP_ROOT / "report_center.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_base_registry_keeps_receivables_authority_while_final_navigation_centralises_detail_reports():
	source = _read(EDGE_NAV)
	report_source = _read(REPORT_CENTRE)
	assert '{"label": "Customer Receivables", "target_type": "Page", "target": "customer-receivables"' in source
	assert '{"label": "Accounts Receivable (Detailed)", "target_type": "Report", "target": "Accounts Receivable"' in source
	assert '"target": "Accounts Receivable"' in report_source


def test_native_workspace_keeps_actionable_receivables_and_routes_detailed_reporting_to_reports_centre():
	source = _read(WORKSPACE_HOME)
	assert 'WorkspaceHomeItem("Customer Receivables", "Page", "customer-receivables", "Customers"' in source
	assert 'WorkspaceHomeItem("Accounts Receivable (Detailed)", "Report", "Accounts Receivable", "Customers"' not in source
	assert 'WorkspaceHomeItem("Reports Centre", "Page", "reports-centre", "Reports"' in source


def test_stock_movement_detail_is_centralised_in_reports_centre():
	edge_source = _read(EDGE_NAV)
	workspace_source = _read(WORKSPACE_HOME)
	report_source = _read(REPORT_CENTRE)
	assert '{"label": "Stock Movement History", "target_type": "Report", "target": "RetailEdge Stock Movement History"' in edge_source
	assert 'WorkspaceHomeItem("Stock Movement History", "Report", "RetailEdge Stock Movement History"' not in workspace_source
	assert '"target": "stock-movement-history"' in report_source
