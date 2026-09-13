from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import cash_shift_verification as shift


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "public/js/cash_shift_verification/CashShiftVerificationReport.vue"


def test_cashier_search_receives_selected_pos_profile_context():
	read_scope = {"company": "Scope Co", "branch": "Branch A"}
	with (
		patch.object(
			shift,
			"resolve_cash_shift_verification_read_scope",
			return_value=read_scope,
		),
		patch.object(
			shift,
			"_search_scoped_cashiers",
			return_value=[{"value": "cashier@example.com", "label": "Cashier"}],
		) as search,
	):
		result = shift.search_cash_shift_verification_options(
			"cashier",
			"cash",
			company="Scope Co",
			branch="Branch A",
			pos_profile="POS-A",
		)

	search.assert_called_once_with(
		txt="cash",
		read_scope=read_scope,
		pos_profile="POS-A",
	)
	assert result[0]["value"] == "cashier@example.com"


def test_invalid_selected_pos_profile_returns_no_cashier_options():
	read_scope = {"company": "Scope Co", "branch": "Branch A"}
	with (
		patch.object(
			shift,
			"_scoped_audit_values",
			return_value=set(),
		) as scoped_values,
		patch.object(shift.frappe, "get_list") as get_list,
	):
		result = shift._search_scoped_cashiers(
			txt="cash",
			read_scope=read_scope,
			pos_profile="POS-X",
		)

	assert result == []
	get_list.assert_not_called()
	scoped_values.assert_called_once_with(
		fieldname="pos_profile",
		candidates=["POS-X"],
		read_scope=read_scope,
	)


def test_selected_pos_profile_filters_cashier_audit_evidence():
	read_scope = {"company": "Scope Co", "branch": "Branch A"}
	candidates = [
		frappe._dict(name="cashier1@example.com", full_name="Cashier One"),
		frappe._dict(name="cashier2@example.com", full_name="Cashier Two"),
	]
	with (
		patch.object(
			shift,
			"_scoped_audit_values",
			side_effect=[
				{"POS-A"},
				{"cashier1@example.com"},
			],
		) as scoped_values,
		patch.object(shift.frappe, "get_list", return_value=candidates),
	):
		result = shift._search_scoped_cashiers(
			txt="cash",
			read_scope=read_scope,
			pos_profile="POS-A",
		)

	assert result == [
		{
			"value": "cashier1@example.com",
			"label": "Cashier One",
			"description": "cashier1@example.com",
		}
	]
	assert scoped_values.call_args_list[1].kwargs["extra_filters"] == {"pos_profile": "POS-A"}


def test_active_page_passes_pos_profile_and_clears_cashier_on_profile_change():
	source = VUE.read_text(encoding="utf-8")

	assert "pos_profile: this.filters.pos_profile" in source
	assert '@select="onPosProfileSelected"' in source
	assert '@clear="clearPosProfile"' in source

	select_start = source.index("onPosProfileSelected(option)")
	select_block = source[select_start : select_start + 350]
	assert "this.clearCashier();" in select_block

	clear_start = source.index("clearPosProfile()")
	clear_block = source[clear_start : clear_start + 250]
	assert "this.clearCashier();" in clear_block


def test_g2g25_does_not_add_permission_or_transaction_bypass():
	source = Path(shift.__file__).read_text(encoding="utf-8")
	assert "ignore_permissions=True" not in source
	assert "frappe.db.commit()" not in source
