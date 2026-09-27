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
PROFILE_DOCTYPE_JSON = APP_ROOT / "retailedge" / "doctype" / "retailedge_company_profile" / "retailedge_company_profile.json"


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


def test_company_profile_keeps_erpnext_accounting_truth_and_uses_owner_managed_overlay():
    source = read(PROFILE)
    definition = read(PROFILE_DOCTYPE_JSON)

    for marker in (
        'frappe.db.exists("Company", company)',
        'frappe.get_meta("Company")',
        'frappe.db.get_value("Company", company',
        'PROFILE_DOCTYPE = "RetailEdge Company Profile"',
        "PROFILE_FIELDS = (",
        "def ensure_company_profile",
        "def save_company_profile",
        "def save_company_address",
        "def set_company_logo",
        "def get_shell_identity",
        '"source_of_truth": "ERPNext Company + RetailEdge Company Profile"',
    ):
        assert marker in source

    for forbidden in ("frappe.db.set_value(", "ignore_permissions"):
        assert forbidden not in source

    for editable_field in (
        '"display_name"',
        '"logo"',
        '"phone"',
        '"whatsapp_number"',
        '"email"',
        '"website"',
        '"address_line1"',
        '"city"',
        '"state"',
        '"postal_code"',
    ):
        assert editable_field in definition

    for accounting_field in (
        '"default_currency"',
        '"abbr"',
        '"default_bank_account"',
        '"default_cash_account"',
        '"chart_of_accounts"',
    ):
        assert accounting_field not in definition

    assert '"role":"RetailEdgeManager"' in definition
    assert '"write":1' in definition
    assert '"role":"RetailEdge Branch Manager"' in definition


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
        'title.textContent = "ProcessEdge Retail"',
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
        "RetailEdge Company Profile",
        "frappe.ui.FileUploader",
        '"retailedge.company_profile.ensure_company_profile"',
        '"retailedge.company_profile.save_company_profile"',
        '"retailedge.company_profile.save_company_address"',
        '"retailedge.company_profile.set_company_logo"',
        "window.retailedgeSyncShellIdentity",
        'v-model.trim="profile.display_name"',
        'v-model.trim="profile.phone"',
        'v-model.trim="profile.whatsapp_number"',
        'v-model.trim="profile.email"',
        'product="retailedge"',
        'title="ProcessEdge Retail"',
    ):
        assert marker in source

    assert "<select" not in source
    assert 'v-model.trim="profile.tax_id"' not in source
    assert 'v-model="profile.date_of_establishment"' not in source
    assert "default_currency" not in source
    assert "default_cash_account" not in source
    assert "default_bank_account" not in source
