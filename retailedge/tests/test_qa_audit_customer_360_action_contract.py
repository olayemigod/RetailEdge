from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_360 = ROOT / "public/js/customer_360/Customer360.vue"


def test_customer_360_load_action_uses_shared_edgesuite_state_action():
	source = CUSTOMER_360.read_text(encoding="utf-8")

	assert 'actionLabel="Load Customer"' in source
	assert '@action="fetchData"' in source
	assert 'title="Ready to load customer"' in source
	assert '<button class="edge-primary-button"' not in source
	assert 'customer-360-filter-action' not in source


def test_customer_360_touched_surface_uses_business_facing_copy():
	source = CUSTOMER_360.read_text(encoding="utf-8")

	assert "submitted ERPNext sales" not in source
	assert "current ERPNext outstanding balances" not in source
	assert "Required interface components are unavailable" not in source
	assert 'label: "Gross Profit"' in source
