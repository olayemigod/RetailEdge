from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRANCH_SETUP_DIR = ROOT / "retailedge" / "doctype" / "retailedge_branch_profile"
BRANCH_SETUP_PATH = BRANCH_SETUP_DIR / "retailedge_branch_profile.json"
BRANCH_SETUP_FORM_JS = BRANCH_SETUP_DIR / "retailedge_branch_profile.js"
BRANCH_SETUP_LIST_JS = BRANCH_SETUP_DIR / "retailedge_branch_profile_list.js"
BRANCH_USER_PATH = (
	ROOT
	/ "retailedge"
	/ "doctype"
	/ "retailedge_branch_profile_user"
	/ "retailedge_branch_profile_user.json"
)


def _load(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def _fields(meta: dict) -> dict[str, dict]:
	return {field["fieldname"]: field for field in meta.get("fields", []) if field.get("fieldname")}


def test_branch_setup_preserves_internal_doctype_identity():
	meta = _load(BRANCH_SETUP_PATH)
	assert meta["name"] == "RetailEdge Branch Profile"
	assert meta["module"] == "RetailEdge"


def test_branch_setup_uses_customer_facing_branch_and_stock_location_labels():
	fields = _fields(_load(BRANCH_SETUP_PATH))

	assert fields["profile_identity_section"]["label"] == "Branch Setup"
	assert fields["profile_name"]["label"] == "Setup Name"
	assert fields["branch"]["label"] == "Branch"
	assert fields["warehouse_defaults_section"]["label"] == "Stock Location Defaults"
	assert fields["default_warehouse"]["label"] == "Default Stock Location"
	assert fields["default_source_warehouse"]["label"] == "Default Source Stock Location"
	assert fields["default_target_warehouse"]["label"] == "Default Destination Stock Location"
	assert fields["default_returns_warehouse"]["label"] == "Default Returns Stock Location"
	assert fields["operational_users_section"]["label"] == "Branch Users"


def test_branch_setup_keeps_erpnext_warehouse_as_system_of_record():
	fields = _fields(_load(BRANCH_SETUP_PATH))
	for fieldname in (
		"default_warehouse",
		"default_source_warehouse",
		"default_target_warehouse",
		"default_returns_warehouse",
	):
		assert fields[fieldname]["fieldtype"] == "Link"
		assert fields[fieldname]["options"] == "Warehouse"


def test_branch_setup_keeps_internal_child_doctype_identity():
	fields = _fields(_load(BRANCH_SETUP_PATH))
	for fieldname in ("default_cashiers", "default_managers", "default_auditors"):
		assert fields[fieldname]["options"] == "RetailEdge Branch Profile User"

	child_meta = _load(BRANCH_USER_PATH)
	assert child_meta["name"] == "RetailEdge Branch Profile User"
	child_fields = _fields(child_meta)
	assert child_fields["role_type"]["label"] == "Branch Role"
	assert child_fields["is_default"]["label"] == "Default for Role"


def test_branch_setup_form_and_list_present_customer_facing_title():
	for path in (BRANCH_SETUP_FORM_JS, BRANCH_SETUP_LIST_JS):
		source = path.read_text(encoding="utf-8")
		assert 'set_title(__("Branch Setup"))' in source
		assert 'frappe.ui.form.on("RetailEdge Branch Profile"' in source or 'frappe.listview_settings["RetailEdge Branch Profile"]' in source


def test_customer_labels_do_not_expose_internal_branch_profile_name():
	meta = _load(BRANCH_SETUP_PATH)
	labels = [field.get("label", "") for field in meta.get("fields", [])]
	assert "RetailEdge Branch Profile" not in labels
	assert "Warehouse Defaults" not in labels
	assert "Default Warehouse" not in labels
