# Phase 2 — Operating Branch Switcher

## Business goal

Give each RetailEdge user an explicit **Operating Company** and **Operating Branch** context so new work starts in the correct branch without changing historical document truth.

The operating context is a user/session convenience and control layer. It is not a new accounting dimension, stock ledger, document owner, or replacement for ERPNext Company/Branch/Warehouse fields.

## Product layer

Phase 2 belongs in RetailEdge today because RetailEdge needs the operating context immediately for guided sales, purchases, payments, stock and POS workflows. The implementation must remain compatible with the long-term CoreEdge context service and keep existing CoreEdge/user-default/Branch Profile resolution as fallback.

## Core contracts

1. Existing submitted or draft documents retain their stored Company, Branch, Warehouse, POS Profile and accounting values.
2. The Operating Branch guides **new** guided drafts/defaults only when the caller has not made an explicit valid selection.
3. Explicit Warehouse/Stock Location remains authoritative when supplied.
4. Branch selection is validated server-side for:
   - Company read permission;
   - Branch read permission;
   - Company/Branch association where Branch has a Company field;
   - active/not-disabled Branch state where supported;
   - RetailEdge/CoreEdge/User Permission branch restrictions;
   - enabled Branch Setup membership where Branch Users are configured for a non-global user.
5. Allowed Company/Branch options are permission-aware and bounded; do not preload unrelated masters.
6. Branch Profile remains the source of RetailEdge operational defaults such as POS Profile, stock locations, cost centres and payment accounts.
7. Existing branch resolvers remain fallback/historical resolvers and are not deleted.
8. A context switch must not silently rewrite an open document.
9. An active POSNext shift or ERPNext POS Opening Entry blocks switching to a different Company/Branch server-side.
10. Unsaved browser-only POS/cart/payment state uses a client guard extension point; provider-specific cart integration is not falsely claimed by this phase.
11. Broad full-form, POS Profile, report and dashboard default activation belongs to **Phase 3 — Branch defaults & operational context activation**.

## Delivery slices

### 2A — Operating context service — implemented

- `retailedge/operating_context.py`
- Session-scoped cache keyed by user + Frappe session id.
- 12-hour TTL; clearable without changing Frappe User Defaults.
- APIs:
  - `get_operating_context`
  - `get_allowed_operating_contexts`
  - `switch_operating_context`
  - `clear_operating_context`
- Existing user/CoreEdge/default resolver used only when no valid session override exists.
- Company, Branch, branch/company association and disabled state are validated server-side.
- Non-global users are additionally constrained by configured Branch Setup membership when available.
- Previewing another Company's Branch options does not mutate or clear the active context.
- Clearing a session override resolves the fallback first and applies the same POS switch-safety gate before changing context.

### 2B — Guided-entry integration — implemented

- `guided_entry_context.resolve_branch_warehouse_selection` consumes Operating Branch only when Branch and Stock Location are both absent.
- Explicit Company/Branch/Stock Location selections continue to win.
- Branch Profile resolves the correct stock-location preference for sales, purchases, source, target or default use.
- Internal ERPNext `Warehouse` identities and fields remain unchanged.

### 2C — Shell switcher and POS protection — implemented for Phase 2

- Dedicated `Operating Context` Page under RetailEdge Home.
- Current Operating Company/Branch flows into the existing EdgeSuite product profile through the canonical Business Hub context.
- Company → Branch selection cascades using bounded permission-aware server options.
- Successful switch invalidates the existing Business Hub context cache and refreshes the product menu.
- Server-side switch blockers cover:
  - POSNext `POS Opening Shift`;
  - ERPNext `POS Opening Entry`.
- Client-side `window.retailedgeOperatingContextGuard.getBlocker()` extension point is available for browser-only unsaved cart/payment state. The actual provider-specific cart guard is deferred until the POS integration phase where that state is owned.

### 2D — Phase 2 hardening/audit — current gate

- Audit branch/company isolation, fallback behavior, cache/session lifecycle, Page visibility, switch safety and multi-app coexistence.
- Lock safety findings with regression tests.
- Run fresh exact-head Linters and clean Frappe v16 CI.
- Defer manual/browser QA until predecessor QA/promotion reaches this stacked PR.

## Deferred to Phase 3 — Branch defaults & operational context activation

Phase 3 will consume the trusted Phase 2 Operating Context more broadly. It should cover, where appropriate:

- full-form new-document defaults;
- branch-specific POS Profile activation and related operational defaults;
- report/dashboard default filters while still allowing authorized users to broaden scope;
- additional branch-aware operational pages and workflows;
- migration/backward-compatibility review for the wider activation layer.

Phase 2 does **not** turn Operating Branch into a hard historical-document filter or a competing source of document truth.

## Out of scope

- No Company/Branch field rewrite on existing documents.
- No new accounting dimension.
- No parallel Warehouse/Stock Location DocType.
- No Branch rename or internal ERPNext field rename.
- No automatic submission or posting.
- No CoreEdge package requirement for standalone RetailEdge.
- No broad report enforcement that prevents authorized users from broadening scope.
- No claim that unsaved POSNext/ERPNext browser carts are detected until the owning POS integration supplies the guard.

## Security and accounting safety

- No `ignore_permissions`.
- No manual database commit.
- No submitted-document mutation.
- Company remains a hard accounting boundary.
- ERPNext Warehouse remains stock truth.
- Branch Profile only supplies defaults; ERPNext document validation remains authoritative.
- Client-side filtering/guards never replace server-side validation.
- Clearing or previewing context cannot be used to bypass branch/POS safety.

## Tests required

### Unit/static contract

- session key and expiry behavior;
- permission-aware Company/Branch queries;
- disabled/wrong-company/unauthorized Branch rejection;
- Branch Setup membership restriction;
- fallback resolver preservation;
- safe default-context restore;
- explicit selection precedence;
- Branch Profile default projection;
- POSNext and ERPNext POS switch blockers;
- no broad `get_all`, `ignore_permissions`, manual commit or accounting-document mutation.

### Integration

- switch then new guided Sales Invoice resolves branch sales stock location;
- switch then Purchase Invoice resolves receiving stock location;
- switch then Stock Transfer resolves source/target defaults correctly;
- invalid branch/company combination blocked;
- unauthorized branch blocked;
- Branch Setup-unassigned branch blocked where Branch Users are configured;
- clear context restores configured fallback only when switch-safe;
- multi-company user switches only to permitted company/branch combinations;
- active POSNext/ERPNext POS session allows same-context use but blocks cross-context switch.

### Manual browser QA

- current company/branch visible in shell;
- Company → Branch cascade;
- invalid dependent Branch clears on Company change;
- switch refreshes guided-create defaults without reload surprises;
- existing open document remains unchanged;
- branch-specific guided stock-location defaults are respected;
- active POS session blocks cross-branch switching;
- client guard behaves correctly once an owning POS integration provides browser-state evidence;
- mobile/responsive picker behavior;
- multi-app shell remains stable.

## Phase closure

Phase 2 implementation may be automated/audited while predecessor browser QA is pending. It remains a stacked Draft PR. Before Phase 2 manual QA/promotion, reconcile against the promoted/moved predecessor if needed and require fresh exact-head automated validation.
