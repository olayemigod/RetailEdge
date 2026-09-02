from pathlib import Path
import re

root = Path("retailedge")
backend_path = root / "edgesuite_ui.py"
backend = backend_path.read_text()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f"{label}: expected one match, got {count}"
    return text.replace(old, new, 1)


backend = replace_once(
    backend,
    '@frappe.whitelist()\ndef get_retailedge_business_hub_context() -> dict[str, Any]:\n\troles = set(frappe.get_roles(frappe.session.user))\n\ttarget_cache: dict[tuple[str, str], bool] = {}\n',
    '@frappe.whitelist()\ndef get_retailedge_business_hub_context() -> dict[str, Any]:\n\troles = set(frappe.get_roles(frappe.session.user))\n\taccess_context = _get_edgesuite_access_context()\n\ttarget_cache: dict[tuple[str, str], bool] = {}\n',
    "business hub access context",
)
backend = replace_once(
    backend,
    '\tquick_actions = _get_permitted_quick_actions(\n\t\troles=roles,\n\t\ttarget_cache=target_cache,\n\t\tpermission_cache=permission_cache,\n\t)\n\treturn {\n',
    '\tquick_actions = _get_permitted_quick_actions(\n\t\troles=roles,\n\t\ttarget_cache=target_cache,\n\t\tpermission_cache=permission_cache,\n\t\tnative_desk_enabled=bool(access_context.get("can_use_native_desk")),\n\t)\n\treturn {\n',
    "quick action access mode",
)
backend = replace_once(
    backend,
    '\t\t"quick_actions": quick_actions,\n\t\t"context": {\n',
    '\t\t"quick_actions": quick_actions,\n\t\t"access": access_context,\n\t\t"context": {\n',
    "context payload",
)
backend = replace_once(
    backend,
    '\t\t\t"native_document_fallback_enabled": True,\n',
    '\t\t\t"native_document_fallback_enabled": bool(access_context.get("can_use_native_desk")),\n',
    "native fallback flag",
)

anchor = '\ndef _get_permitted_navigation_groups(\n'
helper = '\ndef _get_edgesuite_access_context() -> dict[str, Any]:\n\t"""Read shared interface exposure without changing RetailEdge authorization."""\n\ttry:\n\t\tfrom edgesuite_ui.access_control import get_access_context\n\texcept ImportError:\n\t\treturn {\n\t\t\t"mode": "native_desk",\n\t\t\t"restricted_to_edgesuite": False,\n\t\t\t"can_use_native_desk": True,\n\t\t\t"authorization_source": "frappe_permissions",\n\t\t}\n\treturn dict(get_access_context())\n\n\ndef _get_permitted_navigation_groups(\n'
backend = replace_once(backend, anchor, helper, "shared access helper")
backend = replace_once(
    backend,
    'def _get_permitted_quick_actions(*, roles=None, target_cache=None, permission_cache=None) -> list[dict[str, Any]]:\n',
    'def _get_permitted_quick_actions(\n\t*, roles=None, target_cache=None, permission_cache=None, native_desk_enabled: bool = True,\n) -> list[dict[str, Any]]:\n',
    "quick action signature",
)
backend = replace_once(
    backend,
    '\tfor action in QUICK_ACTIONS:\n\t\tdoctype = action["doctype"]\n\t\tif not _doctype_exists_cached(doctype, target_cache) or not _has_permission_cached(doctype, "create", permission_cache):\n',
    '\tfor action in QUICK_ACTIONS:\n\t\tdoctype = action["doctype"]\n\t\tif action.get("mode") == "native_fallback" and not native_desk_enabled:\n\t\t\tcontinue\n\t\tif not _doctype_exists_cached(doctype, target_cache) or not _has_permission_cached(doctype, "create", permission_cache):\n',
    "quick action native fallback",
)
backend = replace_once(
    backend,
    '\tif target_type == "Page":\n\t\treturn _target_exists_cached(target_type, target, target_cache)\n\treturn False\n\n\ndef _can_open_report_cached',
    '\tif target_type == "Page":\n\t\treturn _target_exists_cached(target_type, target, target_cache) and _can_open_page_cached(\n\t\t\ttarget, permission_cache\n\t\t)\n\treturn False\n\n\ndef _can_open_page_cached(page_name: str, cache: dict[tuple[str, str], bool]) -> bool:\n\tkey = (f"Page:{page_name}", "open")\n\tif key not in cache:\n\t\tcache[key] = _can_open_page(page_name)\n\treturn cache[key]\n\n\ndef _can_open_page(page_name: str) -> bool:\n\ttry:\n\t\tpage = frappe.get_doc("Page", page_name)\n\t\treturn bool(page.is_permitted())\n\texcept Exception:\n\t\treturn False\n\n\ndef _can_open_report_cached',
    "page permission",
)
backend_path.write_text(backend)

hub_path = root / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"
hub = hub_path.read_text()
dialog_names = [
    "SimpleSalesInvoiceDialog",
    "SimplePaymentDialog",
    "SimpleCashDepositDialog",
    "SimpleCashTransferDialog",
    "SimplePurchaseInvoiceDialog",
    "SimpleCashierExpenseDialog",
    "SimpleStockTransferDialog",
    "SimpleStockAdjustmentDialog",
]
for name in dialog_names:
    pattern = re.compile(rf'(<{re.escape(name)}\n\s*:open="[^"]+"\n)')
    hub, count = pattern.subn(
        r'\1\t\t\t\t:native-fallback-enabled="nativeFallbackEnabled"\n',
        hub,
        count=1,
    )
    assert count == 1, f"missing parent prop for {name}"

hub = replace_once(
    hub,
    '\t\t\tfeatureFlags: {},\n\t\t};\n',
    '\t\t\tfeatureFlags: {},\n\t\t\taccessContext: { mode: "native_desk", restricted_to_edgesuite: false, can_use_native_desk: true },\n\t\t};\n',
    "hub access state",
)
hub = replace_once(
    hub,
    '\t\tshellMenuItems() {\n',
    '\t\tnativeFallbackEnabled() {\n\t\t\treturn (\n\t\t\t\tthis.accessContext.can_use_native_desk !== false &&\n\t\t\t\tthis.featureFlags.native_document_fallback_enabled !== false\n\t\t\t);\n\t\t},\n\t\tshellMenuItems() {\n',
    "hub native fallback computed",
)
hub = replace_once(
    hub,
    '\t\t\t\t\t\t\tdescription: item.description || "",\n\t\t\t\t\t\t\troute: this.routeForTarget(item),\n\t\t\t\t\t\t\ticon: item.icon || "list",\n\t\t\t\t\t\t\tsource: item,\n',
    '\t\t\t\t\t\t\tdescription: item.description || "",\n\t\t\t\t\t\t\troute: this.routeForTarget(item),\n\t\t\t\t\t\t\ticon: item.icon || "list",\n\t\t\t\t\t\t\tlink_type: item.target_type,\n\t\t\t\t\t\t\tlink_to: item.target,\n\t\t\t\t\t\t\tsource: item,\n',
    "shell link metadata",
)
hub = replace_once(
    hub,
    '\t\t\tthis.featureFlags = data.feature_flags || {};\n\t\t\tif (!this.quickActions.length) this.createPickerOpen = false;\n',
    '\t\t\tthis.featureFlags = data.feature_flags || {};\n\t\t\tthis.accessContext = { ...this.accessContext, ...(data.access || {}) };\n\t\t\tif (!this.quickActions.length) this.createPickerOpen = false;\n',
    "hub access apply",
)
hub = replace_once(
    hub,
    '\t\t\tfrappe.new_doc(action.doctype);\n\t\t},\n\t\tnotifyGuidedDraftSaved',
    '\t\t\tif (!this.nativeFallbackEnabled) {\n\t\t\t\tfrappe.show_alert?.({ message: "This account is limited to EdgeSuite operational pages.", indicator: "orange" });\n\t\t\t\treturn;\n\t\t\t}\n\t\t\tfrappe.new_doc(action.doctype);\n\t\t},\n\t\tnotifyGuidedDraftSaved',
    "hub native fallback guard",
)
hub = replace_once(
    hub,
    '\t\t\tconst doctype = result.doctype || fallbackDoctype;\n\t\t\tfrappe.set_route("Form", doctype, result.name);\n\t\t\tfrappe.call({\n',
    '\t\t\tconst doctype = result.doctype || fallbackDoctype;\n\t\t\tif (this.nativeFallbackEnabled) {\n\t\t\t\tfrappe.set_route("Form", doctype, result.name);\n\t\t\t}\n\t\t\tfrappe.call({\n',
    "guided save continuation",
)
hub_path.write_text(hub)

for name in dialog_names:
    path = root / f"public/js/retailedge_business_hub/{name}.vue"
    text = path.read_text()
    multiline_props = '\tprops: {\n'
    inline_open_props = '\tprops: { open: { type: Boolean, default: false } },\n'
    if multiline_props in text:
        text = replace_once(
            text,
            multiline_props,
            multiline_props + '\t\tnativeFallbackEnabled: { type: Boolean, default: true },\n',
            f"{name} multiline props",
        )
    else:
        text = replace_once(
            text,
            inline_open_props,
            '\tprops: {\n\t\topen: { type: Boolean, default: false },\n\t\tnativeFallbackEnabled: { type: Boolean, default: true },\n\t},\n',
            f"{name} inline props",
        )
    pattern = re.compile(r'(<button\b)([^>]*@click="openFullForm"[^>]*>)')
    text, count = pattern.subn(
        r'\1 v-if="nativeFallbackEnabled"\2',
        text,
        count=1,
    )
    assert count == 1, f"Open Full Form button mismatch: {name}"
    path.write_text(text)
