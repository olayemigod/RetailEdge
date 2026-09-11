from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import patch

import frappe
import pytest

from retailedge import guided_entry_context as cascade
from retailedge import professional_selling as selling


def _restricted(branches):
	return {
		"company": "Demo Company",
		"restricted": True,
		"allowed_branches": list(branches),
		"source": "branch_assignment",
	}


def test_shared_resolver_restricted_zero_rejects_unmapped_warehouse():
	with (
		patch.object(cascade, "_assert_read_permission"),
		patch.object(cascade.frappe.db, "get_value", return_value="Demo Company"),
		patch.object(cascade, "resolve_branch_from_warehouse", return_value={"branch": ""}),
		patch.object(cascade, "get_branch_profile", return_value=None),
		patch.object(cascade, "get_operational_branch_scope", return_value=_restricted([])),
		pytest.raises(frappe.PermissionError),
	):
		cascade.resolve_branch_warehouse_selection(
			company="Demo Company",
			warehouse="Loose Warehouse - DC",
		)


def test_shared_resolver_restricted_single_requires_profile_for_unmapped_warehouse():
	profile = SimpleNamespace(branch="Lagos")
	with (
		patch.object(cascade, "_assert_read_permission"),
		patch.object(cascade.frappe.db, "get_value", return_value="Demo Company"),
		patch.object(cascade, "resolve_branch_from_warehouse", return_value={"branch": ""}),
		patch.object(cascade, "get_operational_branch_scope", return_value=_restricted(["Lagos"])),
		patch.object(
			cascade,
			"resolve_operational_branch",
			return_value={**_restricted(["Lagos"]), "branch": "Lagos"},
		) as resolve_branch,
		patch.object(cascade, "get_branch_profile", return_value=profile) as get_profile,
	):
		result = cascade.resolve_branch_warehouse_selection(
			company="Demo Company",
			warehouse="Loose Warehouse - DC",
		)

	resolve_branch.assert_called_once_with("Demo Company", "", user=frappe.session.user)
	get_profile.assert_called_with(
		company="Demo Company",
		branch="Lagos",
		user=frappe.session.user,
		warehouse="Loose Warehouse - DC",
		active_only=True,
	)
	assert result["branch"] == "Lagos"
	assert result["warehouse"] == "Loose Warehouse - DC"


def test_shared_resolver_unrestricted_keeps_company_wide_unmapped_warehouse():
	with (
		patch.object(cascade, "_assert_read_permission"),
		patch.object(cascade.frappe.db, "get_value", return_value="Demo Company"),
		patch.object(cascade, "resolve_branch_from_warehouse", return_value={"branch": ""}),
		patch.object(cascade, "get_branch_profile", return_value=None),
		patch.object(
			cascade,
			"get_operational_branch_scope",
			return_value={
				"company": "Demo Company",
				"restricted": False,
				"allowed_branches": [],
				"source": "global",
			},
		),
	):
		result = cascade.resolve_branch_warehouse_selection(
			company="Demo Company",
			warehouse="Company Warehouse - DC",
		)

	assert result["branch"] == ""
	assert result["warehouse"] == "Company Warehouse - DC"


def test_professional_selling_restricted_zero_warehouse_search_fails_closed():
	with (
		patch.object(selling, "get_operational_branch_scope", return_value=_restricted([])),
		patch.object(selling, "has_field", return_value=True),
	):
		filters = selling._warehouse_filters("Demo Company", "")

	assert filters["company"] == "Demo Company"
	assert filters["name"] == "__never__"


def test_professional_selling_restricted_multi_waits_for_branch_before_warehouse_search():
	with (
		patch.object(
			selling,
			"get_operational_branch_scope",
			return_value=_restricted(["Lagos", "Abuja"]),
		),
		patch.object(selling, "has_field", return_value=True),
	):
		assert selling._warehouse_filters("Demo Company", "") is None


def test_professional_selling_warehouse_branch_is_revalidated_server_side():
	with (
		patch.object(selling, "get_operating_context", return_value={}),
		patch.object(selling, "_assert_read"),
		patch.object(selling, "_field_exists", return_value=True),
		patch.object(selling.frappe.db, "get_value", return_value="Demo Company"),
		patch.object(selling, "resolve_branch_from_warehouse", return_value={"branch": "Abuja"}),
		patch.object(
			selling,
			"resolve_operational_branch",
			side_effect=frappe.PermissionError("not permitted"),
		) as resolve_branch,
		pytest.raises(frappe.PermissionError),
	):
		selling._validate_context(
			{
				"company": "Demo Company",
				"branch": "",
				"warehouse": "Abuja Warehouse - DC",
			}
		)

	resolve_branch.assert_called_with("Demo Company", "Abuja", user=frappe.session.user)


def test_professional_selling_restricted_blank_write_uses_operational_resolver():
	with (
		patch.object(selling, "get_operating_context", return_value={}),
		patch.object(selling, "_assert_read"),
		patch.object(
			selling,
			"resolve_operational_branch",
			return_value={**_restricted(["Lagos"]), "branch": "Lagos"},
		) as resolve_branch,
	):
		company, branch, warehouse = selling._validate_context(
			{"company": "Demo Company", "branch": "", "warehouse": ""}
		)

	assert (company, branch, warehouse) == ("Demo Company", "Lagos", "")
	resolve_branch.assert_called_once_with("Demo Company", "", user=frappe.session.user)


def test_professional_selling_recent_scope_restricted_zero_never_becomes_company_wide():
	with (
		patch.object(selling, "get_operational_branch_scope", return_value=_restricted([])),
		patch.object(selling.frappe, "get_meta") as get_meta,
	):
		get_meta.return_value.has_field.side_effect = lambda field: field in {"company", "branch"}
		filters = selling._operating_document_filters(
			"Sales Order",
			company="Demo Company",
			branch="",
		)

	assert filters["company"] == "Demo Company"
	assert filters["name"] == "__never__"


def test_backend_cascade_uses_explicit_operational_scope_contract():
	for module in (cascade, selling):
		source = inspect.getsource(module)
		assert "get_operational_branch_scope" in source
		assert "resolve_operational_branch" in source


def test_frontend_branch_change_invalidates_dependent_warehouse_and_pricing():
	from pathlib import Path

	root = Path(__file__).resolve().parents[1]
	paths = [
		root / "public/js/retailedge_business_hub/SimpleSalesInvoiceDialog.vue",
		root / "public/js/retailedge_business_hub/SimplePurchaseInvoiceDialog.vue",
		root / "public/js/professional_selling/ProfessionalQuotationDialog.vue",
		root / "public/js/professional_selling/ProfessionalSalesOrderDialog.vue",
		root / "public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue",
	]
	for path in paths:
		source = path.read_text(encoding="utf-8")
		start = source.index("setBranch(next)")
		end = source.index("async setWarehouse(next)", start)
		method = source[start:end]
		assert 'this.values.warehouse = "";' in method
		assert 'rate: ""' in method
		assert method.index('this.values.warehouse = "";') < method.index('if (!branch')
