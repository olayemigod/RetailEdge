from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import branch_performance_dashboard as dashboard

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/branch_performance_dashboard/BranchPerformanceDashboard.vue"


def test_branch_performance_option_scope_uses_governed_branch_contract():
	source = inspect.getsource(dashboard)
	assert "get_operational_branch_scope" in source
	assert "validate_operating_branch" in source
	assert "resolve_branch_from_pos_profile" in source
	assert "BRANCH_SETUP_DOCTYPE" in source
	assert "MAX_POS_PROFILE_SCAN = 60" in source
	assert "MAX_BRANCH_SETUP_SCAN = 100" in source
	assert "ignore_permissions" not in source
	assert "frappe.get_all" not in source
	assert "frappe.db.commit" not in source


def test_restricted_zero_option_scope_fails_closed():
	with patch.object(
		dashboard,
		"get_operational_branch_scope",
		return_value={"restricted": True, "allowed_branches": [], "source": "branch_assignment"},
	):
		assert dashboard._resolve_option_branch_scope("Scope Co", "") == {
			"restricted": True,
			"branches": [],
		}


def test_explicit_branch_is_revalidated_server_side():
	with (
		patch.object(
			dashboard,
			"get_operational_branch_scope",
			return_value={"restricted": True, "allowed_branches": ["Branch A"], "source": "branch_assignment"},
		),
		patch.object(dashboard, "validate_operating_branch") as validate_branch,
	):
		result = dashboard._resolve_option_branch_scope("Scope Co", "Branch A")

	assert result == {"restricted": True, "branches": ["Branch A"]}
	validate_branch.assert_called_once_with(
		company="Scope Co",
		branch="Branch A",
		user=frappe.session.user,
		throw=True,
	)


def test_pos_profile_and_cashier_searches_fail_closed_for_restricted_zero():
	scope = {"restricted": True, "branches": []}
	with patch.object(dashboard.frappe, "get_list") as get_list:
		assert dashboard._search_pos_profiles("%%", "Scope Co", scope) == []
		assert dashboard._search_cashiers("%%", "Scope Co", scope) == []
	get_list.assert_not_called()


def test_frontend_cascades_branch_performance_dependent_filters():
	source = COMPONENT.read_text(encoding="utf-8")
	assert "branch: this.filters.branch" in source
	assert "pos_profile: this.filters.pos_profile" in source
	assert 'this.filters.company = option.value; this.filters.branch = ""; this.filters.pos_profile = ""; this.filters.cashier = "";' in source
	assert 'this.filters.branch = option.value; this.filters.pos_profile = ""; this.filters.cashier = "";' in source
	assert 'clearBranch() { this.filters.branch = ""; this.filters.pos_profile = ""; this.filters.cashier = ""; }' in source
	assert 'this.filters.pos_profile = option.value; this.filters.cashier = "";' in source
	assert 'clearPosProfile() { this.filters.pos_profile = ""; this.filters.cashier = ""; }' in source
	assert 'focusBranch(branch) { this.filters.branch = branch === "Unattributed" ? "" : branch; this.filters.pos_profile = ""; this.filters.cashier = ""; this.fetchData(); }' in source
