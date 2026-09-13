from __future__ import annotations

from retailedge.operating_context import resolve_operational_branch


def resolve_planning_branch_scope(company: str, branch: str | None = None, *, user: str | None = None) -> str:
	"""Resolve Forecasting & Planning Branch scope through the governed operational contract.

	Branch Assignment history is authoritative when present. Users without Branch
	Assignment history retain the compatibility fallback already owned by
	Operating Context. Restricted-zero access fails closed.
	"""
	resolved = resolve_operational_branch(
		company=company,
		branch=str(branch or "").strip(),
		user=user,
	)
	return str(resolved.get("branch") or "").strip()
