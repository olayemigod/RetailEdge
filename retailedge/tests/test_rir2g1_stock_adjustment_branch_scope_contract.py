from __future__ import annotations

import inspect
from unittest.mock import patch

from retailedge import guided_stock_adjustment as adjustment


def test_branch_search_restricted_zero_fails_closed():
	with (
		patch.object(adjustment, "get_operational_branch_scope", return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": [],
			"source": "branch_assignment",
		}),
		patch.object(adjustment, "has_field", return_value=True),
	):
		filters = adjustment._branch_search_filters("Demo Company", "stock@example.com")

	assert filters["company"] == "Demo Company"
	assert filters["name"] == "__never__"


def test_warehouse_search_restricted_zero_never_broadens_to_company():
	with (
		patch.object(adjustment, "get_operational_branch_scope", return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": [],
			"source": "branch_assignment",
		}),
		patch.object(adjustment, "has_field", return_value=True),
	):
		filters = adjustment._warehouse_search_filters("Demo Company", "", "stock@example.com")

	assert filters["company"] == "Demo Company"
	assert filters["name"] == "__never__"


def test_warehouse_search_restricted_multi_requires_branch_selection():
	with (
		patch.object(adjustment, "get_operational_branch_scope", return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": ["Lagos", "Ikeja"],
			"source": "branch_assignment",
		}),
		patch.object(adjustment, "has_field", return_value=True),
	):
		assert adjustment._warehouse_search_filters("Demo Company", "", "stock@example.com") is None


def test_warehouse_search_restricted_single_auto_resolves_branch():
	with (
		patch.object(adjustment, "get_operational_branch_scope", return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": ["Lagos"],
			"source": "branch_assignment",
		}),
		patch.object(adjustment, "resolve_operational_branch", return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": ["Lagos"],
			"branch": "Lagos",
		}) as resolve_branch,
		patch.object(adjustment, "has_field", return_value=True),
		patch.object(adjustment, "get_first_existing_field", return_value="branch"),
	):
		filters = adjustment._warehouse_search_filters("Demo Company", "", "stock@example.com")

	resolve_branch.assert_called_once_with("Demo Company", "", user="stock@example.com")
	assert filters["branch"] == "Lagos"


def test_explicit_branch_is_revalidated_through_operational_scope_before_warehouse_filtering():
	with (
		patch.object(adjustment, "resolve_operational_branch", return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": ["Lagos"],
			"branch": "Lagos",
		}) as resolve_branch,
		patch.object(adjustment, "has_field", return_value=True),
		patch.object(adjustment, "get_first_existing_field", return_value="branch"),
	):
		filters = adjustment._warehouse_search_filters("Demo Company", "Lagos", "stock@example.com")

	resolve_branch.assert_called_once_with("Demo Company", "Lagos", user="stock@example.com")
	assert filters["branch"] == "Lagos"


def test_guided_stock_adjustment_uses_operational_scope_not_legacy_empty_list_contract():
	source = inspect.getsource(adjustment)
	assert "get_operational_branch_scope" in source
	assert "resolve_operational_branch" in source
	assert "get_user_allowed_branches" not in source
	assert "user_has_global_branch_access" not in source
	assert "validate_user_branch_access" not in source


def test_draft_creation_resolves_branch_before_warehouse_validation_and_insert():
	source = inspect.getsource(adjustment.create_simple_stock_adjustment_draft)
	resolve_index = source.index("resolve_operational_branch")
	warehouse_index = source.index('warehouse = str(values.get("warehouse")')
	insert_index = source.index("doc.insert()")
	assert resolve_index < warehouse_index < insert_index


def test_stock_reconciliation_remains_draft_only_and_erpnext_owned():
	source = inspect.getsource(adjustment.create_simple_stock_adjustment_draft)
	assert "frappe.new_doc(STOCK_RECONCILIATION_DOCTYPE)" in source
	assert "doc.insert()" in source
	assert "doc.submit()" not in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source
