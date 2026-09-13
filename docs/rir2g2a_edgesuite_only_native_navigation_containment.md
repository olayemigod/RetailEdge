# RIR2G2A — EdgeSuite-Only Native Navigation Containment

## Goal

Ensure ordinary EdgeSuite-only RetailEdge users are not presented raw ERPNext/Frappe DocType or Query Report navigation, while preserving those routes for users explicitly allowed to use Native Desk.

This is presentation/composition hardening only. It does not change ERPNext permissions or remove advanced functionality.

## Context

The shared access context exposes `can_use_native_desk`.

Current base filtering removes only navigation items marked `mode = "native_fallback"`. Numerous raw DocType and Report items have no such marker and therefore survive for EdgeSuite-only users.

Final `master_experience` composition can append Project DocType and project Report routes after the base filter.

Business Hub also lacks its own fail-closed check before routing a received DocType/Report.

## Scope

- `retailedge/edgesuite_ui.py`
- `retailedge/master_experience.py`
- `retailedge/public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue`
- focused access/navigation contract tests
- RIR2G2 audit/contract documentation

## Required Behavior

### Base navigation

When `native_desk_enabled = false`:

- do not return any navigation item whose resolved `target_type` is `DocType` or `Report`;
- keep permission-allowed `Page` and `URL` items;
- runtime-resolved POS Opening/Closing DocType routes must also be contained;
- normal target existence and Frappe permission checks remain authoritative for retained items.

When `native_desk_enabled = true`:

- preserve existing permission-aware DocType/Report navigation behavior.

The filter must act on the **resolved** navigation item, not only the pre-resolution registry entry.

### Final master composition

After all promotions and additions, if final access says `can_use_native_desk = false`:

- remove any remaining/appended `DocType` or `Report` navigation item;
- remove groups left empty by containment;
- keep Pages and URLs;
- do not modify quick actions here.

This prevents post-filter additions such as native Project/report routes from escaping containment.

### Business Hub defense in depth

For EdgeSuite-only users:

- `shellMenuItems` must not expose DocType/Report routes;
- `routeForTarget()` must return no route for DocType/Report items;
- `openTarget()` must fail closed before DocType/Report navigation;
- every Business Hub `openNative*` handler must return before `frappe.new_doc` when native fallback is disabled.

These client guards are defensive only. Server composition remains the primary exposure control.

## Preserved Behavior

- EdgeSuite Pages continue to open normally.
- Approved URL targets such as POS runtime may remain.
- Native-Desk-capable users retain native forms/reports subject to Frappe permissions.
- Underlying ERPNext DocTypes, Reports, permissions and roles are unchanged.
- Deliberate advanced-native workflows remain available to authorised Native Desk users.
- standard Quick Entry for Customer/Supplier/Item remains EdgeSuite-hosted.
- Phase-2 workflow completion owners remain unchanged.

## Out of Scope

- building replacement EdgeSuite pages for every hidden native item;
- changing ERPNext roles or permissions;
- changing `desk_access`;
- changing POS lifecycle;
- table sorting;
- report feature expansion;
- Business Hub redesign;
- accounting, stock or workflow semantics;
- schema/migration work;
- manual browser/persona QA.

## Tests Required

1. base navigation removes resolved DocType items when Native Desk is disabled;
2. base navigation removes resolved Report items when Native Desk is disabled;
3. base navigation keeps Page/URL items for EdgeSuite-only users;
4. runtime-resolved native POS opening/closing routes are contained;
5. Native-Desk-capable users retain permission-allowed DocType/Report items;
6. final master composition removes DocType/Report items appended after base filtering;
7. empty navigation groups are removed;
8. final master composition preserves Pages/URLs;
9. Business Hub shell menu filters DocType/Report entries when native fallback is disabled;
10. `routeForTarget` fails closed for DocType/Report without Native Desk;
11. `openTarget` fails closed for DocType/Report without Native Desk;
12. all Business Hub `openNative*` methods defensively check `nativeFallbackEnabled`;
13. standard guided/Quick Entry actions remain available;
14. existing report permission gate remains unchanged for Native-Desk-capable users;
15. no `ignore_permissions`, manual DB commit or permission bypass is introduced.

## Freeze Rule

RIR2G2A may freeze only when the same exact runtime head passes:

- RetailEdge Theme Compatibility;
- Linters / Semgrep / vulnerable dependency audit;
- clean Frappe v16 CI;
- EdgeSuite UI Candidate Compatibility.

Browser/persona acceptance remains deferred to consolidated RIR2E.
