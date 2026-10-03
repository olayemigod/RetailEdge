from __future__ import annotations

from retailedge.patches.backfill_cashier_expense_posting_readiness import execute as refresh_posting_readiness


def execute():
	"""Re-run readiness after document-level posting-policy snapshot hardening."""
	refresh_posting_readiness()
