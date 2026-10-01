from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

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


class TestCoreEdgeQuotaOperationsCenter(FrappeTestCase):
	def _allow_center(
		self,
		stack: ExitStack,
		*,
		restricted: bool = True,
		allowed: list[str] | None = None,
	) -> None:
		allowed = allowed if allowed is not None else ["Ketu"]
		stack.enter_context(patch.object(center, "_require_read_access", lambda: None))
		stack.enter_context(patch.object(center, "_user_can_retry", lambda: True))
		stack.enter_context(patch.object(center, "_can_read_source", lambda *_args: False))
		stack.enter_context(
			patch.object(
				center,
				"get_allowed_operating_contexts",
				lambda company="": {
					"companies": ["RetailEdge Consulting"],
					"selected_company": company or "RetailEdge Consulting",
				},
			)
		)
		stack.enter_context(
			patch.object(
				center,
				"get_operational_branch_scope",
				lambda company: {
					"company": company,
					"restricted": restricted,
					"allowed_branches": list(allowed),
					"source": "test",
				},
			)
		)

	def test_blank_branch_filter_preserves_restricted_branch_scope(self):
		captured = {}

		def fake_get_list(doctype, **kwargs):
			captured["doctype"] = doctype
			captured.update(kwargs)
			return [_operation_row()]

		with ExitStack() as stack:
			self._allow_center(
				stack,
				restricted=True,
				allowed=["Ketu", "Lekki"],
			)
			stack.enter_context(patch.object(frappe, "get_list", fake_get_list))
			result = center.get_quota_operations(
				{"company": "RetailEdge Consulting", "status": "Open"}
			)

		self.assertEqual(captured["doctype"], center.OPERATION_DOCTYPE)
		self.assertEqual(captured["filters"]["company"], "RetailEdge Consulting")
		self.assertEqual(captured["filters"]["branch"], ["in", ["Ketu", "Lekki"]])
		self.assertEqual(
			captured["filters"]["status"],
			["in", ["Pending Finalize", "Needs Review"]],
		)
		self.assertEqual(result["rows"][0]["action"], "Retry Finalization")
		self.assertTrue(result["metadata"]["branch_scope_enforced"])

	def test_global_scope_does_not_invent_branch_filter(self):
		captured = {}

		def fake_get_list(_doctype, **kwargs):
			captured.update(kwargs)
			return [_operation_row(branch="")]

		with ExitStack() as stack:
			self._allow_center(stack, restricted=False, allowed=[])
			stack.enter_context(patch.object(frappe, "get_list", fake_get_list))
			center.get_quota_operations(
				{"company": "RetailEdge Consulting", "status": "All"}
			)

		self.assertNotIn("branch", captured["filters"])
		self.assertNotIn("status", captured["filters"])

	def test_explicit_branch_is_server_validated(self):
		validated = []

		with ExitStack() as stack:
			self._allow_center(stack, restricted=False, allowed=[])
			stack.enter_context(
				patch.object(
					center,
					"validate_operating_branch",
					lambda **kwargs: validated.append(kwargs) or {"allowed": True},
				)
			)
			stack.enter_context(
				patch.object(
					frappe,
					"get_list",
					lambda _doctype, **_kwargs: [_operation_row(branch="Ketu")],
				)
			)
			center.get_quota_operations(
				{
					"company": "RetailEdge Consulting",
					"branch": "Ketu",
					"status": "Open",
				}
			)

		self.assertEqual(
			validated,
			[
				{
					"company": "RetailEdge Consulting",
					"branch": "Ketu",
					"throw": True,
				}
			],
		)

	def test_bounded_dataset_requires_narrower_filters(self):
		with ExitStack() as stack:
			self._allow_center(stack)
			stack.enter_context(
				patch.object(
					frappe,
					"get_list",
					lambda _doctype, **_kwargs: [
						_operation_row(name=f"quota-op-{index}")
						for index in range(center.MAX_DATASET_ROWS + 1)
					],
				)
			)
			with self.assertRaises(frappe.ValidationError):
				center.get_quota_operations(
					{"company": "RetailEdge Consulting", "status": "Open"}
				)

	def test_retry_queues_only_pending_finalize_after_scope_check(self):
		scoped = []
		queued = []
		with ExitStack() as stack:
			stack.enter_context(patch.object(center, "_require_post", lambda: None))
			stack.enter_context(patch.object(center, "_require_retry_access", lambda: None))
			stack.enter_context(
				patch.object(
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
			)
			stack.enter_context(
				patch.object(
					center,
					"_assert_row_scope",
					lambda row: scoped.append(row.name),
				)
			)
			stack.enter_context(
				patch.object(
					center,
					"queue_sales_quota_finalization",
					lambda name: queued.append(name) or True,
				)
			)
			result = center.retry_quota_operation("quota-op-001")

		self.assertEqual(scoped, ["quota-op-001"])
		self.assertEqual(queued, ["quota-op-001"])
		self.assertTrue(result["queued"])

	def test_needs_review_is_not_retryable_from_browser(self):
		def should_not_queue(_name):
			raise AssertionError("Needs Review must not be queued")

		with ExitStack() as stack:
			stack.enter_context(patch.object(center, "_require_post", lambda: None))
			stack.enter_context(patch.object(center, "_require_retry_access", lambda: None))
			stack.enter_context(
				patch.object(
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
			)
			stack.enter_context(
				patch.object(center, "_assert_row_scope", lambda _row: None)
			)
			stack.enter_context(
				patch.object(
					center,
					"queue_sales_quota_finalization",
					should_not_queue,
				)
			)
			with self.assertRaises(frappe.ValidationError):
				center.retry_quota_operation("quota-op-review")

	def test_backend_is_permission_aware_and_does_not_mutate_accounting(self):
		source = (APP_ROOT / "coreedge_quota_operations_center.py").read_text(
			encoding="utf-8"
		)
		self.assertIn("frappe.get_list(", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit()", source)
		self.assertIn("_require_post()", source)
		self.assertIn("queue_sales_quota_finalization", source)
		self.assertIn("Sales Invoice", source)
		self.assertIn("POS Invoice", source)

	def test_edgesuite_page_keeps_needs_review_read_only(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "quota_operations"
			/ "QuotaOperationsCenter.vue"
		).read_text(encoding="utf-8")
		bundle = (
			APP_ROOT / "public" / "js" / "quota_operations.bundle.js"
		).read_text(encoding="utf-8")
		page_js = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "quota_operations"
			/ "quota_operations.js"
		).read_text(encoding="utf-8")

		self.assertIn("EdgeReportShell", component)
		self.assertIn("Pending Finalize may be retried", component)
		self.assertIn("Needs Review is intentionally read-only", component)
		self.assertIn("retry_quota_operation", component)
		self.assertNotIn("finalize_sales_quota_operation", component)
		self.assertIn("mountQuotaOperationsPage", bundle)
		self.assertIn('const PAGE_ROUTE = "quota-operations"', page_js)
		self.assertIn("edgeui.bundle.js", page_js)

	def test_quota_operations_navigation_is_review_only_and_does_not_change_existing_roles(
		self,
	):
		edgesuite = (APP_ROOT / "edgesuite_ui.py").read_text(encoding="utf-8")
		master = (APP_ROOT / "master_experience.py").read_text(encoding="utf-8")

		self.assertIn('"label": "Quota Operations"', edgesuite)
		self.assertIn('"target": "quota-operations"', edgesuite)
		self.assertIn('"quota-operations"', master)
		self.assertIn('"RetailEdge Branch Manager"', edgesuite)
		self.assertIn('"RetailEdgeBranchManager"', edgesuite)
		quota_block = edgesuite.split("QUOTA_OPERATIONS_ROLES = {", 1)[1].split(
			"}",
			1,
		)[0]
		self.assertNotIn('"RetailEdge Branch Manager"', quota_block)
		self.assertNotIn('"RetailEdgeBranchManager"', quota_block)

	def test_page_roles_match_safe_quota_operation_read_roles(self):
		page_json = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "quota_operations"
			/ "quota_operations.json"
		).read_text(encoding="utf-8")

		self.assertIn('"System Manager"', page_json)
		self.assertIn('"RetailEdge Manager"', page_json)
		self.assertIn('"RetailEdge Auditor"', page_json)
		self.assertNotIn('"RetailEdge Branch Manager"', page_json)
		self.assertNotIn('"RetailEdgeBranchManager"', page_json)
