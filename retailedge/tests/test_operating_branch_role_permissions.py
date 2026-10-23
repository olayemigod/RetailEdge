from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


def test_global_branch_authority_roles_receive_minimum_branch_master_access():
	source = (APP_ROOT / "setup_roles.py").read_text(encoding="utf-8")
	assert "from retailedge.branch_context import GLOBAL_BRANCH_ACCESS_ROLES" in source
	assert "set(ALL_RETAILEDGE_ROLE_NAMES).union(GLOBAL_BRANCH_ACCESS_ROLES)" in source
	assert 'update_permission_property("Branch", role_name, 0, "read", 1)' in source
	assert 'update_permission_property("Branch", role_name, 0, "select", 1)' in source
	assert 'frappe.clear_cache(doctype="Branch")' in source

	branch_scope = source[
		source.index("def _ensure_operational_branch_read()") :
		len(source)
	]
	for denied in ('"write", 1', '"create", 1', '"delete", 1', '"import", 1'):
		assert denied not in branch_scope
