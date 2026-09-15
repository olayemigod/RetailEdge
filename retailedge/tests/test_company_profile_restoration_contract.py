from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_ROOT = APP_ROOT / "retailedge" / "page" / "company_profile"
PROFILE = APP_ROOT / "company_profile.py"
BOOT = APP_ROOT / "boot.py"
MASTER = APP_ROOT / "master_experience.py"
SHELL = APP_ROOT / "public" / "js" / "retailedge_shell_context.js"
OPERATING = APP_ROOT / "public" / "js" / "operating_context" / "OperatingContext.vue"
COMPONENT = APP_ROOT / "public" / "js" / "company_profile" / "CompanyProfile.vue"
BUNDLE = APP_ROOT / "public" / "js" / "company_profile.bundle.js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_company_profile_standard_page_is_present_and_not_orphaned():
    page_json = PAGE_ROOT / "company_profile.json"
    page_js = PAGE_ROOT / "company_profile.js"
    page_py = PAGE_ROOT / "company_profile.py"

    for path in (page_json, page_js, page_py, PROFILE, COMPONENT, BUNDLE):
        assert path.exists(), path

    source = read(page_json)
    assert '"name": "company-profile"' in source
    assert '"page_name": "company-profile"' in source
    assert '"standard": "Yes"' in source
    assert '"module": "RetailEdge"' in source


def test_company_profile_uses_erpnext_company_as_source_of_truth_and_safe_profile_fields():
    source = read(PROFILE)

    for marker in (
        'frappe.db.exists("Company", company)',
        'frappe.get_meta("Company")',
        'frappe.db.get_value("Company", company',
        '"source_of_truth": "ERPNext Company"',
        "PROFILE_EDITABLE_FIELDS = (",
        '"company_name"',
        '"tax_id"',
        '"website"',
        '"date_of_establishment"',
        "def save_company_profile",
        "def save_company_address",
        "def set_company_logo",
        "def get_shell_identity",
    ):
        assert marker in source

    for forbidden in ("frappe.db.set_value(", "ignore_permissions"):
        assert forbidden not in source

    editable_block = source.split("PROFILE_EDITABLE_FIELDS = (", 1)[1].split(")", 1)[0]
    for accounting_field in ("default_currency", "abbr", "country", "default_bank_account", "default_cash_account"):
        assert accounting_field not in editable_block


def test_company_profile_is_in_retailedge_home_navigation_and_context():
    source = read(MASTER)

    for marker in (
        '"label": "Company Profile"',
        '"target": "company-profile"',
        "def _add_company_profile_navigation",
        "_add_company_profile_navigation(navigation_groups)",
        "resolve_company_profile(company)",
        '"company_profile": identity',
    ):
        assert marker in source


def test_boot_and_runtime_share_company_profile_identity():
    boot = read(BOOT)
    shell = read(SHELL)

    assert "from retailedge.company_profile import get_shell_identity" in boot
    assert "payload = get_shell_identity()" in boot
    for marker in (
        '"retailedge.company_profile.get_shell_identity"',
        "window.retailedgeSyncShellIdentity",
        "boot.retailedge_ui_identity",
        "boot.edgesuite_ui_identity.retailedge",
        "function ensureRetailEdgeBrand(shell)",
        'title.textContent = "RetailEdge"',
    ):
        assert marker in shell


def test_operating_context_refreshes_company_identity_after_switch():
    source = read(OPERATING)

    assert ':tenantName="tenantName || current.company"' in source
    assert 'navigation.context?.company_label || navigation.context?.company || ""' in source
    assert '"retailedge.company_profile.get_shell_identity"' in source
    assert "window.retailedgeSyncShellIdentity?.(identity)" in source
    assert "window.location.reload()" in source


def test_company_profile_owner_ui_supports_logo_safe_edits_address_and_advanced_link():
    source = read(COMPONENT)

    for marker in (
        "Upload logo",
        "Remove logo",
        "Save Company profile",
        "Save address",
        "Advanced: Open Company in ERPNext",
        "frappe.ui.FileUploader",
        '"retailedge.company_profile.save_company_profile"',
        '"retailedge.company_profile.save_company_address"',
        '"retailedge.company_profile.set_company_logo"',
        "window.retailedgeSyncShellIdentity",
        "EdgeDropdown",
        'product="retailedge"',
    ):
        assert marker in source

    assert "<select" not in source
    assert "default_currency" not in source
    assert "default_cash_account" not in source
    assert "default_bank_account" not in source
