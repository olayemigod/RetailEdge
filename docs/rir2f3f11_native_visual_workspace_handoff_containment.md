# RIR2F3F11 — Native Visual Workspace Handoff Containment

## Decision

RetailEdge's shared native-visual control workspace remains a read-only EdgeSuite overview. Native ERPNext DocType/report handoffs from that shared component are available only when the final RetailEdge access context grants Native Desk access.

This slice does **not** claim that the overview pages own ERPNext creation, editing, submission, lifecycle or report workflows. The underlying ERPNext capabilities therefore remain present in the product where currently required; F3F11 only closes the shared component's unconditional EdgeSuite-to-Desk escape paths.

## Business goal

Keep EdgeSuite-only users inside the RetailEdge experience while preserving deliberate advanced ERPNext access for authorized users. Avoid hiding genuine business capability before an EdgeSuite replacement exists.

## Affected shared surfaces

The shared `NativeERPNextWorkspace.vue` currently powers control/overview pages including:

- Pricing & Promotions
- Assets
- Service & Warranty
- Sales Team, Targets & Commissions
- Budgeting & Cost Control
- Stock Traceability

The rule applies once in the shared component rather than being reimplemented separately in each wrapper page.

## Implementation contract

1. Default `canUseNativeDesk` to `false`.
2. Resolve access from the final RetailEdge Business Hub context, using `retailedge.master_experience.get_master_retailedge_business_hub_context` when the shared browser helper is unavailable.
3. Set Native Desk permission only from `navigation.access.can_use_native_desk`.
4. EdgeSuite `page` sources remain directly usable for all users who can see the workspace.
5. Native ERPNext `doctype` and `report` source buttons are hidden when Native Desk is unavailable.
6. Native `New`, `View all`, recent-record row open, DocType list and report routing are also code-guarded, not only visually hidden.
7. The embedded shared menu must not expose DocType/report destinations to EdgeSuite-only users from this component. EdgeSuite Pages and URLs remain usable.
8. Read-only metrics, previews, source descriptions and record rows remain visible according to their existing backend permission/scope rules.
9. When Native Desk is available, current native handoff behaviour remains unchanged and ERPNext permissions remain authoritative.

## Out of scope

- Rebuilding Pricing Rule, Item Price, Asset, Warranty, Maintenance, Sales Person, Sales Partner, Budget, Cost Center, Batch or Serial No workflows in EdgeSuite.
- Marking the underlying navigation peers as `native_fallback` in this slice.
- New DocTypes, ledgers, schemas, patches or migrations.
- Changes to ERPNext document lifecycle, accounting, stock, pricing, commission, asset, warranty or budgeting semantics.
- Permission overrides or new roles.

## Safety rules

- ERPNext remains the source of truth for native document/report workflows.
- No submitted accounting or stock document is mutated by this slice.
- Backend preview scoping and Frappe permissions remain unchanged.
- Access failure must fail closed for Native Desk handoff.
- Do not create a shadow lifecycle or duplicate operational engine.

## Follow-up

Each control area can later receive a separate ownership slice. A native peer should be retired from everyday navigation only after EdgeSuite provides the required create/edit/review lifecycle for that business workflow and the exact replacement coverage is tested.
