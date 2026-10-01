from __future__ import annotations

import inspect
import json
from pathlib import Path

from retailedge import payment_statement_import_workspace


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "payment_statement_import_workspace.py"
COMPONENT = ROOT / "public/js/bank_statement_imports/BankStatementImports.vue"
BUNDLE = ROOT / "public/js/bank_statement_imports.bundle.js"
PAGE_JS = ROOT / "retailedge/page/bank_statement_imports/bank_statement_imports.js"
PAGE_JSON = ROOT / "retailedge/page/bank_statement_imports/bank_statement_imports.json"
EDGE_NAV = ROOT / "edgesuite_ui.py"
HOME = ROOT / "workspace_home.py"


def test_bank_statement_imports_is_edgesuite_page_not_native_everyday_entry():
    edge_nav = EDGE_NAV.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert '"label": "Import Bank Statement", "target_type": "Page", "target": "bank-statement-imports"' in edge_nav
    assert 'WorkspaceHomeItem("Import Bank Statement", "Page", "bank-statement-imports"' in home
    assert '"Import Bank Statement", "DocType", "RetailEdge Payment Statement Import"' not in home


def test_page_bootstraps_edgesuite_runtime_and_product_bundle():
    source = PAGE_JS.read_text(encoding="utf-8")
    for expected in (
        'EDGEUI_ASSET = "edgeui.bundle.js"',
        'STATEMENT_ASSET = "bank_statement_imports.bundle.js"',
        'PAGE_ROUTE = "bank-statement-imports"',
        "hideNativePageSidebar",
        "mountRetailEdgeBankStatementImports",
    ):
        assert expected in source
    bundle = BUNDLE.read_text(encoding="utf-8")
    assert "EdgeSuiteUI" in bundle
    assert "createEdgeApp" in bundle
    assert "BankStatementImports.vue" in bundle


def test_page_roles_match_governed_money_and_banking_personas():
    meta = json.loads(PAGE_JSON.read_text(encoding="utf-8"))
    roles = {row["role"] for row in meta.get("roles", [])}
    for role in (
        "System Manager",
        "RetailEdge Manager",
        "RetailEdgeManager",
        "RetailEdge Branch Manager",
        "RetailEdgeBranchManager",
        "Accounts Manager",
        "Accounts User",
    ):
        assert role in roles


def test_workspace_reads_are_permission_aware_bounded_and_branch_scoped():
    source = inspect.getsource(payment_statement_import_workspace)
    for expected in (
        'frappe.has_permission(DOCTYPE, "read")',
        "get_operational_branch_scope",
        "validate_operating_branch",
        "limit_page_length=page_size + 1",
        "MAX_LIST_ROWS = 100",
        "MAX_DETAIL_ROWS = 100",
        "search_retailedge_bank_accounts",
        "resolve_retailedge_bank_account",
    ):
        assert expected in source
    assert "ignore_permissions" not in source
    assert "frappe.db.commit" not in source


def test_workspace_create_is_draft_only_and_revalidates_bank_scope():
    source = inspect.getsource(payment_statement_import_workspace.create_bank_statement_import)
    assert 'frappe.has_permission(DOCTYPE, "create")' in source
    assert "resolve_retailedge_bank_account" in source
    assert "frappe.new_doc(DOCTYPE)" in source
    assert "doc.insert()" in source
    assert 'doc.import_status = "Draft"' in source
    assert "doc.submit()" not in source


def test_statement_actions_are_wrapped_before_legacy_services_are_called():
    source = inspect.getsource(payment_statement_import_workspace)
    for expected in (
        "def _assert_statement_action(",
        'frappe.has_permission("Bank Transaction", bank_transaction_access)',
        "def preview_statement_rows(",
        "def import_statement_rows(",
        "def preview_statement_bank_transactions(",
        "def create_statement_bank_transactions(",
        "def get_statement_possible_duplicates(",
        "def accept_statement_possible_duplicate(",
        "_preview_payment_statement_import_rows",
        "_import_payment_statement_rows",
        "_preview_bank_transaction_import",
        "_import_statement_rows_to_bank_transactions",
        "_get_possible_duplicate_statement_rows",
        "_accept_possible_duplicate_statement_row",
    ):
        assert expected in source


def test_edgesuite_workspace_owns_create_upload_review_and_conversion_actions():
    source = COMPONENT.read_text(encoding="utf-8")
    for expected in (
        "EdgeAppShell",
        "EdgeLinkField",
        "EdgeDropdown",
        "EdgeModal",
        "New Statement Import",
        "Upload File",
        "Preview Statement Rows",
        "Import Statement Rows",
        "Preview Bank Transactions",
        "Create Bank Transactions",
        "Review Possible Duplicates",
        "Accept Selected Row",
        "frappe.ui.FileUploader",
        "confirmAboveEdgeModal",
        "Advanced: Open Full Record",
    ):
        assert expected in source
    assert "retailedge.api." not in source
    assert "retailedge.payment_statement_import_workspace" in source


def test_statement_form_cascades_company_branch_and_bank_account():
    source = COMPONENT.read_text(encoding="utf-8")
    for expected in (
        'this.form.branch = ""',
        'this.form.bank_account = ""',
        "bankAccountSearch(txt)",
        'this.search("bank_account", txt, this.form.company, this.form.branch)',
        "selectFormBranch(option)",
        "clearFormBranch()",
    ):
        assert expected in source


def test_native_doctype_is_advanced_fallback_only_from_edgesuite_workspace():
    source = COMPONENT.read_text(encoding="utf-8")
    assert "Advanced: ERPNext List" in source
    assert "Advanced: Open Full Record" in source
    assert 'frappe.set_route("List", "RetailEdge Payment Statement Import")' in source
    assert 'frappe.set_route("Form", "RetailEdge Payment Statement Import"' in source
