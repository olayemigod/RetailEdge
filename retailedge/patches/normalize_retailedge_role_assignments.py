from __future__ import annotations

from retailedge.setup_roles import ensure_retailedge_roles


def execute():
	# Idempotent: creates missing role records and adds canonical assignments for
	# alias-only users. Compatibility aliases are deliberately retained.
	ensure_retailedge_roles(migrate_alias_assignments=True)
