from __future__ import annotations

from retailedge.patches.backfill_cashier_expense_posting_readiness import execute as refresh_posting_readiness


def execute():
	"""Heal stale persisted readiness after lifecycle-transition synchronization is introduced."""
	refresh_posting_readiness()
