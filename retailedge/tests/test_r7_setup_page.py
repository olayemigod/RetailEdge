from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SETUP_PAGE_ROOT = APP_ROOT / "retailedge" / "page" / "retailedge_setup"
SETUP_PY = SETUP_PAGE_ROOT / "retailedge_setup.py"
SETUP_JS = SETUP_PAGE_ROOT / "retailedge_setup.js"
SETUP_JSON = SETUP_PAGE_ROOT / "retailedge_setup.json"
PRODUCT_MENU = APP_ROOT / "public" / "js" / "retailedge_product_menu.bundle.js"
BRANCH_PROFILE_SERVICE = APP_ROOT / "branch_profile.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_setup_page_uses_existing_configuration_doctypes_as_truth():
    source = _source(SETUP_PY)
    expected_doctypes = (
        "RetailEdge Settings",
        "RetailEdge Branch Profile",
        "RetailEdge Expense Category",
        "RetailEdge Statement Mapping Template",
    )
    for doctype in expected_doctypes:
        assert doctype in source
    assert 'RETAILEDGE_SETTINGS_DOCTYPE = "RetailEdge Settings"' in source
    assert 'EXPENSE_CATEGORY_DOCTYPE = "RetailEdge Expense Category"' in source
    assert 'BRANCH_PROFILE_DOCTYPE = "RetailEdge Branch Profile"' in source
    assert 'STATEMENT_MAPPING_DOCTYPE = "RetailEdge Statement Mapping Template"' in source
    assert "ignore_permissions" not in source


def test_setup_context_uses_permission_filtered_counts_and_permissions():
    source = _source(SETUP_PY)
    assert 'frappe.has_permission(doctype, ptype="read", doc=doc)' in source
    assert 'frappe.has_permission(doctype, ptype="create")' in source
    assert 'frappe.has_permission(doc.doctype, ptype="write", doc=doc)' in source
    assert 'frappe.db.exists("DocType", doctype)' in source
    assert "def _permission_filtered_count(doctype: str)" in source
    assert 'frappe.get_list(doctype, fields=["name"], limit_page_length=0)' in source
    assert "frappe.db.count(doctype)" not in source


def test_setup_page_keeps_full_forms_as_new_tab_fallbacks():
    source = _source(SETUP_JS)
    assert '"_blank", "noopener,noreferrer"' in source
    assert '__("Open Full Form")' in source
    assert "frappe.set_route" not in source


def test_setup_page_uses_business_facing_retailedge_copy():
    js_source = _source(SETUP_JS)
    json_source = _source(SETUP_JSON)
    assert '"RetailEdge Setup"' in json_source
    assert '__("Business Setup")' in js_source
    assert "EdgeSuite" not in js_source
    assert "EdgeSuite" not in json_source


def test_retailedge_owned_setup_links_promote_to_one_setup_page():
    source = _source(PRODUCT_MENU)
    owned_doctypes = (
        "RetailEdge Settings",
        "RetailEdge Branch Profile",
        "RetailEdge Expense Category",
        "RetailEdge Statement Mapping Template",
    )
    for doctype in owned_doctypes:
        assert f'"DocType:{doctype}"' in source
    assert source.count('target: "retailedge-setup"') == 4
    assert source.count('label: "RetailEdge Setup"') == 4
    assert "consolidateNavigationGroups" in source


def test_external_setup_masters_remain_native_advanced_fallbacks():
    source = _source(PRODUCT_MENU)
    assert '"DocType:Bank Account"' not in source
    assert '"DocType:Mode of Payment"' not in source
    assert 'item.link_type === "Report" || item.link_type === "DocType"' in source
    assert 'window.open(url, "_blank", "noopener,noreferrer")' in source


def test_expense_categories_are_managed_inside_setup_with_safe_cascades():
    py_source = _source(SETUP_PY)
    js_source = _source(SETUP_JS)
    assert "def get_expense_categories()" in py_source
    assert "def save_expense_category(values, name: str | None = None)" in py_source
    assert "frappe.get_doc(EXPENSE_CATEGORY_DOCTYPE, name)" in py_source
    assert "frappe.new_doc(EXPENSE_CATEGORY_DOCTYPE)" in py_source
    assert 'row["can_write"] = _has_write_permission(doc)' in py_source
    assert '__("Add Expense Category")' in js_source
    assert '__("Edit Expense Category")' in js_source
    assert 'root_type: "Expense"' in js_source
    assert 'accountField.set_value("")' in js_source
    assert 'costCenterField.set_value("")' in js_source


def test_existing_expense_category_name_is_not_implicitly_renamed():
    py_source = _source(SETUP_PY)
    js_source = _source(SETUP_JS)
    assert 'if fieldname == "category_name" and name:' in py_source
    assert "read_only: editing ? 1 : 0" in js_source


def test_branch_profile_service_enforces_server_side_company_integrity():
    source = _source(BRANCH_PROFILE_SERVICE)
    assert "COMPANY_LINK_FIELDS = {" in source
    for fieldname in (
        "branch",
        "default_pos_profile",
        "default_warehouse",
        "default_source_warehouse",
        "default_target_warehouse",
        "default_returns_warehouse",
        "default_cost_center",
        "default_sales_cost_center",
        "default_expense_cost_center",
        "default_pos_opening_cash_account",
        "default_cash_account",
        "default_bank_account",
        "default_card_pos_account",
        "default_mobile_money_account",
    ):
        assert f'"{fieldname}"' in source
    assert "_validate_company_links(doc)" in source
    assert "_validate_leaf_defaults(doc)" in source
    assert "must belong to Company" in source
    assert "must be a leaf" in source
    assert "must be enabled" in source


def test_branch_profile_details_enforce_record_read_and_match_ui_contract():
    py_source = _source(SETUP_PY)
    js_source = _source(SETUP_JS)
    detail_block = py_source.split("def get_branch_profile_details", 1)[1].split("def _normalize_operational_users", 1)[0]
    assert "doc = frappe.get_doc(BRANCH_PROFILE_DOCTYPE, name)" in detail_block
    assert "_has_read_permission(BRANCH_PROFILE_DOCTYPE, doc=doc)" in detail_block
    assert 'values = {"name": doc.name' in detail_block
    assert 'values["can_write"] = _has_write_permission(doc)' in detail_block
    assert "return values" in detail_block
    assert "details = response.message || row" in js_source
    assert "details.name ? Number(details.enabled) : 1" in js_source


def test_branch_profiles_are_managed_inside_setup_and_reuse_controller_validation():
    py_source = _source(SETUP_PY)
    js_source = _source(SETUP_JS)
    controller_source = _source(BRANCH_PROFILE_SERVICE)
    assert "def get_branch_profiles()" in py_source
    assert "def save_branch_profile(values, name: str | None = None)" in py_source
    assert "frappe.get_doc(BRANCH_PROFILE_DOCTYPE, name)" in py_source
    assert "frappe.new_doc(BRANCH_PROFILE_DOCTYPE)" in py_source
    assert "validate_branch_profile" in controller_source
    assert "An enabled RetailEdge Branch Profile already exists" in controller_source
    assert "Only one enabled default RetailEdge Branch Profile" in controller_source
    assert '__("Add Branch Profile")' in js_source
    assert '__("Edit Branch Profile")' in js_source


def test_branch_profile_company_change_clears_company_dependent_values():
    source = _source(SETUP_JS)
    assert "function configureBranchProfileQueries(dialog)" in source
    for fieldname in (
        "branch",
        "default_pos_profile",
        "default_pos_opening_cash_account",
        "default_warehouse",
        "default_source_warehouse",
        "default_target_warehouse",
        "default_returns_warehouse",
        "default_cost_center",
        "default_sales_cost_center",
        "default_expense_cost_center",
        "default_cash_account",
        "default_bank_account",
        "default_card_pos_account",
        "default_mobile_money_account",
    ):
        assert f'"{fieldname}"' in source
    assert 'companyField.df.onchange = () =>' in source
    assert 'set_value("")' in source


def test_branch_and_pos_queries_use_frappe_filter_shape():
    source = _source(SETUP_JS)
    assert 'branchField.get_query = () => ({ filters: companyFilters() })' in source
    assert 'posField.get_query = () => ({ filters: companyFilters() })' in source
    assert "branchField.get_query = companyFilters" not in source
    assert "posField.get_query = companyFilters" not in source


def test_branch_operational_user_backend_is_safe_and_role_bound():
    source = _source(SETUP_PY)
    assert '"default_cashiers": "Cashier"' in source
    assert '"default_managers": "Manager"' in source
    assert '"default_auditors": "Auditor"' in source
    assert "def _normalize_operational_users(rows, role_type: str)" in source
    assert 'frappe.db.get_value("User", user, "enabled")' in source
    assert "is disabled and cannot be assigned" in source
    assert "cannot appear more than once in the same operational role" in source
    assert '"role_type": role_type' in source
    assert "doc.set(table_field, _normalize_operational_users" in source


def test_branch_operational_users_are_managed_in_setup_ui():
    source = _source(SETUP_JS)
    assert "function branchUserTable(fieldname, label, rows)" in source
    assert "get_branch_profile_details" in source
    for fieldname in ("default_cashiers", "default_managers", "default_auditors"):
        assert f'branchUserTable("{fieldname}"' in source
    assert 'options: "RetailEdge Branch Profile User"' in source
    assert 'filters: { enabled: 1 }' in source
    assert 'fieldname: "is_default"' in source
    assert 'fieldname: "notes"' in source


def test_retailedge_settings_are_managed_through_singleton_with_permissions():
    py_source = _source(SETUP_PY)
    js_source = _source(SETUP_JS)
    assert "def get_retailedge_settings()" in py_source
    assert "def save_retailedge_settings(values)" in py_source
    assert "frappe.get_single(RETAILEDGE_SETTINGS_DOCTYPE)" in py_source
    assert "_has_read_permission(RETAILEDGE_SETTINGS_DOCTYPE, doc=doc)" in py_source
    assert "_has_write_permission(doc)" in py_source
    assert "doc.save()" in py_source
    assert "function openRetailEdgeSettings()" in js_source


def test_settings_operating_role_tables_are_safe_and_managed_in_ui():
    py_source = _source(SETUP_PY)
    js_source = _source(SETUP_JS)
    role_block = py_source.split("SETTINGS_ROLE_TABLES = (", 1)[1].split(")\n\nEXPENSE_CATEGORY_FIELDS", 1)[0]
    for fieldname in (
        "posting_date_allowed_roles",
        "cost_price_hidden_roles",
        "daily_sales_audit_reviewer_roles",
    ):
        assert fieldname in role_block
        assert f'roleTableField("{fieldname}"' in js_source
    assert "allowed_reconciliation_execution_roles" not in role_block
    assert "def _normalize_roles(rows)" in py_source
    assert 'frappe.db.exists("Role", role)' in py_source
    assert "cannot appear more than once in the same setting" in py_source


def test_settings_ui_excludes_bank_and_platform_controls():
    py_source = _source(SETUP_PY)
    js_source = _source(SETUP_JS)
    managed_block = py_source.split("SETTINGS_MANAGED_FIELDS = (", 1)[1].split(")\n\nSETTINGS_ROLE_TABLES", 1)[0]
    excluded = (
        "enable_coreedge_integration",
        "coreedge_required_for_portal",
        "enable_coreedge_payment_requests",
        "enable_coreedge_notifications",
        "enable_coreedge_branch_context",
        "enable_bank_auto_match",
        "auto_prepare_exact_bank_matches",
        "auto_confirm_exact_bank_matches",
        "enable_bank_reconciliation_execution",
        "allowed_reconciliation_execution_roles",
    )
    for fieldname in excluded:
        assert fieldname not in managed_block
        assert f'fieldname: "{fieldname}"' not in js_source
    assert "bank matching/reconciliation settings remain in the full form" in js_source


def test_statement_mappings_are_managed_inside_setup_with_backend_validation():
    py_source = _source(SETUP_PY)
    js_source = _source(SETUP_JS)
    assert "def get_statement_mappings()" in py_source
    assert "def save_statement_mapping(values, name: str | None = None)" in py_source
    assert "def _validate_statement_mapping(doc)" in py_source
    assert 'frappe.db.get_value("Account", doc.default_account' in py_source
    assert "Default Account must be an enabled ledger account" in py_source
    assert "Default Account must belong to the selected Company" in py_source
    assert 'row["can_write"] = _has_write_permission(doc)' in py_source
    assert "function openStatementMappingManager(resource)" in js_source
    assert "function openStatementMappingEditor(row, resource, parentDialog)" in js_source


def test_statement_mapping_company_change_filters_and_clears_default_account():
    source = _source(SETUP_JS)
    assert 'company: companyField.get_value() || undefined' in source
    assert "is_group: 0" in source
    assert "disabled: 0" in source
    assert 'companyField.df.onchange = () => accountField.set_value("")' in source


def test_existing_statement_mapping_name_is_not_implicitly_renamed():
    py_source = _source(SETUP_PY)
    js_source = _source(SETUP_JS)
    assert 'if fieldname == "template_name" and name:' in py_source
    assert 'fieldname: "template_name"' in js_source
    assert "read_only: editing ? 1 : 0" in js_source
