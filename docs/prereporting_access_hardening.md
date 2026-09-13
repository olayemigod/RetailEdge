# RetailEdge Pre-Reporting Access Hardening

## B1 — EdgeSuite-only access foundation

This checkpoint hardens RetailEdge's integration with the governed EdgeSuite UI 1.1.0 Desk Access Management contract before reporting development resumes.

## Access model

RetailEdge operational roles intentionally retain Frappe `desk_access = 1`.

EdgeSuite operational pages run inside Frappe Desk, so normal RetailEdge operators must remain valid **System Users**. The shared EdgeSuite UI app owns the separate per-user **EdgeSuite Desk Access** selector and resolves one of these interface modes:

- `native_desk`
- `edgesuite_only`
- `website`

This selector controls interface exposure only. It does not grant or replace DocType permissions, Page permissions, Report permissions, Role Profiles, User Permissions, Company or Branch scope, workflow authority, accounting authorization, stock authorization, or product-specific backend validation.

## B1 changes

- Business Hub Page targets now use Frappe v16 `Page.is_permitted()` before they are advertised.
- Business Hub context consumes and exposes the shared EdgeSuite access context.
- Native-document fallback is enabled only when the shared access context permits native Desk.
- `native_fallback` quick actions are omitted for EdgeSuite-only users.
- Business Hub shell navigation preserves `link_type` and `link_to`, allowing the shared EdgeSuite access guard to remove native DocType and Report destinations for restricted users.
- Guided dialogs hide **Open Full Form** when native Desk is unavailable.
- Guided draft saves remain on the EdgeSuite operational surface for restricted users instead of routing them into a native ERPNext Form that the shared guard would reject.
- Native Desk users retain the existing full-form continuation and fallback behaviour.

## Backward compatibility

If RetailEdge is temporarily deployed before the compatible EdgeSuite UI access-control module is available, the RetailEdge adapter resolves to native-Desk-capable presentation rather than locking existing System Users out. Frappe/ERPNext permissions remain authoritative throughout that rolling-deploy condition.

The governed RetailEdge compatibility workflow continues to pin and verify the approved EdgeSuite UI 1.1.0 candidate.

## Deliberately unchanged

B1 does **not**:

- rename RetailEdge roles or Role Profiles;
- set RetailEdge operational roles to `desk_access = 0`;
- broaden ERPNext/Frappe permissions;
- bypass Page, Report, DocType, Company, Branch, workflow, stock, payment or accounting authorization;
- mutate submitted accounting or stock documents;
- replace every remaining native ERPNext workflow with a new RetailEdge workflow;
- start reporting implementation.

## Validation requirements

Before freezing B1:

1. Page navigation follows native Frappe Page permission and fails closed on lookup/permission errors.
2. EdgeSuite-only context hides native-only quick actions and full-form fallback controls.
3. EdgeSuite-only guided saves do not navigate to native Form routes.
4. Native Desk users retain existing fallback behaviour.
5. RetailEdge roles remain System-User-capable.
6. Business Hub preserves native link metadata for the shared EdgeSuite route filter.
7. Theme Compatibility, Linters, clean Frappe v16 install/migrate/full RetailEdge tests, and governed EdgeSuite UI candidate compatibility pass on the exact B1 head.

## Next pre-reporting slices

After B1 is green, continue with:

1. EdgeSuite-first everyday operational surface completeness.
2. Company and Branch scope hardening.
3. Performance and request-efficiency review.
4. Persona-based automated QA matrix.
5. Consolidated manual browser QA.
6. Reporting readiness decision.
