from __future__ import annotations

from pathlib import Path

import frappe
import pytest

from retailedge import coreedge_quota_operations_center as center


APP_ROOT = Path(__file__).resolve().parents[1]


def _operation_row(
	*,
	name: str = "quota-op-001",
	status: str = "Pending Finalize",
	company: str = "RetailEdge Consulting",
	branch: str = "Ketu",
):
	return frappe._dict(
		name=name,
		status=status,
		source_doctype="Sales Invoice",
		source_name="SINV-0001",
		company=company,
		branch=branch,
		entitlement_key="SALES_TRANSACTIONS",
		units=1,
		reservation_reference="CEUR-001",
		reservation_expires_on=None,
		warning=0,
		reason_code="WITHIN_LIMIT",
		remote_message="",
		reserved_on="2026-10-01 10:00:00",
		finalized_on=None,
		last_attempt_on=None,
		attempt_count=0,
		last_error="",
		creation="2026-10-01 10:00:00",
	)


def _allow_center(monkeypatch, *, restricted=True, allowed=None):
	allowed = allowed if allowed is not None else ["Ketu"]
	monkeypatch.setattr(center, "_require_read_access", lambda: None)
	monkeypatch.setattr(center, "_user_can_retry", lambda: True)
	monkeypatch.setattr(center, "_can_read_source", lambda *_args: False)
	monkeypatch.setattr(
		center,
		"get_allowed_operating_contexts",
		lambda company="": {
			"companies": ["RetailEdge Consulting"],
			"selected_company": company or "RetailEdge Consulting",
		},
	)
	monkeypatch.setattr(
		center,
		"get_operational_branch_scope",
		lambda company: {
			"company": company,
			"restricted": restricted,
			"allowed_branches": list(allowed),
			"source": "test",
		},
	)


def test_blank_branch_filter_preserves_restricted_branch_scope(monkeypatch):
	_allow_center(monkeypatch, restricted=True, allowed=["Ketu", "Lekki"])
	captured = {}

	def fake_get_list(doctype, **kwargs):
		captured["doctype"] = doctype
		captured.update(kwargs)
		return [_operation_row()]

	monkeypatch.setattr(frappe, "get_list", fake_get_list)

	result = center.get_quota_operations(
		{"company": "RetailEdge Consulting", "status": "Open"}
	)

	assert captured["doctype"] == center.OPERATION_DOCTYPE
	assert captured["filters"]["company"] == "RetailEdge Consulting"
	assert captured["filters"]["branch"] == ["in", ["Ketu", "Lekki"]]
	assert captured["filters"]["status"] == [
		"in",
		["Pending Finalize", "Needs Review"],
	]
	assert result["rows"][0]["action"] == "Retry Finalization"
	assert result["metadata"]["branch_scope_enforced"] is True


def test_global_scope_does_not_invent_branch_filter(monkeypatch):
	_allow_center(monkeypatch, restricted=False, allowed=[])
	captured = {}

	def fake_get_list(_doctype, **kwargs):
		captured.update(kwargs)
		return [_operation_row(branch="")]

	monkeypatch.setattr(frappe, "get_list", fake_get_list)
	center.get_quota_operations(
		{"company": "RetailEdge Consulting", "status": "All"}
	)

	assert "branch" not in captured["filters"]
	assert "status" not in captured["filters"]


def test_explicit_branch_is_server_validated(monkeypatch):
	_allow_center(monkeypatch, restricted=False, allowed=[])
	validated = []
	monkeypatch.setattr(
		center,
		"validate_operating_branch",
		lambda **kwargs: validated.append(kwargs) or {"allowed": True},
	)
	monkeypatch.setattr(
		frappe,
		"get_list",
		lambda _doctype, **_kwargs: [_operation_row(branch="Ketu")],
	)

	center.get_quota_operations(
		{
			"company": "RetailEdge Consulting",
			"branch": "Ketu",
			"status": "Open",
		}
	)

	assert validated == [
		{
			"company": "RetailEdge Consulting",
			"branch": "Ketu",
			"throw": True,
		}
	]


def test_bounded_dataset_requires_narrower_filters(monkeypatch):
	_allow_center(monkeypatch)
	monkeypatch.setattr(
		frappe,
		"get_list",
		lambda _doctype, **_kwargs: [
			_operation_row(name=f"quota-op-{index}")
			for index in range(center.MAX_DATASET_ROWS + 1)
		],
	)

	with pytest.raises(frappe.ValidationError):
		center.get_quota_operations(
			{"company": "RetailEdge Consulting", "status": "Open"}
		)


def test_retry_queues_only_pending_finalize_after_scope_check(monkeypatch):
	monkeypatch.setattr(center, "_require_post", lambda: None)
	monkeypatch.setattr(center, "_require_retry_access", lambda: None)
	monkeypatch.setattr(
		frappe,
		"get_list",
		lambda _doctype, **_kwargs: [
			frappe._dict(
				name="quota-op-001",
				status="Pending Finalize",
				company="RetailEdge Consulting",
				branch="Ketu",
				source_doctype="Sales Invoice",
				source_name="SINV-0001",
			)
		],
	)
	scoped = []
	monkeypatch.setattr(center, "_assert_row_scope", lambda row: scoped.append(row.name))
	queued = []
	monkeypatch.setattr(
		center,
		"queue_sales_quota_finalization",
		lambda name: queued.append(name) or True,
	)

	result = center.retry_quota_operation("quota-op-001")

	assert scoped == ["quota-op-001"]
	assert queued == ["quota-op-001"]
	assert result["queued"] is True


def test_needs_review_is_not_retryable_from_browser(monkeypatch):
	monkeypatch.setattr(center, "_require_post", lambda: None)
	monkeypatch.setattr(center, "_require_retry_access", lambda: None)
	monkeypatch.setattr(
		frappe,
		"get_list",
		lambda _doctype, **_kwargs: [
			frappe._dict(
				name="quota-op-review",
				status="Needs Review",
				company="RetailEdge Consulting",
				branch="Ketu",
				source_doctype="Sales Invoice",
				source_name="SINV-0002",
			)
		],
	)
	monkeypatch.setattr(center, "_assert_row_scope", lambda _row: None)
	monkeypatch.setattr(
		center,
		"queue_sales_quota_finalization",
		lambda _name: pytest.fail("Needs Review must not be queued"),
	)

	with pytest.raises(frappe.ValidationError):
		center.retry_quota_operation("quota-op-review")


def test_backend_is_permission_aware_and_does_not_mutate_accounting():
	source = (APP_ROOT / "coreedge_quota_operations_center.py").read_text(
		encoding="utf-8"
	)
	assert "frappe.get_list(" in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit()" not in source
	assert "_require_post()" in source
	assert "queue_sales_quota_finalization" in source
	assert "Sales Invoice" in source
	assert "POS Invoice" in source


def test_edgesuite_page_keeps_needs_review_read_only():
	component = (
		APP_ROOT
		/ "public"
		/ "js"
		/ "quota_operations"
		/ "QuotaOperationsCenter.vue"
	).read_text(encoding="utf-8")
	bundle = (APP_ROOT / "public" / "js" / "quota_operations.bundle.js").read_text(
		encoding="utf-8"
	)
	page_js = (
		APP_ROOT
		/ "retailedge"
		/ "page"
		/ "quota_operations"
		/ "quota_operations.js"
	).read_text(encoding="utf-8")

	assert "EdgeReportShell" in component
	assert "Pending Finalize may be retried" in component
	assert "Needs Review is intentionally read-only" in component
	assert "retry_quota_operation" in component
	assert "finalize_sales_quota_operation" not in component
	assert "mountQuotaOperationsPage" in bundle
	assert 'const PAGE_ROUTE = "quota-operations"' in page_js
	assert "edgeui.bundle.js" in page_js


def test_quota_operations_navigation_is_review_only_and_does_not_change_existing_roles():
	edgesuite = (APP_ROOT / "edgesuite_ui.py").read_text(encoding="utf-8")
	master = (APP_ROOT / "master_experience.py").read_text(encoding="utf-8")

	assert '"label": "Quota Operations"' in edgesuite
	assert '"target": "quota-operations"' in edgesuite
	assert '"quota-operations"' in master
	assert '"RetailEdge Branch Manager"' in edgesuite
	assert '"RetailEdgeBranchManager"' in edgesuite
	quota_block = edgesuite.split("QUOTA_OPERATIONS_ROLES = {", 1)[1].split("}", 1)[0]
	assert '"RetailEdge Branch Manager"' not in quota_block
	assert '"RetailEdgeBranchManager"' not in quota_block


def test_page_roles_match_safe_quota_operation_read_roles():
	page_json = (
		APP_ROOT
		/ "retailedge"
		/ "page"
		/ "quota_operations"
		/ "quota_operations.json"
	).read_text(encoding="utf-8")

	assert '"System Manager"' in page_json
	assert '"RetailEdge Manager"' in page_json
	assert '"RetailEdge Auditor"' in page_json
	assert '"RetailEdge Branch Manager"' not in page_json
	assert '"RetailEdgeBranchManager"' not in page_json
