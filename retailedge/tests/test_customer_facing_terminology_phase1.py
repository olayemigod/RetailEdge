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
SETTINGS_FORM_JS = ROOT / "retailedge" / "doctype" / "retailedge_settings" / "retailedge_settings.js"
SCOPED_LABELS_JS = ROOT / "public" / "js" / "customer_facing_labels.js"
CASHIER_EXPENSE_LIST_JS = ROOT / "public" / "js" / "retailedge_cashier_expense_list.js"
BANK_IMPORT_LIST_JS = ROOT / "public" / "js" / "payment_statement_import_list.js"
BUSINESS_HUB_PAGE_META = (
	ROOT
	/ "retailedge"
	/ "page"
	/ "retailedge_business_hub"
	/ "retailedge_business_hub.json"
)
BUSINESS_HUB_CONTROLLER = ROOT / "public" / "js" / "retailedge_business_hub_page.js"
EDGESUITE_UI_PATH = ROOT / "edgesuite_ui.py"
WORKSPACE_HOME_PATH = ROOT / "workspace_home.py"
WORKSPACE_SYNC_PATH = ROOT / "workspace_sync.py"
HOOKS_PATH = ROOT / "hooks.py"


def _load(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def _fields(meta: dict) -> dict[str, dict]:
	return {field["fieldname"]: field for field in meta.get("fields", []) if field.get("fieldname")}


def _customer_visible_metadata_offenders() -> list[str]:
	offenders: list[str] = []
	doctype_root = ROOT / "retailedge" / "doctype"
	for path in sorted(doctype_root.glob("**/*.json")):
		meta = _load(path)
		for field in meta.get("fields", []) or []:
			fieldname = field.get("fieldname") or "<unnamed>"
			for key in ("label", "description"):
				value = field.get(key)
				if isinstance(value, str) and "RetailEdge" in value:
					offenders.append(f"{path.relative_to(ROOT)}:{fieldname}:{key}={value}")
	return offenders


def _customer_facing_page_title_offenders() -> list[str]:
	offenders: list[str] = []
	page_root = ROOT / "retailedge" / "page"
	for path in sorted(page_root.glob("**/*.json")):
		meta = _load(path)
		title = meta.get("title")
		if isinstance(title, str) and title.startswith("RetailEdge "):
			offenders.append(f"{path.relative_to(ROOT)}:title={title}")
	return offenders


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


def test_settings_form_presents_customer_facing_title_without_renaming_doctype():
	source = SETTINGS_FORM_JS.read_text(encoding="utf-8")
	assert 'frappe.ui.form.on("RetailEdge Settings"' in source
	assert 'set_title(__("Settings"))' in source


def test_scoped_customer_facing_form_titles_are_not_global_dom_hacks():
	source = SCOPED_LABELS_JS.read_text(encoding="utf-8")
	assert '"RetailEdge Cashier Expense": "Cashier Expense"' in source
	assert '"RetailEdge Payment Statement Import": "Import Bank Statement"' in source
	assert '"RetailEdge Bank Transaction Match": "Bank Match Review"' in source
	assert '"RetailEdge Settings"' not in source
	assert '"RetailEdge Branch Profile"' not in source
	assert "window.cur_frm" in source
	assert "Object.entries(TITLE_BY_DOCTYPE).forEach" not in source
	assert "querySelector" not in source


def test_hooks_apply_scoped_titles_without_duplicate_handlers():
	source = HOOKS_PATH.read_text(encoding="utf-8")
	for doctype in (
		"RetailEdge Cashier Expense",
		"RetailEdge Expense Category",
		"RetailEdge Daily Sales Audit",
		"RetailEdge Payment Statement Import",
		"RetailEdge Statement Mapping Template",
		"RetailEdge Bank Transaction Match",
	):
		assert f'"{doctype}": "public/js/customer_facing_labels.js"' in source
	assert '"RetailEdge Settings": "public/js/customer_facing_labels.js"' not in source
	assert '"RetailEdge Branch Profile": "public/js/customer_facing_labels.js"' not in source


def test_customer_facing_list_titles_are_professional():
	cashier_source = CASHIER_EXPENSE_LIST_JS.read_text(encoding="utf-8")
	bank_source = BANK_IMPORT_LIST_JS.read_text(encoding="utf-8")
	assert 'set_title(__("Cashier Expenses"))' in cashier_source
	assert 'set_title(__("Bank Statement Imports"))' in bank_source
	assert 'frappe.listview_settings["RetailEdge Cashier Expense"]' in cashier_source
	assert 'frappe.listview_settings["RetailEdge Payment Statement Import"]' in bank_source


def test_business_hub_page_fixture_uses_customer_facing_title_and_stable_route():
	meta = _load(BUSINESS_HUB_PAGE_META)
	assert meta["name"] == "retailedge-business-hub"
	assert meta["page_name"] == "retailedge-business-hub"
	assert meta["title"] == "Business Hub"


def test_business_hub_runtime_states_use_customer_facing_copy():
	source = BUSINESS_HUB_CONTROLLER.read_text(encoding="utf-8")
	assert 'title: __("Business Hub")' in source
	assert '__("Loading Business Hub...")' in source
	assert '__("Business Hub failed to load")' in source
	assert 'title: __("RetailEdge Business Hub")' not in source
	assert '__("Loading RetailEdge Business Hub...")' not in source
	assert '__("RetailEdge Business Hub failed to load")' not in source


def test_all_page_fixtures_avoid_unnecessary_product_prefixes():
	offenders = _customer_facing_page_title_offenders()
	assert not offenders, "Customer-facing Page titles still expose product prefixes:\n" + "\n".join(offenders)


def test_customer_labels_do_not_expose_internal_branch_profile_name():
	meta = _load(BRANCH_SETUP_PATH)
	labels = [field.get("label", "") for field in meta.get("fields", [])]
	assert "RetailEdge Branch Profile" not in labels
	assert "Warehouse Defaults" not in labels
	assert "Default Warehouse" not in labels


def test_retailedge_owned_form_metadata_has_no_unnecessary_product_prefixes():
	offenders = _customer_visible_metadata_offenders()
	assert not offenders, "Customer-visible metadata still exposes internal/product prefixes:\n" + "\n".join(offenders)


def test_edgesuite_navigation_uses_customer_facing_labels_but_keeps_targets():
	source = EDGESUITE_UI_PATH.read_text(encoding="utf-8")
	assert '"label": "Business Hub", "target_type": "Page", "target": "retailedge-business-hub"' in source
	assert '"label": "Stock Locations", "target_type": "DocType", "target": "Warehouse"' in source
	assert '"label": "Settings", "target_type": "DocType", "target": "RetailEdge Settings"' in source
	assert '"label": "Branch Setup", "target_type": "DocType", "target": "RetailEdge Branch Profile"' in source
	assert '"label": "RetailEdge Business Hub"' not in source
	assert '"label": "RetailEdge Settings", "target_type": "DocType"' not in source
	assert '"label": "Branch Profiles", "target_type": "DocType", "target": "RetailEdge Branch Profile"' not in source


def test_native_workspace_uses_same_customer_facing_contract():
	source = WORKSPACE_HOME_PATH.read_text(encoding="utf-8")
	assert 'WorkspaceHomeItem("Business Hub", "Page", "retailedge-business-hub"' in source
	assert 'WorkspaceHomeItem("Stock Locations", "DocType", "Warehouse"' in source
	assert 'WorkspaceHomeItem("Settings", "DocType", "RetailEdge Settings"' in source
	assert 'WorkspaceHomeItem("Branch Setup", "DocType", "RetailEdge Branch Profile"' in source
	assert 'WorkspaceHomeItem("RetailEdge Business Hub"' not in source
	assert 'WorkspaceHomeItem("RetailEdge Settings", "DocType"' not in source


def test_workspace_sync_cannot_reintroduce_old_business_hub_label():
	source = WORKSPACE_SYNC_PATH.read_text(encoding="utf-8")
	assert 'BUSINESS_HUB_PAGE = "retailedge-business-hub"' in source
	assert 'BUSINESS_HUB_LABEL = "Business Hub"' in source
	assert 'BUSINESS_HUB_LABEL = "RetailEdge Business Hub"' not in source


def test_operational_copy_avoids_unnecessary_product_prefixes():
	source = EDGESUITE_UI_PATH.read_text(encoding="utf-8")
	assert "access to RetailEdge workspaces" not in source
	assert "permitted warehouses" not in source
	assert "permitted stock locations" in source
