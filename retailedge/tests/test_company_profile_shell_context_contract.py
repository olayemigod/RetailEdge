from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
COMPANY_PROFILE = APP_ROOT / "company_profile.py"
BOOT = APP_ROOT / "boot.py"
MASTER = APP_ROOT / "master_experience.py"
SHELL = APP_ROOT / "public/js/retailedge_shell_context.js"
OPERATING = APP_ROOT / "public/js/operating_context/OperatingContext.vue"
IDENTITY_CSS = APP_ROOT / "public/css/retailedge_product_identity.css"
HUB = APP_ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"


def test_company_profile_reuses_erpnext_company_truth_instead_of_creating_parallel_master():
	source = COMPANY_PROFILE.read_text(encoding="utf-8")
	for marker in (
		'frappe.db.exists("Company", company)',
		'frappe.get_meta("Company")',
		'frappe.db.get_value("Company", company',
		'"company_name"',
		'"company_logo"',
		'"default_currency"',
		'"country"',
		'"tax_id"',
		'"source_of_truth": "ERPNext Company"',
	):
		assert marker in source
	for forbidden in ("frappe.new_doc(", ".insert(", ".save(", "frappe.db.set_value(", "ignore_permissions"):
		assert forbidden not in source


def test_shell_identity_is_one_company_profile_contract_for_boot_and_runtime_refresh():
	profile = COMPANY_PROFILE.read_text(encoding="utf-8")
	boot = BOOT.read_text(encoding="utf-8")
	shell = SHELL.read_text(encoding="utf-8")
	for marker in (
		"def get_shell_identity",
		'"tenant_name": profile.get("label")',
		'"tenant_logo": profile.get("logo")',
		'"active_company": company',
		'"active_branch": _clean(current.get("branch"))',
		'"company_profile": profile',
	):
		assert marker in profile
	assert "payload = get_shell_identity()" in boot
	for marker in (
		'"retailedge.company_profile.get_shell_identity"',
		"window.retailedgeSyncShellIdentity",
		"boot.retailedge_ui_identity",
		"boot.edgesuite_ui_identity.retailedge",
		'"edgesuite-context-changed"',
		'"retailedge-operating-context-changed"',
	):
		assert marker in shell


def test_operating_context_switch_refreshes_shell_identity_and_persists_context_across_pages():
	component = OPERATING.read_text(encoding="utf-8")
	for marker in (
		'"retailedge.operating_context.switch_operating_context"',
		'"retailedge.company_profile.get_shell_identity"',
		"window.retailedgeSyncShellIdentity?.(identity)",
		"window.location.reload()",
		'"retailedge.operating_context.clear_operating_context"',
	):
		assert marker in component


def test_retailedge_sidebar_follows_shared_navigation_shell_pattern_and_has_identity_fallback():
	shell = SHELL.read_text(encoding="utf-8")
	css = IDENTITY_CSS.read_text(encoding="utf-8")
	for marker in (
		"function ensureRetailEdgeBrand(shell)",
		'".edge-sidebar__brand"',
		'".edge-sidebar__brand-copy"',
		'title.textContent = "RetailEdge"',
	):
		assert marker in shell
	for marker in (
		".edge-nav-shell-v2",
		"var(--edge-color-surface",
		"var(--edge-color-border",
		"var(--edge-color-ink-950",
		"box-shadow: inset 2px 0 0 var(--edge-color-brand-600)",
		'data-edge-appearance="dark"',
	):
		assert marker in css


def test_operating_context_warning_uses_theme_semantics_in_dark_mode():
	component = OPERATING.read_text(encoding="utf-8")
	for marker in (
		"color-mix(in srgb, var(--edge-color-warning) 12%, var(--edge-color-surface))",
		"color-mix(in srgb, var(--edge-color-warning) 38%, var(--edge-color-border))",
		"var(--edge-color-ink-950)",
		"var(--edge-color-ink-700)",
		':global(:root[data-edge-appearance="dark"]) .operating-context-warning',
	):
		assert marker in component


def test_business_hub_compacts_large_values_but_preserves_exact_value_tooltips():
	source = HUB.read_text(encoding="utf-8")
	for marker in (
		"compactNumber(value",
		'notation: "compact"',
		'{ value: 1e9, suffix: "B" }',
		'{ value: 1e6, suffix: "M" }',
		'{ value: 1e3, suffix: "K" }',
		'formatHomeValue(card, { compact: false })',
		'formatHomeValue(index.headline, { compact: false })',
		'formatHomeValue(index.signal, { compact: false })',
		"text-overflow: ellipsis",
		"overflow-wrap: anywhere",
	):
		assert marker in source


def test_company_profile_is_promoted_into_edgesuite_home_navigation():
	master = MASTER.read_text(encoding="utf-8")
	for marker in (
		'"label": "Company Profile"',
		'"target": "company-profile"',
		"def _add_company_profile_navigation",
		"_add_company_profile_navigation(navigation_groups)",
		"resolve_company_profile(company)",
		'"company_profile": identity',
	):
		assert marker in master
